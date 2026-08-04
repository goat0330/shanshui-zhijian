"""Validate package dependencies, metadata, hashes, and strict model loading."""

from __future__ import annotations

import json
import sys

import torch

from inference_common import build_offline_model, load_model_manifest, load_payload, package_root, sha256_file


def main() -> int:
    root = package_root()
    manifest = load_model_manifest(root)
    checkpoint_results = []
    for spec in manifest["checkpoints"]:
        path = root / spec["path"]
        digest = sha256_file(path)
        if digest != spec["sha256"]:
            raise RuntimeError(f"SHA256 mismatch: {path.name}")
        payload = load_payload(path)
        model = build_offline_model()
        incompatible = model.load_state_dict(payload["model"], strict=True)
        if incompatible.missing_keys or incompatible.unexpected_keys:
            raise RuntimeError(f"state_dict mismatch: {path.name}")
        checkpoint_results.append({"path": str(spec["path"]), "sha256": digest, "state_dict": "strict_ok"})
        del model, payload
    print(json.dumps({
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "labels": manifest["labels"],
        "checkpoints": checkpoint_results,
        "status": "ok",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
