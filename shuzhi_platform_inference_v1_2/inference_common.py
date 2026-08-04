"""Offline-only runtime shared by the platform inference entry points."""

from __future__ import annotations

import gc
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import timm
import torch
from PIL import Image, ImageOps
from torch import Tensor, nn
from torchvision import transforms

LABELS: tuple[str, ...] = ("乱采", "乱建", "乱堆", "乱占", "有漂浮物", "正常")
SUPPORTED_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})
ARCHITECTURE = "convnext_tiny"
CHECKPOINT_MODEL_NAME = "convnext_tiny_384"
CHECKPOINT_DATA_IMAGE_SIZE = 384
IMAGE_SIZE = 448
INTERPOLATION = "bicubic"
MEAN: tuple[float, ...] = (0.485, 0.456, 0.406)
STD: tuple[float, ...] = (0.229, 0.224, 0.225)
PADDING_FILL_RGB: tuple[int, ...] = tuple(round(value * 255) for value in MEAN)
SUPPORTED_ENSEMBLE_METHODS = {
    "equal mean of per-fold softmax probabilities followed by argmax",
    "weighted sum of per-fold softmax probabilities followed by argmax",
}


def _float_tuple(values: Sequence[object]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)


def _int_tuple(values: Sequence[object]) -> tuple[int, ...]:
    return tuple(int(value) for value in values)


class ResizePad:
    """Match the training validation transform without cropping the scene."""

    def __init__(self, size: int, fill: tuple[int, int, int]) -> None:
        if size <= 0:
            raise ValueError("ResizePad size must be positive")
        self.size = int(size)
        self.fill = tuple(int(value) for value in fill)

    def __call__(self, image: Image.Image) -> Image.Image:
        width, height = image.size
        if width <= 0 or height <= 0:
            raise ValueError("image has an invalid size")
        scale = self.size / max(width, height)
        resized = image.resize(
            (max(1, round(width * scale)), max(1, round(height * scale))),
            Image.Resampling.BICUBIC,
        )
        canvas = Image.new("RGB", (self.size, self.size), self.fill)
        canvas.paste(
            resized,
            ((self.size - resized.width) // 2, (self.size - resized.height) // 2),
        )
        return canvas


def build_transform(manifest: Mapping[str, Any] | None = None) -> transforms.Compose:
    model = manifest["model"] if manifest is not None else {}
    size = int(model.get("input_size", IMAGE_SIZE))
    mean = _float_tuple(model.get("mean", MEAN))
    std = _float_tuple(model.get("std", STD))
    fill = _int_tuple(model.get("padding_fill_rgb", PADDING_FILL_RGB))
    interpolation = str(model.get("interpolation", INTERPOLATION)).lower()
    if interpolation != INTERPOLATION:
        raise ValueError(f"unsupported interpolation: {interpolation}")
    return transforms.Compose(
        [
            ResizePad(size, fill),
            transforms.ToTensor(),
            transforms.Normalize(mean, std),
        ]
    )


def package_root() -> Path:
    return Path(__file__).resolve().parent


def _validate_relative_package_path(relative: Path, package: Path) -> Path:
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError(f"path must stay inside the package: {relative}")
    resolved = (package / relative).resolve()
    try:
        resolved.relative_to(package)
    except ValueError as error:
        raise ValueError(f"path escapes the package root: {relative}") from error
    return resolved


def load_model_manifest(
    root: Path | None = None,
    *,
    require_checkpoint_files: bool = True,
) -> dict[str, Any]:
    package = (root or package_root()).resolve()
    path = package / "model_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("model_manifest.json must contain an object")
    if tuple(data.get("labels", ())) != LABELS:
        raise ValueError("model manifest labels do not match the official order")

    model = data.get("model")
    if not isinstance(model, dict):
        raise ValueError("model manifest is missing model metadata")
    if model.get("architecture") != ARCHITECTURE:
        raise ValueError("unsupported model architecture in model manifest")
    if model.get("checkpoint_model_name") != CHECKPOINT_MODEL_NAME:
        raise ValueError("unexpected checkpoint model name in model manifest")
    if model.get("freeze_mode") != "last_stage":
        raise ValueError("model manifest freeze mode must be last_stage")
    if int(model.get("input_size", -1)) != IMAGE_SIZE:
        raise ValueError("model manifest input size must be 448")
    if str(model.get("interpolation", "")).lower() != INTERPOLATION:
        raise ValueError("model manifest interpolation must be bicubic")
    if _float_tuple(model.get("mean", ())) != MEAN:
        raise ValueError("model manifest mean does not match the training transform")
    if _float_tuple(model.get("std", ())) != STD:
        raise ValueError("model manifest std does not match the training transform")
    if _int_tuple(model.get("padding_fill_rgb", ())) != PADDING_FILL_RGB:
        raise ValueError("model manifest padding color does not match the training transform")

    checkpoints = data.get("checkpoints")
    ensemble = data.get("ensemble")
    if not isinstance(checkpoints, list) or not checkpoints:
        raise ValueError("model manifest must contain at least one checkpoint")
    if not isinstance(ensemble, dict):
        raise ValueError("model manifest is missing ensemble metadata")
    fold_count = int(ensemble.get("fold_count", -1))
    if fold_count != len(checkpoints):
        raise ValueError("ensemble fold_count must match checkpoint count")
    method = str(ensemble.get("method", ""))
    if method not in SUPPORTED_ENSEMBLE_METHODS:
        raise ValueError(f"unsupported ensemble method: {method}")
    weights_raw = ensemble.get("weights")
    if not isinstance(weights_raw, list) or len(weights_raw) != fold_count:
        raise ValueError("ensemble weights must match checkpoint count")
    weights = [float(value) for value in weights_raw]
    if any(value < 0 for value in weights):
        raise ValueError("ensemble weights must be non-negative")
    if abs(sum(weights) - 1.0) > 1e-8:
        raise ValueError("ensemble weights must sum to one")

    expected_folds = list(range(fold_count))
    actual_folds: list[int] = []
    for spec in checkpoints:
        if not isinstance(spec, dict):
            raise ValueError("each checkpoint specification must be an object")
        fold = int(spec.get("fold", -1))
        actual_folds.append(fold)
        relative = Path(str(spec.get("path", "")))
        resolved = _validate_relative_package_path(relative, package)
        if require_checkpoint_files and not resolved.is_file():
            raise FileNotFoundError(f"missing packaged checkpoint: {relative}")
        digest = str(spec.get("sha256", "")).lower()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"invalid checkpoint sha256 for fold {fold}")
    if actual_folds != expected_folds:
        raise ValueError(f"checkpoint folds must be consecutive and ordered: {expected_folds}")
    return data


