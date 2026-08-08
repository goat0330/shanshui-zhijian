"""Robust timm trainer for the six-class water anomaly competition.

Key repairs versus the earlier adapter:
- official ConvNeXt 22K->1K 384 checkpoint can be loaded through an alias;
- true CE baseline defaults to label_smoothing=0;
- head / staged unfreezing and differential learning rates;
- AMP and early stopping;
- per-sample best-epoch OOF logits/probabilities;
- EXIF-safe JPG/PNG loading and model-config-aware resize+padding;
- legacy class_sequence sampler is blocked because it truncates each class to
  the rarest-class capacity.
"""
from __future__ import annotations

import argparse
import csv
import json
from contextlib import nullcontext
from pathlib import Path

import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader, WeightedRandomSampler

from classification_common import (
    LABELS,
    ClassificationDataset,
    build_cv_records,
    build_model,
    build_transforms,
    configure_trainable_layers,
    confusion_matrix_from_ids,
    json_ready,
    metrics_from_confusion,
    optimizer_param_groups,
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
        "--manifest",
        type=Path,
        default=Path("competition/shuzhi_anomaly/generated/data_manifest.csv"),
    )
    parser.add_argument("--train-index", type=Path, required=True)
    parser.add_argument(
        "--cv-manifest",
        type=Path,
        required=True,
        help="Internal labeled CV manifest with filename and fold columns.",
    )
    parser.add_argument("--fold", type=int, required=True)
    parser.add_argument(
        "--label-version", choices=("raw_v1", "reviewed_v1", "reviewed_v2"), default="raw_v1"
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--model",
        default="convnext_tiny_384",
        help=(
            "Alias or timm model name. convnext_tiny_384 resolves to "
            "hf-hub:timm/convnext_tiny.fb_in22k_ft_in1k_384."
        ),
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("weights/timm"))
    parser.add_argument("--init-checkpoint", type=Path, default=None)
    parser.add_argument("--copy-paste-manifest", type=Path, default=None)
    parser.add_argument("--copy-paste-root", type=Path, default=None)
    parser.add_argument("--image-size", type=int, default=384)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--freeze-mode",
        choices=("full", "head", "last_stage", "last2_stages"),
        default="head",
    )
    parser.add_argument("--backbone-lr", type=float, default=2e-5)
    parser.add_argument("--head-lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=0.05)
    parser.add_argument("--label-smoothing", type=float, default=0.0)
    parser.add_argument("--logit-adjustment", type=float, default=0.0)
    parser.add_argument(
        "--loss", choices=("ce", "balanced_softmax"), default="ce"
    )
    parser.add_argument(
        "--sampler",
        choices=(
            "standard",
            "power_balanced",
            "scene_group_equal",
            "class_balanced_legacy",
            "class_sequence_legacy",
        ),
        default="standard",
    )
    parser.add_argument("--scene-group-manifest", type=Path, default=None)
    parser.add_argument(
        "--sampling-alpha",
        type=float,
        default=0.25,
        help="For power_balanced: per-sample weight = class_count ** (-alpha).",
    )
    parser.add_argument("--samples-per-epoch", type=int, default=0)
    parser.add_argument("--early-stopping-patience", type=int, default=6)
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument(
        "--selection-metric",
        choices=("weighted_f1", "macro_f1", "mIoU", "accuracy"),
        default="weighted_f1",
    )
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--pretrained", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()


def load_copy_paste_records(
    manifest_path: Path,
    image_root: Path,
    cv_map: dict[str, dict[str, str]],
    fold: int,
) -> list[dict[str, object]]:
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    records: list[dict[str, object]] = []
    skipped = 0
    for row in rows:
        foreground = row["foreground"]
        background = row["background"]
        if foreground not in cv_map or background not in cv_map:
            raise ValueError(f"copy-paste source is absent from CV manifest: {row['id']}")
        if int(cv_map[foreground]["fold"]) == fold or int(cv_map[background]["fold"]) == fold:
            skipped += 1
            continue
        path = image_root / "images" / f"{row['id']}.jpg"
        if not path.exists():
            raise FileNotFoundError(f"copy-paste image missing: {path}")
        records.append(
            {
                "filename": f"copy_paste/{row['id']}.jpg",
                "path": path,
                "label": "乱堆",
                "label_id": LABELS.index("乱堆"),
                "sequence_id": f"copy_paste_{row['foreground']}",
            }
        )
    print(
        f"copy_paste candidates: added={len(records)} skipped_for_fold={skipped} "
        f"fold={fold} manifest={manifest_path}"
    )
    return records


def load_scene_group_map(manifest_path: Path) -> dict[str, str]:
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    mapping: dict[str, str] = {}
    for row in rows:
        filename = row["filename"]
        scene_group = row.get("scene_group", "").strip()
        if not filename or not scene_group:
            raise ValueError(f"scene_group is empty for {filename or '<unknown>'}")
        mapping[filename] = scene_group
    if not mapping:
        raise ValueError(f"scene_group manifest is empty: {manifest_path}")
    return mapping


class BalancedSoftmaxLoss(nn.Module):
    def __init__(self, class_counts: Tensor, label_smoothing: float = 0.0):
        super().__init__()
        self.register_buffer("log_counts", class_counts.float().clamp_min(1).log())
        self.label_smoothing = label_smoothing

    def forward(self, logits: Tensor, targets: Tensor) -> Tensor:
        return nn.functional.cross_entropy(
            logits + self.log_counts,
            targets,
            label_smoothing=self.label_smoothing,
        )


def make_grad_scaler(enabled: bool):
    try:
        return torch.amp.GradScaler("cuda", enabled=enabled)
    except (AttributeError, TypeError):
        return torch.cuda.amp.GradScaler(enabled=enabled)


def autocast_context(enabled: bool):
    if not enabled:
        return nullcontext()
    return torch.autocast(device_type="cuda", dtype=torch.float16)


def resolve_train_json(args: argparse.Namespace) -> Path:
    if args.train_json is not None:
        return args.train_json.resolve()
    if args.label_version == "raw_v1":
        return (args.source_root.resolve() / "train.json").resolve()
    return Path(
        f"competition/shuzhi_anomaly/generated/train_{args.label_version}.json"
    ).resolve()


def build_sampler(
    args: argparse.Namespace,
    records: list[dict[str, object]],
    scene_group_map: dict[str, str] | None = None,
):
    if args.sampler == "standard":
        return None
    if args.sampler == "class_sequence_legacy":
        raise ValueError(
            "class_sequence_legacy is intentionally blocked: the old implementation "
            "sets every class budget to the rarest-class capacity and discarded nearly "
            "all training rows. Use standard or power_balanced."
        )
    if args.sampler == "scene_group_equal":
        if scene_group_map is None:
            raise ValueError("scene_group_equal requires --scene-group-manifest")
        dump_id = LABELS.index("乱堆")
        dump_indices = [
            index
            for index, row in enumerate(records)
            if int(row["label_id"]) == dump_id
        ]
        if not dump_indices:
            raise ValueError("scene_group_equal found no 乱堆 training records")
        group_by_index: dict[int, str] = {}
        group_counts: dict[str, int] = {}
        for index in dump_indices:
            filename = str(records[index]["filename"])
            if filename not in scene_group_map:
                raise ValueError(f"missing scene_group for 乱堆 record: {filename}")
            group = scene_group_map[filename]
            group_by_index[index] = group
            group_counts[group] = group_counts.get(group, 0) + 1
        weights = torch.ones(len(records), dtype=torch.double)
        dump_total = len(dump_indices)
        group_total = len(group_counts)
        for index, group in group_by_index.items():
            weights[index] = dump_total / (group_total * group_counts[group])
        num_samples = args.samples_per_epoch or len(records)
        print(
            "scene_group sampler:",
            group_counts,
            "dump_total:",
            dump_total,
            "num_samples:",
            num_samples,
        )
        return WeightedRandomSampler(weights, num_samples=num_samples, replacement=True)
    labels = torch.tensor([int(row["label_id"]) for row in records])
    counts = torch.bincount(labels, minlength=len(LABELS)).float()
    if args.sampler == "class_balanced_legacy":
        alpha = 1.0
        print("WARNING: class_balanced_legacy is aggressive and previously caused severe false positives.")
    else:
        alpha = args.sampling_alpha
        if not (0.0 <= alpha <= 1.0):
            raise ValueError("--sampling-alpha must be between 0 and 1")
    weights = counts[labels].pow(-alpha)
    num_samples = args.samples_per_epoch or len(records)
    print(
        "sampler counts:",
        dict(zip(LABELS, counts.tolist())),
        "alpha:",
        alpha,
        "num_samples:",
        num_samples,
    )
    return WeightedRandomSampler(weights, num_samples=num_samples, replacement=True)


def run_epoch(
    *,
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    fold: int,
    optimizer: torch.optim.Optimizer | None,
    scaler,
    amp_enabled: bool,
    grad_clip: float,
    logit_adjustment: Tensor | None,
) -> tuple[float, Tensor, list[dict[str, object]]]:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    total_count = 0
    target_ids: list[int] = []
    prediction_ids: list[int] = []
    rows: list[dict[str, object]] = []

    for images, targets, filenames in loader:
        images = images.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)
        if training:
            optimizer.zero_grad(set_to_none=True)

        with torch.set_grad_enabled(training):
            with autocast_context(amp_enabled):
                logits = model(images)
                loss_logits = (
                    logits + logit_adjustment
                    if logit_adjustment is not None
                    else logits
                )
                loss = criterion(loss_logits, targets)
            if training:
                scaler.scale(loss).backward()
                if grad_clip > 0:
                    scaler.unscale_(optimizer)
                    nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
                scaler.step(optimizer)
                scaler.update()

        batch_size = targets.size(0)
        total_loss += float(loss.item()) * batch_size
        total_count += batch_size
        raw_logits = logits.detach().float().cpu()
        probabilities = raw_logits.softmax(dim=1)
        predictions = raw_logits.argmax(dim=1)
        target_cpu = targets.detach().cpu()
        target_ids.extend(target_cpu.tolist())
        prediction_ids.extend(predictions.tolist())

        if not training:
            for filename, target_id, pred_id, logit_row, prob_row in zip(
                filenames,
                target_cpu.tolist(),
                predictions.tolist(),
                raw_logits.tolist(),
                probabilities.tolist(),
            ):
                row: dict[str, object] = {
                    "filename": filename,
                    "fold": fold,
                    "true_label_id": target_id,
                    "true_label": LABELS[target_id],
                    "pred_label_id": pred_id,
                    "pred_label": LABELS[pred_id],
                }
                row.update({f"logit_{label}": value for label, value in zip(LABELS, logit_row)})
                row.update({f"prob_{label}": value for label, value in zip(LABELS, prob_row)})
                rows.append(row)

    matrix = confusion_matrix_from_ids(target_ids, prediction_ids)
    return total_loss / max(total_count, 1), matrix, rows


