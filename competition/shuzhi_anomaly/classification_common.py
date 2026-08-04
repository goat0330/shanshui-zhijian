"""Shared utilities for the six-class water anomaly classification task.

Designed to be copied into ``competition/shuzhi_anomaly`` and imported by the
training / feature-extraction scripts in this patch.
"""
from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import timm
import torch
from PIL import Image, ImageOps
from torch import Tensor, nn
from torchvision import transforms
from torchvision.transforms import InterpolationMode

LABELS: tuple[str, ...] = ("乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常")
LABEL_TO_ID = {label: index for index, label in enumerate(LABELS)}
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png"}

MODEL_ALIASES = {
    # Use the Hub path because some local timm registries do not expose the
    # full tagged model name even though the official checkpoint is available.
    "convnext_tiny_384": "hf-hub:timm/convnext_tiny.fb_in22k_ft_in1k_384",
    "convnext_tiny_1k": "convnext_tiny",
    "efficientnetv2_s": "efficientnetv2_rw_s.ra2_in1k",
}


@dataclass(frozen=True)
class ModelBundle:
    model: nn.Module
    resolved_name: str
    data_config: dict[str, object]


def json_ready(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def resolve_model_name(name: str) -> str:
    return MODEL_ALIASES.get(name, name)


def build_model(
    model_name: str,
    *,
    num_classes: int,
    pretrained: bool,
    cache_dir: Path | None = None,
    checkpoint_path: Path | None = None,
) -> ModelBundle:
    resolved_name = resolve_model_name(model_name)
    kwargs: dict[str, object] = {
        "pretrained": pretrained,
        "num_classes": num_classes,
    }
    if cache_dir is not None:
        kwargs["cache_dir"] = str(cache_dir)
    model = timm.create_model(resolved_name, **kwargs)
    if checkpoint_path is not None:
        try:
            checkpoint = torch.load(
                checkpoint_path, map_location="cpu", weights_only=False
            )
        except TypeError:  # PyTorch < 2.6
            checkpoint = torch.load(checkpoint_path, map_location="cpu")
        state_dict = checkpoint.get("model", checkpoint)
        missing, unexpected = model.load_state_dict(state_dict, strict=False)
        if missing:
            print(f"WARNING: missing checkpoint keys ({len(missing)}): {missing[:8]}")
        if unexpected:
            print(f"WARNING: unexpected checkpoint keys ({len(unexpected)}): {unexpected[:8]}")
    data_config = timm.data.resolve_model_data_config(model)
    return ModelBundle(model=model, resolved_name=resolved_name, data_config=data_config)


def classifier_modules(model: nn.Module) -> list[nn.Module]:
    modules: list[nn.Module] = []
    try:
        classifier = model.get_classifier()
        if isinstance(classifier, nn.Module):
            modules.append(classifier)
    except (AttributeError, TypeError):
        pass
    for name in ("head", "classifier", "fc"):
        module = getattr(model, name, None)
        if isinstance(module, nn.Module) and module not in modules:
            modules.append(module)
    return modules


def _unfreeze_module(module: nn.Module | None) -> None:
    if module is None:
        return
    for parameter in module.parameters():
        parameter.requires_grad = True


def configure_trainable_layers(model: nn.Module, freeze_mode: str) -> dict[str, int]:
    """Configure trainable parameters for head / staged transfer learning.

    Supported modes:
    - ``full``: train everything.
    - ``head``: only the classification head.
    - ``last_stage``: head plus final feature stage/block.
    - ``last2_stages``: head plus final two feature stages/blocks.
    """
    if freeze_mode not in {"full", "head", "last_stage", "last2_stages"}:
        raise ValueError(f"unsupported freeze_mode={freeze_mode!r}")

    for parameter in model.parameters():
        parameter.requires_grad = freeze_mode == "full"

    if freeze_mode != "full":
        for module in classifier_modules(model):
            _unfreeze_module(module)
        # ConvNeXt commonly has a final norm outside stages.
        _unfreeze_module(getattr(model, "norm_pre", None))
        _unfreeze_module(getattr(model, "norm", None))

    count = 0
    if freeze_mode == "last_stage":
        count = 1
    elif freeze_mode == "last2_stages":
        count = 2

    if count:
        stage_container = None
        for candidate in ("stages", "blocks", "layers"):
            container = getattr(model, candidate, None)
            if container is not None and hasattr(container, "__len__"):
                stage_container = container
                break
        if stage_container is None:
            children = [module for _, module in model.named_children()]
            if not children:
                raise RuntimeError("cannot identify feature stages for staged unfreezing")
            for module in children[-count:]:
                _unfreeze_module(module)
        else:
            for module in list(stage_container)[-count:]:
                _unfreeze_module(module)

    total = sum(parameter.numel() for parameter in model.parameters())
    trainable = sum(
        parameter.numel() for parameter in model.parameters() if parameter.requires_grad
    )
    return {"total": total, "trainable": trainable}


def optimizer_param_groups(
    model: nn.Module,
    *,
    backbone_lr: float,
    head_lr: float,
    weight_decay: float,
) -> list[dict[str, object]]:
    head_ids = {
        id(parameter)
        for module in classifier_modules(model)
        for parameter in module.parameters()
        if parameter.requires_grad
    }
    head_parameters: list[nn.Parameter] = []
    backbone_parameters: list[nn.Parameter] = []
    for parameter in model.parameters():
        if not parameter.requires_grad:
            continue
        if id(parameter) in head_ids:
            head_parameters.append(parameter)
        else:
            backbone_parameters.append(parameter)

    groups: list[dict[str, object]] = []
    if backbone_parameters:
        groups.append(
            {
                "params": backbone_parameters,
                "lr": backbone_lr,
                "weight_decay": weight_decay,
                "group_name": "backbone",
            }
        )
    if head_parameters:
        groups.append(
            {
                "params": head_parameters,
                "lr": head_lr,
                "weight_decay": weight_decay,
                "group_name": "head",
            }
        )
    if not groups:
        raise RuntimeError("no trainable parameters after freeze configuration")
    return groups


def load_json_records(path: Path) -> list[dict[str, object]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError(f"expected a list of labeled records: {path}")
    result: list[dict[str, object]] = []
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
    return {row["filename"]: row for row in rows if row.get("filename")}


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
    for path in source_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            result[path.name].append(path)
    return result


def resolve_labeled_records(
    records: Iterable[dict[str, object]],
    source_root: Path,
    manifest: dict[str, dict[str, str]],
    images: dict[str, list[Path]],
) -> list[dict[str, object]]:
    resolved: list[dict[str, object]] = []
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
        resolved.append(
            {
                "filename": filename,
                "path": path,
                "label": str(record["label"]),
                "label_id": LABEL_TO_ID[str(record["label"])],
                "sequence_id": manifest_row.get("sequence_id")
                or f"filename_{filename}",
            }
        )
    return resolved


def build_cv_records(
    *,
    source_root: Path,
    train_json: Path,
    manifest_path: Path,
    train_index_path: Path | None,
    cv_manifest_path: Path,
    fold: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, dict[str, str]]]:
    manifest = load_manifest(manifest_path)
    images = discover_images(source_root)
    label_by_filename = {
        str(record["filename"]): str(record["label"])
        for record in load_json_records(train_json)
    }
    source_records = (
        load_train_index(train_index_path)
        if train_index_path is not None
        else load_json_records(train_json)
    )
    for record in source_records:
        filename = str(record["filename"])
        if filename in label_by_filename:
            record["label"] = label_by_filename[filename]

    with cv_manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        cv_rows = list(csv.DictReader(handle))
    cv_map = {row["filename"]: row for row in cv_rows}
    if not cv_map:
        raise ValueError(f"internal CV manifest is empty: {cv_manifest_path}")

    train_source = [
        record
        for record in source_records
        if str(record["filename"]) in cv_map
        and int(cv_map[str(record["filename"])]["fold"]) != fold
    ]
    val_source = [
        record
        for record in load_json_records(train_json)
        if str(record["filename"]) in cv_map
        and int(cv_map[str(record["filename"])]["fold"]) == fold
    ]
    train_records = resolve_labeled_records(train_source, source_root, manifest, images)
    val_records = resolve_labeled_records(val_source, source_root, manifest, images)
    if not train_records or not val_records:
        raise ValueError(
            f"empty split for fold={fold}: train={len(train_records)}, val={len(val_records)}"
        )
    return train_records, val_records, cv_map


def pil_interpolation(value: object) -> Image.Resampling:
    name = str(value).lower()
    return {
        "bicubic": Image.Resampling.BICUBIC,
        "bilinear": Image.Resampling.BILINEAR,
        "nearest": Image.Resampling.NEAREST,
        "lanczos": Image.Resampling.LANCZOS,
    }.get(name, Image.Resampling.BICUBIC)


class ResizePad:
    """Preserve the entire scene while matching a square model input."""

    def __init__(
        self,
        size: int,
        *,
        interpolation: Image.Resampling,
        mean: Sequence[float],
    ):
        self.size = size
        self.interpolation = interpolation
        self.fill = tuple(max(0, min(255, round(float(v) * 255))) for v in mean)

    def __call__(self, image: Image.Image) -> Image.Image:
        width, height = image.size
        scale = self.size / max(width, height)
        resized = image.resize(
            (max(1, round(width * scale)), max(1, round(height * scale))),
            self.interpolation,
        )
        canvas = Image.new("RGB", (self.size, self.size), self.fill)
        canvas.paste(
            resized,
            ((self.size - resized.width) // 2, (self.size - resized.height) // 2),
        )
        return canvas


def build_transforms(
    *,
    image_size: int,
    data_config: dict[str, object],
    train: bool,
) -> transforms.Compose:
    mean = tuple(float(v) for v in data_config.get("mean", (0.485, 0.456, 0.406)))
    std = tuple(float(v) for v in data_config.get("std", (0.229, 0.224, 0.225)))
    operations: list[object] = [
        ResizePad(
            image_size,
            interpolation=pil_interpolation(data_config.get("interpolation", "bicubic")),
            mean=mean,
        )
    ]
    if train:
        operations.extend(
            [
                transforms.RandomHorizontalFlip(p=0.5),
                transforms.ColorJitter(
                    brightness=0.12,
                    contrast=0.12,
                    saturation=0.12,
                    hue=0.02,
                ),
            ]
        )
    operations.extend([transforms.ToTensor(), transforms.Normalize(mean, std)])
    return transforms.Compose(operations)


class ClassificationDataset(torch.utils.data.Dataset[tuple[Tensor, int, str]]):
    def __init__(self, records: list[dict[str, object]], transform: transforms.Compose):
        self.records = records
        self.transform = transform

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[Tensor, int, str]:
        record = self.records[index]
        with Image.open(Path(record["path"])) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        return self.transform(image), int(record["label_id"]), str(record["filename"])


def confusion_matrix_from_ids(
    targets: Sequence[int] | Tensor,
    predictions: Sequence[int] | Tensor,
) -> Tensor:
    target_tensor = torch.as_tensor(targets, dtype=torch.int64)
    prediction_tensor = torch.as_tensor(predictions, dtype=torch.int64)
    flat = target_tensor * len(LABELS) + prediction_tensor
    return torch.bincount(flat, minlength=len(LABELS) ** 2).reshape(
        len(LABELS), len(LABELS)
    )


def metrics_from_confusion(matrix: Tensor) -> dict[str, object]:
    matrix = matrix.to(torch.float64)
    true_positive = matrix.diag()
    support = matrix.sum(dim=1)
    predicted = matrix.sum(dim=0)
    precision = true_positive / predicted.clamp_min(1.0)
    recall = true_positive / support.clamp_min(1.0)
    f1 = 2 * precision * recall / (precision + recall).clamp_min(1e-12)
    denominator = support + predicted - true_positive
    iou = torch.where(denominator > 0, true_positive / denominator, torch.nan)
    total = matrix.sum().item()
    return {
        "accuracy": float(true_positive.sum().item() / total) if total else 0.0,
        "weighted_f1": float((f1 * support / support.sum().clamp_min(1.0)).sum().item()),
        "macro_f1": float(f1.mean().item()),
        "balanced_accuracy": float(recall.mean().item()),
        "mIoU": float(torch.nanmean(iou).item()),
        "per_class_precision": dict(zip(LABELS, precision.tolist())),
        "per_class_recall": dict(zip(LABELS, recall.tolist())),
        "per_class_f1": dict(zip(LABELS, f1.tolist())),
        "per_class_iou": dict(
            zip(LABELS, [None if math.isnan(v) else v for v in iou.tolist()])
        ),
        "support": dict(zip(LABELS, support.to(torch.int64).tolist())),
        "prediction_distribution": dict(
            zip(LABELS, predicted.to(torch.int64).tolist())
        ),
        "confusion_matrix": matrix.to(torch.int64).tolist(),
    }


def write_prediction_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "filename",
        "fold",
        "true_label_id",
        "true_label",
        "pred_label_id",
        "pred_label",
        *[f"logit_{label}" for label in LABELS],
        *[f"prob_{label}" for label in LABELS],
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
