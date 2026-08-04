"""Extract frozen timm embeddings and run fold-wise Logistic Regression OOF.

This script is a fast diagnostic: it tests whether pretrained visual features
contain minority-class signal before expensive end-to-end fine-tuning.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader

from classification_common import (
    LABELS,
    ClassificationDataset,
    build_cv_records,
    build_model,
    build_transforms,
    confusion_matrix_from_ids,
    json_ready,
    metrics_from_confusion,
    seed_everything,
    write_prediction_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path(r"D:\研究生作业\人工智能实践比赛\水域综合异常识别_训练集+验证集"),
    )
    parser.add_argument("--train-json", type=Path, default=None)
    parser.add_argument(
        "--manifest", type=Path, default=Path("competition/shuzhi_anomaly/generated/data_manifest.csv")
    )
    parser.add_argument("--train-index", type=Path, required=True)
    parser.add_argument("--cv-manifest", type=Path, required=True)
    parser.add_argument("--folds", type=int, nargs="+", default=[0, 1, 2, 3])
    parser.add_argument("--model", default="convnext_tiny_384")
    parser.add_argument("--cache-dir", type=Path, default=Path("weights/timm"))
    parser.add_argument("--image-size", type=int, default=384)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--c", type=float, default=1.0)
    parser.add_argument(
        "--class-weight", choices=("none", "balanced", "power"), default="none"
    )
    parser.add_argument("--power-alpha", type=float, default=0.25)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()


@torch.inference_mode()
def extract(model, loader, device: torch.device):
    model.eval()
    feature_rows: list[np.ndarray] = []
    label_rows: list[int] = []
    filenames: list[str] = []
    for images, targets, batch_filenames in loader:
        images = images.to(device, non_blocking=True)
        with torch.autocast(
            device_type="cuda", dtype=torch.float16, enabled=device.type == "cuda"
        ):
            features = model(images)
        if features.ndim > 2:
            features = features.flatten(1)
        feature_rows.append(features.float().cpu().numpy())
        label_rows.extend(targets.tolist())
        filenames.extend(batch_filenames)
    return np.concatenate(feature_rows), np.asarray(label_rows), filenames


def main() -> int:
    args = parse_args()
    seed_everything(args.seed)
    source_root = args.source_root.resolve()
    train_json = (
        args.train_json.resolve()
        if args.train_json
        else (source_root / "train.json").resolve()
    )
    bundle = build_model(
        args.model,
        num_classes=0,
        pretrained=True,
        cache_dir=args.cache_dir.resolve(),
    )
    device = torch.device(args.device)
    model = bundle.model.to(device)
    transform = build_transforms(
        image_size=args.image_size, data_config=bundle.data_config, train=False
    )
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    all_oof_rows: list[dict[str, object]] = []
    fold_metrics: list[dict[str, object]] = []

    for fold in args.folds:
        train_records, val_records, _ = build_cv_records(
            source_root=source_root,
            train_json=train_json,
            manifest_path=args.manifest.resolve(),
            train_index_path=args.train_index.resolve(),
            cv_manifest_path=args.cv_manifest.resolve(),
            fold=fold,
        )
        train_loader = DataLoader(
            ClassificationDataset(train_records, transform),
            batch_size=args.batch_size,
            shuffle=False,
            num_workers=args.workers,
            pin_memory=device.type == "cuda",
            persistent_workers=args.workers > 0,
        )
        val_loader = DataLoader(
            ClassificationDataset(val_records, transform),
            batch_size=args.batch_size,
            shuffle=False,
            num_workers=args.workers,
            pin_memory=device.type == "cuda",
            persistent_workers=args.workers > 0,
        )
        x_train, y_train, _ = extract(model, train_loader, device)
        x_val, y_val, val_names = extract(model, val_loader, device)
        scaler = StandardScaler()
        x_train = scaler.fit_transform(x_train)
        x_val = scaler.transform(x_val)

        class_weight = "balanced" if args.class_weight == "balanced" else None
        classifier = LogisticRegression(
            C=args.c,
            max_iter=5000,
            class_weight=class_weight,
            random_state=args.seed,
        )
        sample_weight = None
        if args.class_weight == "power":
            counts = np.bincount(y_train, minlength=len(LABELS)).astype(np.float64)
            sample_weight = counts[y_train] ** (-args.power_alpha)
        classifier.fit(x_train, y_train, sample_weight=sample_weight)
        raw_probabilities = classifier.predict_proba(x_val)
        probabilities = np.zeros((len(y_val), len(LABELS)), dtype=np.float64)
        probabilities[:, classifier.classes_.astype(int)] = raw_probabilities
        predictions = probabilities.argmax(axis=1)
        matrix = confusion_matrix_from_ids(y_val, predictions)
        metrics = metrics_from_confusion(matrix)
        metrics["fold"] = fold
        fold_metrics.append(metrics)
        print(
            f"fold={fold} weighted_f1={metrics['weighted_f1']:.4f} "
            f"macro_f1={metrics['macro_f1']:.4f} mIoU={metrics['mIoU']:.4f}"
        )

        for filename, target_id, pred_id, prob_row in zip(
            val_names, y_val.tolist(), predictions.tolist(), probabilities.tolist()
        ):
            row: dict[str, object] = {
                "filename": filename,
                "fold": fold,
                "true_label_id": target_id,
                "true_label": LABELS[target_id],
                "pred_label_id": pred_id,
                "pred_label": LABELS[pred_id],
            }
            row.update({f"logit_{label}": "" for label in LABELS})
            row.update({f"prob_{label}": value for label, value in zip(LABELS, prob_row)})
            all_oof_rows.append(row)

    write_prediction_csv(out_dir / "oof_predictions.csv", all_oof_rows)
    y_true = [int(row["true_label_id"]) for row in all_oof_rows]
    y_pred = [int(row["pred_label_id"]) for row in all_oof_rows]
    global_metrics = metrics_from_confusion(confusion_matrix_from_ids(y_true, y_pred))
    report = {
        "model": args.model,
        "resolved_model_name": bundle.resolved_name,
        "class_weight": args.class_weight,
        "power_alpha": args.power_alpha,
        "fold_metrics": fold_metrics,
        "global_oof_metrics": global_metrics,
    }
    (out_dir / "feature_screening_metrics.json").write_text(
        json.dumps(json_ready(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"global_oof weighted_f1={global_metrics['weighted_f1']:.6f} "
        f"macro_f1={global_metrics['macro_f1']:.6f} mIoU={global_metrics['mIoU']:.6f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