def main() -> int:
    args = parse_args()
    seed_everything(args.seed)
    source_root = args.source_root.resolve()
    train_json = resolve_train_json(args)
    train_records, val_records, cv_map = build_cv_records(
        source_root=source_root,
        train_json=train_json,
        manifest_path=args.manifest.resolve(),
        train_index_path=args.train_index.resolve(),
        cv_manifest_path=args.cv_manifest.resolve(),
        fold=args.fold,
    )
    if args.copy_paste_manifest is not None:
        copy_paste_root = (
            args.copy_paste_root.resolve()
            if args.copy_paste_root is not None
            else args.copy_paste_manifest.resolve().parent
        )
        train_records.extend(
            load_copy_paste_records(
                args.copy_paste_manifest.resolve(),
                copy_paste_root,
                cv_map,
                args.fold,
            )
        )

    bundle = build_model(
        args.model,
        num_classes=len(LABELS),
        pretrained=args.pretrained,
        cache_dir=args.cache_dir.resolve(),
        checkpoint_path=args.init_checkpoint.resolve() if args.init_checkpoint else None,
    )
    trainable = configure_trainable_layers(bundle.model, args.freeze_mode)
    print(
        f"model={bundle.resolved_name} freeze_mode={args.freeze_mode} "
        f"trainable={trainable['trainable']:,}/{trainable['total']:,}"
    )

    train_transform = build_transforms(
        image_size=args.image_size, data_config=bundle.data_config, train=True
    )
    val_transform = build_transforms(
        image_size=args.image_size, data_config=bundle.data_config, train=False
    )
    train_dataset = ClassificationDataset(train_records, train_transform)
    val_dataset = ClassificationDataset(val_records, val_transform)
    scene_group_map = (
        load_scene_group_map(args.scene_group_manifest.resolve())
        if args.scene_group_manifest is not None
        else None
    )
    sampler = build_sampler(args, train_records, scene_group_map)
    device = torch.device(args.device)
    pin_memory = device.type == "cuda"
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        sampler=sampler,
        shuffle=sampler is None,
        num_workers=args.workers,
        pin_memory=pin_memory,
        persistent_workers=args.workers > 0,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=pin_memory,
        persistent_workers=args.workers > 0,
    )

    model = bundle.model.to(device)
    class_counts = torch.bincount(
        torch.tensor([int(row["label_id"]) for row in train_records]),
        minlength=len(LABELS),
    ).float()
    if args.loss == "balanced_softmax":
        criterion: nn.Module = BalancedSoftmaxLoss(
            class_counts.to(device), label_smoothing=args.label_smoothing
        )
    else:
        criterion = nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)

    optimizer = torch.optim.AdamW(
        optimizer_param_groups(
            model,
            backbone_lr=args.backbone_lr,
            head_lr=args.head_lr,
            weight_decay=args.weight_decay,
        )
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=max(args.epochs, 1)
    )
    amp_enabled = args.amp and device.type == "cuda"
    scaler = make_grad_scaler(amp_enabled)

    adjustment = None
    if args.logit_adjustment != 0:
        prior = class_counts / class_counts.sum()
        adjustment = args.logit_adjustment * prior.clamp_min(1e-12).log().to(device)

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    run_config = {
        **vars(args),
        "resolved_model_name": bundle.resolved_name,
        "model_data_config": bundle.data_config,
        "train_size": len(train_records),
        "val_size": len(val_records),
        "trainable_parameters": trainable,
        "train_json": train_json,
    }
    (out_dir / "run_config.json").write_text(
        json.dumps(json_ready(run_config), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    best_score = float("-inf")
    best_epoch = 0
    stale_epochs = 0
    history: list[dict[str, object]] = []
    for epoch in range(1, args.epochs + 1):
        train_loss, _, _ = run_epoch(
            model=model,
            loader=train_loader,
            criterion=criterion,
            device=device,
            fold=args.fold,
            optimizer=optimizer,
            scaler=scaler,
            amp_enabled=amp_enabled,
            grad_clip=args.grad_clip,
            logit_adjustment=adjustment,
        )
        val_loss, matrix, prediction_rows = run_epoch(
            model=model,
            loader=val_loader,
            criterion=criterion,
            device=device,
            fold=args.fold,
            optimizer=None,
            scaler=scaler,
            amp_enabled=amp_enabled,
            grad_clip=args.grad_clip,
            logit_adjustment=None,
        )
        metrics = metrics_from_confusion(matrix)
        metrics.update(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "val_loss": val_loss,
                "learning_rates": [group["lr"] for group in optimizer.param_groups],
            }
        )
        history.append(metrics)
        selection_score = float(metrics[args.selection_metric])
        print(
            f"epoch={epoch:03d} train_loss={train_loss:.4f} val_loss={val_loss:.4f} "
            f"weighted_f1={metrics['weighted_f1']:.4f} "
            f"macro_f1={metrics['macro_f1']:.4f} mIoU={metrics['mIoU']:.4f}",
            flush=True,
        )

        checkpoint = {
            "model": model.state_dict(),
            "model_name": args.model,
            "resolved_model_name": bundle.resolved_name,
            "labels": LABELS,
            "epoch": epoch,
            "metrics": metrics,
            "args": json_ready(vars(args)),
            "data_config": bundle.data_config,
        }
        torch.save(checkpoint, out_dir / "last.pt")

        if selection_score > best_score:
            best_score = selection_score
            best_epoch = epoch
            stale_epochs = 0
            torch.save(checkpoint, out_dir / "best.pt")
            write_prediction_csv(out_dir / "oof_predictions.csv", prediction_rows)
            (out_dir / "best_metrics.json").write_text(
                json.dumps(json_ready(metrics), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with (out_dir / "confusion_matrix.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as handle:
                writer = csv.writer(handle)
                writer.writerow(["true\\pred", *LABELS])
                for label, row in zip(LABELS, metrics["confusion_matrix"]):
                    writer.writerow([label, *row])
        else:
            stale_epochs += 1
        scheduler.step()

        (out_dir / "history.json").write_text(
            json.dumps(json_ready(history), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        if args.early_stopping_patience > 0 and stale_epochs >= args.early_stopping_patience:
            print(
                f"early_stop epoch={epoch} best_epoch={best_epoch} "
                f"best_{args.selection_metric}={best_score:.6f}"
            )
            break

    (out_dir / "history.json").write_text(
        json.dumps(json_ready(history), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"best_{args.selection_metric}={best_score:.6f} best_epoch={best_epoch} "
        f"checkpoint={out_dir / 'best.pt'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
