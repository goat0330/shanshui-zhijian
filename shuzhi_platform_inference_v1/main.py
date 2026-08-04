"""Platform entry point for arbitrary-count, offline six-class inference."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from inference_common import (
    LABELS,
    atomic_write_text,
    build_transform,
    load_model_for_fold,
    load_model_manifest,
    package_root,
    read_image,
    release_model,
    scan_input_images,
    validate_probabilities,
)


class ImageDataset(Dataset[tuple[torch.Tensor, str]]):
    def __init__(self, paths: list[Path], transform) -> None:
        self.paths = paths
        self.transform = transform

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, str]:
        tensor, _, _ = read_image(self.paths[index], self.transform)
        return tensor, self.paths[index].name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("submission.json"))
    parser.add_argument("--probability-output", type=Path, default=None)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    return parser.parse_args()


def select_device(requested: str) -> torch.device:
    if requested == "auto":
        requested = "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--device cuda was requested but CUDA is unavailable")
    return torch.device(requested)


def write_probability_csv(path: Path, names: list[str], dimensions: list[tuple[int, int]], probabilities: torch.Tensor) -> None:
    rows: list[dict[str, object]] = []
    for name, (width, height), values in zip(names, dimensions, probabilities.tolist()):
        row: dict[str, object] = {"filename": name, "width": str(width), "height": str(height)}
        row.update({f"prob_{label}": f"{value:.10f}" for label, value in zip(LABELS, values)})
        rows.append(row)
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be positive")
    root = package_root()
    manifest = load_model_manifest(root)
    paths = scan_input_images(args.input_dir)
    dimensions: list[tuple[int, int]] = []
    transform = build_transform()
    for path in paths:
        with Image.open(path) as image:
            dimensions.append((int(image.size[0]), int(image.size[1])))
    names = [path.name for path in paths]
    device = select_device(args.device)
    loader = DataLoader(
        ImageDataset(paths, transform),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )
    fold_probabilities: list[torch.Tensor] = []
    for fold in range(4):
        model = load_model_for_fold(root, manifest, fold, device)
        batches: list[torch.Tensor] = []
        names_seen: list[str] = []
        with torch.inference_mode():
            for images, batch_names in loader:
                logits = model(images.to(device, non_blocking=device.type == "cuda"))
                probabilities = logits.float().softmax(dim=1).cpu()
                validate_probabilities(probabilities)
                batches.append(probabilities)
                names_seen.extend(batch_names)
        if names_seen != names:
            raise RuntimeError(f"fold {fold} changed deterministic input order")
        fold_probabilities.append(torch.cat(batches, dim=0))
        release_model(model, device)
        print(json.dumps({"fold": fold, "device": str(device), "count": len(paths)}, ensure_ascii=False))
    probabilities = torch.stack(fold_probabilities, dim=0).mean(dim=0)
    validate_probabilities(probabilities)
    labels = [LABELS[index] for index in probabilities.argmax(dim=1).tolist()]
    output_rows = [
        {
            "filename": str(name),
            "width": str(width),
            "height": str(height),
            "label": str(label),
        }
        for name, (width, height), label in zip(names, dimensions, labels)
    ]
    atomic_write_text(args.output, json.dumps(output_rows, ensure_ascii=False, indent=4) + "\n")
    if args.probability_output is not None:
        write_probability_csv(args.probability_output, names, dimensions, probabilities)
    print(json.dumps({"output": str(args.output.expanduser().resolve()), "count": len(output_rows), "device": str(device)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
