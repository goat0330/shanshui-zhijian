"""Small timm adapter for the six-class water anomaly classifier.

The script intentionally keeps the competition-specific code local:
JSON/manifest loading, class+sequence sampling, and confusion-matrix mIoU.
It never treats an unlabeled test directory as validation data.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import timm
import torch
from PIL import Image
from torch import Tensor, nn
from torch.utils.data import DataLoader, Dataset, Sampler
from torchvision import transforms


LABELS = ("乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常")
LABEL_TO_ID = {label: index for index, label in enumerate(LABELS)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path(r"D:\研究生作业\人工智能实践比赛\水域综合异常识别_训练集+验证集"),
    )
    parser.add_argument("--train-json", type=Path, default=None)
    parser.add_argument(
        "--val-json",
        type=Path,
        default=None,
        help="Labeled validation JSON. If omitted, use rows with split=val in --manifest.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("competition/shuzhi_anomaly/generated/data_manifest.csv"),
    )
    parser.add_argument(
        "--train-index",
        type=Path,
        default=None,
        help="Optional non-destructive train_index.csv; only training_use=True rows are used.",
    )
    parser.add_argument("--out-dir", type=Path, default=Path("runs/shuzhi_baseline"))
    parser.add_argument("--model", default="resnet18")
    parser.add_argument(
        "--image-size",
        type=int,
        default=384,
        help="Square output size after aspect-preserving resize and padding.",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--sampler",
        choices=("standard", "class_sequence"),
        default="standard",
        help="standard is the safe baseline; class_sequence is an ablation only.",
    )
    parser.add_argument(
        "--max-frames-per-sequence",
        type=int,
        default=4,
        choices=(1, 2, 3, 4),
    )
    parser.add_argument("--label-smoothing", type=float, default=0.03)
    parser.add_argument("--logit-adjustment", type=float, default=0.0)
    parser.add_argument(
        "--selection-metric",
        choices=("miou", "macro_f1", "accuracy"),
        default="miou",
        help="Metric used to select best.pt; mIoU matches the competition objective.",
    )
    parser.add_argument(
        "--cv-manifest",
        type=Path,
        default=None,
        help="Optional internal CV manifest produced by build_internal_cv.py.",
    )
    parser.add_argument(
        "--fold",
        type=int,
        default=None,
        help="Validation fold when --cv-manifest is supplied.",
    )
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--pretrained", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_json_records(path: Path) -> list[dict[str, object]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"expected a list of labeled records: {path}")
    result = []
    for record in records:
        filename = str(record["filename"])
        label = str(record["label"])
        if label not in LABEL_TO_ID:
            raise ValueError(f"unknown label {label!r}: {filename}")
        result.append({"filename": filename, "label": label})
    return result


def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = {}
    for row in rows:
        filename = row.get("filename", "")
        if filename:
            result[filename] = row
    return result


def load_train_index(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {"filename": row["filename"], "label": row["label"]}
        for row in rows
        if row.get("training_use", "").lower() == "true"
    ]


def discover_images(source_root: Path) -> dict[str, list[Path]]:
    result: dict[str, list[Path]] = defaultdict(list)
    for path in source_root.rglob("*.jpg"):
        result[path.name].append(path)
    return result


def resolve_labeled_records(
    records: Iterable[dict[str, object]],
    source_root: Path,
    manifest: dict[str, dict[str, str]],
    images: dict[str, list[Path]],
) -> list[dict[str, object]]:
    resolved = []
    for record in records:
        filename = str(record["filename"])
        manifest_row = manifest.get(filename, {})
        relative_path = manifest_row.get("relative_path", "")
        path = source_root / relative_path if relative_path else None
        if path is None or not path.exists():
            candidates = images.get(filename, [])
            if len(candidates) != 1:
                raise FileNotFoundError(
                    f"cannot resolve a unique image for {filename}: {candidates}"
                )
            path = candidates[0]
        sequence_id = manifest_row.get("sequence_id") or f"filename_{filename}"
        resolved.append(
            {
                "filename": filename,
                "path": path,
                "label": str(record["label"]),
                "label_id": LABEL_TO_ID[str(record["label"])],
                "sequence_id": sequence_id,
            }
        )
    return resolved


class WaterDataset(Dataset[tuple[Tensor, int]]):
    def __init__(self, records: list[dict[str, object]], transform: transforms.Compose):
        self.records = records
        self.transform = transform

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[Tensor, int]:
        record = self.records[index]
        with Image.open(record["path"]) as image:
            image = image.convert("RGB")
        return self.transform(image), int(record["label_id"])


class ClassSequenceSampler(Sampler[int]):
    """Equal class budget; each sequence contributes at most N frames/epoch."""

    def __init__(
        self,
        records: list[dict[str, object]],
        max_frames_per_sequence: int,
        seed: int,
    ):
        self.seed = seed
        self.epoch = 0
        grouped: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
        for index, record in enumerate(records):
            grouped[int(record["label_id"])][str(record["sequence_id"])].append(index)
        self.grouped = grouped
        self.max_frames = max_frames_per_sequence
        self.capacity = {
            label_id: sum(
                min(self.max_frames, len(indices))
                for indices in sequence_rows.values()
            )
            for label_id, sequence_rows in grouped.items()
        }
        missing = sorted(set(range(len(LABELS))) - set(self.capacity))
        if missing:
            raise ValueError(f"training records are missing labels: {[LABELS[i] for i in missing]}")
        self.class_budget = min(self.capacity.values())
        if self.class_budget == 0:
            raise ValueError("class sequence sampler has zero capacity")

    def set_epoch(self, epoch: int) -> None:
        self.epoch = epoch

    def __iter__(self):
        rng = random.Random(self.seed + self.epoch)
        sampled: list[int] = []
        for label_id in range(len(LABELS)):
            candidates: list[int] = []
            sequences = list(self.grouped[label_id].items())
            rng.shuffle(sequences)
            for _, indices in sequences:
                shuffled = list(indices)
                rng.shuffle(shuffled)
                candidates.extend(shuffled[: self.max_frames])
            rng.shuffle(candidates)
            sampled.extend(candidates[: self.class_budget])
        rng.shuffle(sampled)
        return iter(sampled)

    def __len__(self) -> int:
        return self.class_budget * len(LABELS)


class ResizePad:
    """Preserve the whole scene instead of cropping away a small anomaly."""

    def __init__(self, size: int):
        self.size = size

    def __call__(self, image: Image.Image) -> Image.Image:
        width, height = image.size
        scale = self.size / max(width, height)
        resized = image.resize(
            (max(1, round(width * scale)), max(1, round(height * scale))),
            Image.Resampling.BILINEAR,
        )
        canvas = Image.new("RGB", (self.size, self.size), (123, 116, 103))
        left = (self.size - resized.width) // 2
        top = (self.size - resized.height) // 2
        canvas.paste(resized, (left, top))
        return canvas


def build_transforms(image_size: int) -> tuple[transforms.Compose, transforms.Compose]:
    train_transform = transforms.Compose(
        [
            ResizePad(image_size),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.15),
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ]
    )
    val_transform = transforms.Compose(
        [
            ResizePad(image_size),
            transforms.ToTensor(),
            transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
        ]
    )
    return train_transform, val_transform


def confusion_matrix(targets: Tensor, predictions: Tensor) -> Tensor:
    matrix = torch.zeros((len(LABELS), len(LABELS)), dtype=torch.int64)
    for target, prediction in zip(targets.tolist(), predictions.tolist()):
        matrix[target, prediction] += 1
    return matrix


def m_iou(matrix: Tensor) -> tuple[float, list[float | None]]:
    true_positive = matrix.diag().float()
    denominator = matrix.sum(dim=1) + matrix.sum(dim=0) - true_positive
    ious: list[float | None] = []
    for numerator, denom in zip(true_positive, denominator):
        ious.append(None if denom.item() == 0 else float((numerator / denom).item()))
    valid = [value for value in ious if value is not None]
    return (sum(valid) / len(valid) if valid else 0.0), ious


def classification_metrics(matrix: Tensor) -> dict[str, object]:
    true_positive = matrix.diag().float()
    support = matrix.sum(dim=1).float()
    predicted = matrix.sum(dim=0).float()
    precision_denominator = predicted.clamp_min(1.0)
    recall_denominator = support.clamp_min(1.0)
    precision = true_positive / precision_denominator
    recall = true_positive / recall_denominator
    f1 = 2 * precision * recall / (precision + recall).clamp_min(1e-12)
    total = matrix.sum().item()
    accuracy = float(true_positive.sum().item() / total) if total else 0.0
    macro_f1 = float(f1.mean().item())
    weighted_f1 = float((f1 * support / support.sum().clamp_min(1.0)).sum().item())
    return {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "balanced_accuracy": float(recall.mean().item()),
        "per_class_precision": dict(zip(LABELS, precision.tolist())),
        "per_class_recall": dict(zip(LABELS, recall.tolist())),
        "per_class_f1": dict(zip(LABELS, f1.tolist())),
        "prediction_distribution": matrix.sum(dim=0).tolist(),
    }


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
    adjustment: Tensor | None = None,
) -> tuple[float, Tensor]:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    total_count = 0
    target_rows: list[Tensor] = []
    prediction_rows: list[Tensor] = []
    for images, targets in loader:
        images = images.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)
        with torch.set_grad_enabled(training):
            logits = model(images)
            loss_logits = logits + adjustment if adjustment is not None else logits
            loss = criterion(loss_logits, targets)
            if training:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()
        total_loss += loss.item() * targets.size(0)
        total_count += targets.size(0)
        target_rows.append(targets.detach().cpu())
        prediction_rows.append(logits.argmax(dim=1).detach().cpu())
    matrix = confusion_matrix(torch.cat(target_rows), torch.cat(prediction_rows))
    return total_loss / max(total_count, 1), matrix


def main() -> int:
    args = parse_args()
    seed_everything(args.seed)
    source_root = args.source_root.resolve()
    train_json = (args.train_json or source_root / "train.json").resolve()
    manifest_path = args.manifest.resolve()
    manifest = load_manifest(manifest_path)
    images = discover_images(source_root)

    train_source_records = load_json_records(train_json)
    if args.train_index:
        train_index_path = args.train_index.resolve()
        if not train_index_path.exists():
            raise FileNotFoundError(f"train index does not exist: {train_index_path}")
        train_source_records = load_train_index(train_index_path)
    train_records = resolve_labeled_records(
        train_source_records, source_root, manifest, images
    )
    cv_map: dict[str, dict[str, str]] = {}
    if args.cv_manifest:
        if args.fold is None:
            raise ValueError("--fold is required when --cv-manifest is supplied")
        with args.cv_manifest.resolve().open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                cv_map[row["filename"]] = row
        if not cv_map:
            raise ValueError(f"internal CV manifest is empty: {args.cv_manifest}")
        train_source_records = [
            record for record in train_source_records
            if str(record["filename"]) in cv_map
            and int(cv_map[str(record["filename"])] ["fold"]) != args.fold
        ]
        val_source_records = [
            record for record in load_json_records(train_json)
            if str(record["filename"]) in cv_map
            and int(cv_map[str(record["filename"])] ["fold"]) == args.fold
        ]
        train_records = resolve_labeled_records(
            train_source_records, source_root, manifest, images
        )
        val_records = resolve_labeled_records(
            val_source_records, source_root, manifest, images
        )
    elif args.val_json:
        val_records = resolve_labeled_records(
            load_json_records(args.val_json.resolve()), source_root, manifest, images
        )
    else:
        val_records = []
        for row in manifest.values():
            if row.get("split") == "val" and row.get("label") in LABEL_TO_ID:
                val_records.append(
                    {
                        "filename": row["filename"],
                        "label": row["label"],
                    }
                )
        val_records = resolve_labeled_records(val_records, source_root, manifest, images)
    if not val_records:
        raise ValueError(
            "No labeled validation records found. Pass --val-json or provide labeled rows "
            "with split=val in --manifest; the unlabeled test directory is not validation."
        )

    train_transform, val_transform = build_transforms(args.image_size)
    train_dataset = WaterDataset(train_records, train_transform)
    val_dataset = WaterDataset(val_records, val_transform)
    sampler: Sampler[int] | None = None
    if args.sampler == "class_sequence":
        sampler = ClassSequenceSampler(
            train_records, args.max_frames_per_sequence, args.seed
        )
        print(
            "class_sequence capacity:",
            {label: sampler.capacity[index] for index, label in enumerate(LABELS)},
            "per_class_budget:",
            sampler.class_budget,
        )
        if len({str(row["sequence_id"]) for row in train_records}) <= 9:
            print("WARNING: sequence_id appears provisional/coarse; review before trusting Group Fold.")
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        sampler=sampler,
        shuffle=sampler is None,
        num_workers=args.workers,
        pin_memory=args.device.startswith("cuda"),
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=args.device.startswith("cuda"),
    )

    device = torch.device(args.device)
    model = timm.create_model(
        args.model,
        pretrained=args.pretrained,
        num_classes=len(LABELS),
    ).to(device)
    criterion = nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    adjustment = None
    if args.logit_adjustment:
        counts = torch.bincount(
            torch.tensor([int(row["label_id"]) for row in train_records]),
            minlength=len(LABELS),
        ).float()
        adjustment = args.logit_adjustment * (counts / counts.sum()).log().to(device)

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    best_selection_score = -1.0
    history = []
    for epoch in range(args.epochs):
        if isinstance(sampler, ClassSequenceSampler):
            sampler.set_epoch(epoch)
        train_loss, _ = run_epoch(model, train_loader, criterion, device, optimizer, adjustment)
        val_loss, matrix = run_epoch(model, val_loader, criterion, device)
        score, per_class = m_iou(matrix)
        metrics = classification_metrics(matrix)
        row = {
            "epoch": epoch + 1,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "mIoU": score,
            "per_class_IoU": dict(zip(LABELS, per_class)),
            **metrics,
            "confusion_matrix": matrix.tolist(),
        }
        history.append(row)
        selection_score = {
            "miou": score,
            "macro_f1": metrics["macro_f1"],
            "accuracy": metrics["accuracy"],
        }[args.selection_metric]
        print(
            f"epoch={epoch + 1:03d} train_loss={train_loss:.4f} "
            f"val_loss={val_loss:.4f} mIoU={score:.4f} "
            f"macro_f1={metrics['macro_f1']:.4f}"
        )
        if selection_score > best_selection_score:
            best_selection_score = selection_score
            torch.save(
                {
                    "model": model.state_dict(),
                    "model_name": args.model,
                    "labels": LABELS,
                    "mIoU": score,
                    "selection_metric": args.selection_metric,
                    "selection_score": selection_score,
                    "epoch": epoch + 1,
                    "args": vars(args),
                },
                out_dir / "best.pt",
            )
        scheduler.step()
    (out_dir / "history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"best_{args.selection_metric}={best_selection_score:.4f} "
        f"checkpoint={out_dir / 'best.pt'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
