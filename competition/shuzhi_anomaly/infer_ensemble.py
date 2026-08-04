"""Run equal-weight four-fold probability averaging on the frozen test set."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import torch
from PIL import Image, ImageOps
from torch import Tensor
from torch.utils.data import DataLoader, Dataset

from classification_common import LABELS, build_model, build_transforms


EXPECTED_COUNT = 695
FOLD_COUNT = 4
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_DIR = PROJECT_ROOT / "competition" / "shuzhi_anomaly"
DEFAULT_MANIFEST = PROJECT_DIR / "generated" / "test_manifest_v1.csv"
DEFAULT_SOURCE_ROOT = PROJECT_ROOT / "水域综合异常识别_训练集+验证集"
DEFAULT_OUTPUT = PROJECT_DIR / "generated" / "submission_ensemble_last_stage.json"
DEFAULT_CACHE_DIR = PROJECT_DIR / "weights" / "timm"
DEFAULT_CHECKPOINTS = tuple(
    PROJECT_DIR / "runs" / "repair_v2" / f"fold{i}_last_stage" / "best.pt"
    for i in range(FOLD_COUNT)
)


class TestDataset(Dataset):
    def __init__(self, rows: list[dict[str, str]], source_root: Path, transform) -> None:
        self.rows = rows
        self.source_root = source_root.resolve()
        self.transform = transform

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[Tensor, str]:
        row = self.rows[index]
        path = self.source_root / Path(row["relative_path"])
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
        return self.transform(image), row["filename"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--checkpoint", action="append", nargs="+", dest="checkpoints", metavar="PATH"
    )
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.resolve().open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_COUNT:
        raise ValueError(f"expected {EXPECTED_COUNT} test rows, found {len(rows)}")
    required = {"filename", "relative_path", "width", "height"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"manifest must contain {sorted(required)}")
    filenames = [row["filename"] for row in rows]
    if len(set(filenames)) != len(filenames):
        raise ValueError("manifest contains duplicate filenames")
    for index, row in enumerate(rows, 1):
        if int(row["width"]) <= 0 or int(row["height"]) <= 0:
            raise ValueError(f"invalid dimensions for {row['filename']}")
        if "submission_order" in row and int(row["submission_order"]) != index:
            raise ValueError("manifest submission_order is not consecutive")
    return rows


def resolve_records(rows: list[dict[str, str]], source_root: Path) -> None:
    root = source_root.resolve()
    for row in rows:
        relative = Path(row["relative_path"])
        if relative.is_absolute():
            raise ValueError("manifest relative_path must be relative")
        path = root / relative
        if not path.is_file() or path.name != row["filename"]:
            raise FileNotFoundError(f"test image does not match manifest: {path}")


def checkpoint_paths(args: argparse.Namespace) -> list[Path]:
    raw = [item for group in args.checkpoints for item in group] if args.checkpoints else list(DEFAULT_CHECKPOINTS)
    if len(raw) != FOLD_COUNT:
        raise ValueError(f"exactly {FOLD_COUNT} checkpoints are required, found {len(raw)}")
    paths = [Path(item).expanduser().resolve() for item in raw]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing checkpoint: " + ", ".join(missing))
    return paths


def load_checkpoint(path: Path) -> tuple[str, int, dict, dict]:
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    if not isinstance(payload, dict) or tuple(payload.get("labels", ())) != tuple(LABELS):
        raise ValueError(f"checkpoint labels are not the official six classes: {path}")
    args = payload.get("args", {})
    if not isinstance(args, dict) or args.get("freeze_mode") != "last_stage":
        raise ValueError(f"checkpoint is not a last-stage checkpoint: {path}")
    model_name = payload.get("model_name") or payload.get("resolved_model_name") or args.get("model")
    state = payload.get("model")
    if not isinstance(model_name, str) or not isinstance(state, dict):
        raise ValueError(f"checkpoint metadata is incomplete: {path}")
    size = int(args.get("image_size", 384))
    config = payload.get("data_config", {})
    return model_name, size, config if isinstance(config, dict) else {}, state


def validate_probabilities(probabilities: Tensor) -> None:
    if probabilities.ndim != 2 or probabilities.shape[1] != len(LABELS):
        raise ValueError(f"invalid probability shape: {tuple(probabilities.shape)}")
    if not torch.isfinite(probabilities).all() or (probabilities < 0).any() or (probabilities > 1).any():
        raise ValueError("probabilities contain invalid values")
    if not torch.allclose(probabilities.sum(1), torch.ones(len(probabilities)), atol=1e-5):
        raise ValueError("probabilities do not sum to one")


def main() -> int:
    args = parse_args()
    if tuple(LABELS) != ("乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常"):
        raise RuntimeError("classification_common.LABELS does not match official labels")
    if args.batch_size <= 0 or args.workers < 0:
        raise ValueError("batch-size must be positive and workers must be non-negative")
    rows = read_manifest(args.manifest)
    resolve_records(rows, args.source_root)
    paths = checkpoint_paths(args)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "test_count": len(rows), "checkpoints": [str(p) for p in paths]}, ensure_ascii=False, indent=2))
        return 0

    device = torch.device(args.device)
    models: list[torch.nn.Module] = []
    transform = None
    expected_model = None
    expected_size = None
    for path in paths:
        model_name, image_size, data_config, state = load_checkpoint(path)
        if expected_model is None:
            expected_model, expected_size = model_name, image_size
            transform = build_transforms(image_size=image_size, data_config=data_config, train=False)
        elif (model_name, image_size) != (expected_model, expected_size):
            raise ValueError("checkpoint model names or image sizes do not match")
        bundle = build_model(model_name, num_classes=len(LABELS), pretrained=False, cache_dir=args.cache_dir.resolve())
        missing, unexpected = bundle.model.load_state_dict(state, strict=False)
        if missing or unexpected:
            raise ValueError(f"state_dict mismatch for {path}: missing={missing[:4]}, unexpected={unexpected[:4]}")
        models.append(bundle.model.to(device).eval())

    loader = DataLoader(TestDataset(rows, args.source_root, transform), batch_size=args.batch_size, shuffle=False, num_workers=args.workers, pin_memory=device.type == "cuda")
    expected_names = [row["filename"] for row in rows]
    fold_probabilities: list[Tensor] = []
    for fold, model in enumerate(models):
        names: list[str] = []
        batches: list[Tensor] = []
        with torch.inference_mode():
            for images, filenames in loader:
                logits = model(images.to(device, non_blocking=True))
                probabilities = logits.float().softmax(1).cpu()
                validate_probabilities(probabilities)
                batches.append(probabilities)
                names.extend(filenames)
        if names != expected_names:
            raise ValueError(f"fold {fold} changed manifest order")
        fold_probabilities.append(torch.cat(batches))
    mean_probabilities = torch.stack(fold_probabilities).mean(0)
    validate_probabilities(mean_probabilities)
    labels = [LABELS[index] for index in mean_probabilities.argmax(1).tolist()]
    output_rows = [
        {
            "filename": str(row["filename"]),
            "width": str(row["width"]),
            "height": str(row["height"]),
            "label": str(label),
        }
        for row, label in zip(rows, labels)
    ]
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(json.dumps(output_rows, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "count": len(output_rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
