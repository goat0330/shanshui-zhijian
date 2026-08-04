"""Dump equal-weight 4-fold mean test probabilities to CSV for a candidate."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import torch
from PIL import Image, ImageOps
from torch.utils.data import DataLoader, Dataset

from classification_common import LABELS, build_model, build_transforms

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_DIR = PROJECT_ROOT / "competition" / "shuzhi_anomaly"
DEFAULT_MANIFEST = PROJECT_DIR / "generated" / "test_manifest_v1.csv"
DEFAULT_SOURCE_ROOT = PROJECT_ROOT / "水域综合异常识别_训练集+验证集"
DEFAULT_CACHE_DIR = PROJECT_DIR / "weights" / "timm"
FOLD_COUNT = 4


class TestDataset(Dataset):
    def __init__(self, rows, source_root, transform):
        self.rows = rows
        self.source_root = source_root.resolve()
        self.transform = transform

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        path = self.source_root / Path(row["relative_path"])
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
        return self.transform(image), row["filename"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", action="append", nargs="+", dest="checkpoints", metavar="PATH")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    with args.manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    raw = [item for group in args.checkpoints for item in group]
    assert len(raw) == FOLD_COUNT, f"need {FOLD_COUNT} checkpoints"

    device = torch.device(args.device)
    models = []
    transform = None
    expected = None
    for path in raw:
        payload = torch.load(path, map_location="cpu", weights_only=False)
        model_name = payload["model_name"] or payload["resolved_model_name"]
        size = int(payload["args"].get("image_size", 384))
        data_config = payload.get("data_config", {})
        if expected is None:
            expected = (model_name, size)
            transform = build_transforms(image_size=size, data_config=data_config, train=False)
        assert (model_name, size) == expected
        bundle = build_model(model_name, num_classes=len(LABELS), pretrained=False, cache_dir=args.cache_dir.resolve())
        missing, unexpected = bundle.model.load_state_dict(payload["model"], strict=False)
        assert not missing and not unexpected
        models.append(bundle.model.to(device).eval())

    loader = DataLoader(TestDataset(rows, args.source_root, transform), batch_size=args.batch_size, shuffle=False, num_workers=args.workers, pin_memory=device.type == "cuda")
    names = [row["filename"] for row in rows]
    folds = []
    for model in models:
        batches = []
        with torch.inference_mode():
            for images, fnames in loader:
                logits = model(images.to(device, non_blocking=True))
                batches.append(logits.float().softmax(1).cpu())
        folds.append(torch.cat(batches))
    mean = torch.stack(folds).mean(0)
    assert names == [row["filename"] for row in rows]

    out = args.output.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["filename", *[f"prob_{label}" for label in LABELS], "pred_label"])
        for name, probs in zip(names, mean.tolist()):
            pred = LABELS[int(torch.argmax(torch.tensor(probs)))]
            writer.writerow([name, *[f"{v:.9f}" for v in probs], pred])
    print(f"wrote {len(names)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
