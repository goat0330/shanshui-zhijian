"""Validate dependencies, metadata, hashes, and the exact production load path."""

from __future__ import annotations

import argparse
import json
import sys

import timm
import torch
import torchvision
from PIL import __version__ as pillow_version

from inference_common import (
    checkpoint_specs,
    load_model_for_checkpoint,
    load_model_manifest,
    package_root,
    release_model,
    sha256_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cpu")
    return parser.parse_args()


def select_device(requested: str) -> torch.device:
    if requested == "auto":
        requested = "cuda" if torch.cuda.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA validation was requested but CUDA is unavailable")
    return torch.device(requested)


def main() -> int:
    args = parse_args()
    device = select_device(args.device)
    root = package_root()
    manifest = load_model_manifest(root)
    checkpoint_results = []

    # Reuse the exact production loader. This validates SHA256, labels, fold,
    # model metadata, freeze mode, preprocessing metadata and strict state load.
    for spec in checkpoint_specs(manifest):
        path = root / str(spec["path"])
        digest = sha256_file(path)
        model = load_model_for_checkpoint(root, manifest, spec, device)
        checkpoint_results.append(
            {
                "fold": int(spec["fold"]),
                "path": str(spec["path"]),
                "sha256": digest,
                "metadata": "strict_ok",
                "state_dict": "strict_ok",
            }
        )
        release_model(model, device)

    print(
        json.dumps(
            {
                "python": sys.version.split()[0],
                "torch": torch.__version__,
                "torchvision": torchvision.__version__,
                "timm": timm.__version__,
                "pillow": pillow_version,
                "device": str(device),
                "cuda_available": torch.cuda.is_available(),
                "labels": manifest["labels"],
                "ensemble_weights": manifest["ensemble"]["weights"],
                "checkpoints": checkpoint_results,
                "status": "ok",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