def ensemble_weights(manifest: Mapping[str, Any]) -> tuple[float, ...]:
    return tuple(float(value) for value in manifest["ensemble"]["weights"])


def checkpoint_specs(manifest: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(manifest["checkpoints"])


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_payload(path: Path) -> Mapping[str, Any]:
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:  # PyTorch versions before the weights_only argument.
        payload = torch.load(path, map_location="cpu")
    if not isinstance(payload, Mapping):
        raise ValueError(f"checkpoint is not a mapping: {path.name}")
    return payload


def build_offline_model() -> nn.Module:
    # pretrained=False is intentional: the package contains the complete model
    # state and must never consult a Hub, cache, or network.
    return timm.create_model(ARCHITECTURE, pretrained=False, num_classes=len(LABELS))


def validate_checkpoint_payload(
    payload: Mapping[str, Any],
    manifest: Mapping[str, Any],
    spec: Mapping[str, Any],
    path: Path,
) -> Mapping[str, Any]:
    fold = int(spec["fold"])
    if tuple(payload.get("labels", ())) != LABELS:
        raise ValueError(f"checkpoint labels do not match official order: {path.name}")
    args = payload.get("args")
    if not isinstance(args, Mapping):
        raise ValueError(f"checkpoint args metadata is missing: {path.name}")
    if args.get("model") != CHECKPOINT_MODEL_NAME:
        raise ValueError(f"checkpoint architecture metadata is unexpected: {path.name}")
    if int(args.get("fold", -1)) != fold:
        raise ValueError(f"checkpoint fold metadata is unexpected: {path.name}")
    if args.get("freeze_mode") != manifest["model"]["freeze_mode"]:
        raise ValueError(f"checkpoint freeze mode is unexpected: {path.name}")
    if int(args.get("image_size", -1)) != int(manifest["model"]["input_size"]):
        raise ValueError(f"checkpoint image size is unexpected: {path.name}")
    if payload.get("model_name") != CHECKPOINT_MODEL_NAME:
        raise ValueError(f"checkpoint model_name is unexpected: {path.name}")
    resolved_name = str(payload.get("resolved_model_name", ""))
    if ARCHITECTURE not in resolved_name:
        raise ValueError(f"checkpoint resolved architecture is unexpected: {path.name}")
    data_config = payload.get("data_config")
    if not isinstance(data_config, Mapping):
        raise ValueError(f"checkpoint data_config is missing: {path.name}")
    checkpoint_data_size = tuple(data_config.get("input_size", ()))
    if checkpoint_data_size != (
        3,
        CHECKPOINT_DATA_IMAGE_SIZE,
        CHECKPOINT_DATA_IMAGE_SIZE,
    ):
        raise ValueError(f"checkpoint model data_config input size is unexpected: {path.name}")
    if str(data_config.get("interpolation", "")).lower() != str(
        manifest["model"]["interpolation"]
    ).lower():
        raise ValueError(f"checkpoint interpolation metadata is unexpected: {path.name}")
    if _float_tuple(data_config.get("mean", ())) != _float_tuple(manifest["model"]["mean"]):
        raise ValueError(f"checkpoint mean metadata is unexpected: {path.name}")
    if _float_tuple(data_config.get("std", ())) != _float_tuple(manifest["model"]["std"]):
        raise ValueError(f"checkpoint std metadata is unexpected: {path.name}")
    state = payload.get("model")
    if not isinstance(state, Mapping):
        raise ValueError(f"checkpoint model state is missing: {path.name}")
    return state


def load_model_for_checkpoint(
    root: Path,
    manifest: Mapping[str, Any],
    spec: Mapping[str, Any],
    device: torch.device,
) -> nn.Module:
    package = root.resolve()
    relative = Path(str(spec["path"]))
    path = _validate_relative_package_path(relative, package)
    fold = int(spec["fold"])
    expected_hash = str(spec["sha256"]).lower()
    actual_hash = sha256_file(path)
    if actual_hash != expected_hash:
        raise ValueError(
            f"checkpoint SHA256 mismatch for fold {fold}: "
            f"expected {expected_hash}, got {actual_hash}"
        )
    payload = load_payload(path)
    state = validate_checkpoint_payload(payload, manifest, spec, path)
    model = build_offline_model()
    try:
        incompatible = model.load_state_dict(state, strict=True)
    except RuntimeError as error:
        raise ValueError(f"strict state_dict load failed for {path.name}: {error}") from error
    if incompatible.missing_keys or incompatible.unexpected_keys:
        raise ValueError(f"strict state_dict mismatch for {path.name}")
    del payload, state
    return model.to(device).eval()


def load_model_for_fold(
    root: Path, manifest: Mapping[str, Any], fold: int, device: torch.device
) -> nn.Module:
    specs = checkpoint_specs(manifest)
    if fold < 0 or fold >= len(specs):
        raise IndexError(f"fold index is out of range: {fold}")
    return load_model_for_checkpoint(root, manifest, specs[fold], device)


def scan_input_images(input_dir: Path) -> list[Path]:
    root = input_dir.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"input directory does not exist: {root}")
    paths = sorted(
        [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES],
        key=lambda path: (path.name.casefold(), str(path)),
    )
    seen: dict[str, Path] = {}
    for path in paths:
        key = path.name.casefold()
        if key in seen:
            raise ValueError(
                f"duplicate filename across input directories: {seen[key]} and {path}"
            )
        seen[key] = path
    if not paths:
        raise ValueError("input directory contains no JPG/JPEG/PNG images")
    return paths


def read_image(path: Path, transform: transforms.Compose) -> tuple[Tensor, int, int]:
    with Image.open(path) as source:
        width, height = source.size
        image = ImageOps.exif_transpose(source).convert("RGB")
        tensor = transform(image)
    return tensor, int(width), int(height)


def validate_probabilities(probabilities: Tensor) -> None:
    if probabilities.ndim != 2 or probabilities.shape[1] != len(LABELS):
        raise ValueError(f"invalid probability shape: {tuple(probabilities.shape)}")
    if not torch.isfinite(probabilities).all():
        raise ValueError("probabilities contain NaN or infinity")
    if (probabilities < 0).any() or (probabilities > 1).any():
        raise ValueError("probabilities are outside [0, 1]")
    expected = torch.ones(len(probabilities), dtype=probabilities.dtype)
    if not torch.allclose(probabilities.sum(1).cpu(), expected, atol=1e-5):
        raise ValueError("probabilities do not sum to one")


def release_model(model: nn.Module, device: torch.device) -> None:
    del model
    gc.collect()
    if device.type == "cuda":
        torch.cuda.empty_cache()


def atomic_write_text(path: Path, content: str) -> None:
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
