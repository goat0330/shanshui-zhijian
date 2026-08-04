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
IMAGE_SIZE = 384
INTERPOLATION = "bicubic"
MEAN: tuple[float, ...] = (0.485, 0.456, 0.406)
STD: tuple[float, ...] = (0.229, 0.224, 0.225)
PADDING_FILL_RGB: tuple[int, ...] = tuple(round(value * 255) for value in MEAN)


class ResizePad:
    """Match the training validation transform without cropping the scene."""

    def __init__(self, size: int) -> None:
        self.size = size
        self.fill = PADDING_FILL_RGB

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


def build_transform() -> transforms.Compose:
    return transforms.Compose(
        [
            ResizePad(IMAGE_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(MEAN, STD),
        ]
    )


def package_root() -> Path:
    return Path(__file__).resolve().parent


def load_model_manifest(root: Path | None = None) -> dict[str, Any]:
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
        raise ValueError("model manifest input size must be 384")
    if str(model.get("interpolation", "")).lower() != INTERPOLATION:
        raise ValueError("model manifest interpolation must be bicubic")
    if tuple(float(value) for value in model.get("mean", ())) != MEAN:
        raise ValueError("model manifest mean does not match the training transform")
    if tuple(float(value) for value in model.get("std", ())) != STD:
        raise ValueError("model manifest std does not match the training transform")
    if tuple(int(value) for value in model.get("padding_fill_rgb", ())) != PADDING_FILL_RGB:
        raise ValueError("model manifest padding color does not match the training transform")
    checkpoints = data.get("checkpoints")
    if not isinstance(checkpoints, list) or len(checkpoints) != 4:
        raise ValueError("model manifest must contain exactly four checkpoints")
    for expected_fold, spec in enumerate(checkpoints):
        if not isinstance(spec, dict) or int(spec.get("fold", -1)) != expected_fold:
            raise ValueError("checkpoint folds must be 0, 1, 2, 3 in order")
        relative = Path(str(spec.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("checkpoint path must stay inside the package")
        if not (package / relative).is_file():
            raise FileNotFoundError(f"missing packaged checkpoint: {relative}")
        digest = str(spec.get("sha256", "")).lower()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"invalid checkpoint sha256 for fold {expected_fold}")
    return data


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


def load_model_for_fold(
    root: Path, manifest: Mapping[str, Any], fold: int, device: torch.device
) -> nn.Module:
    model_meta = manifest["model"]
    spec = manifest["checkpoints"][fold]
    path = (root / Path(str(spec["path"]))).resolve()
    expected_hash = str(spec["sha256"]).lower()
    actual_hash = sha256_file(path)
    if actual_hash != expected_hash:
        raise ValueError(
            f"checkpoint SHA256 mismatch for fold {fold}: "
            f"expected {expected_hash}, got {actual_hash}"
        )
    payload = load_payload(path)
    if tuple(payload.get("labels", ())) != LABELS:
        raise ValueError(f"checkpoint labels do not match official order: {path.name}")
    args = payload.get("args")
    if not isinstance(args, Mapping):
        raise ValueError(f"checkpoint args metadata is missing: {path.name}")
    if args.get("model") != CHECKPOINT_MODEL_NAME:
        raise ValueError(f"checkpoint architecture metadata is unexpected: {path.name}")
    if int(args.get("fold", -1)) != fold:
        raise ValueError(f"checkpoint fold metadata is unexpected: {path.name}")
    if args.get("freeze_mode") != "last_stage":
        raise ValueError(f"checkpoint is not the reviewed last-stage model: {path.name}")
    if int(args.get("image_size", -1)) != IMAGE_SIZE:
        raise ValueError(f"checkpoint image size is not 384: {path.name}")
    if payload.get("model_name") != CHECKPOINT_MODEL_NAME:
        raise ValueError(f"checkpoint model_name is unexpected: {path.name}")
    resolved_name = str(payload.get("resolved_model_name", ""))
    if "convnext_tiny" not in resolved_name:
        raise ValueError(f"checkpoint resolved architecture is unexpected: {path.name}")
    data_config = payload.get("data_config")
    if not isinstance(data_config, Mapping):
        raise ValueError(f"checkpoint data_config is missing: {path.name}")
    if tuple(data_config.get("input_size", ())) != (3, IMAGE_SIZE, IMAGE_SIZE):
        raise ValueError(f"checkpoint input size metadata is unexpected: {path.name}")
    if str(data_config.get("interpolation", "")).lower() != INTERPOLATION:
        raise ValueError(f"checkpoint interpolation metadata is unexpected: {path.name}")
    if tuple(float(value) for value in data_config.get("mean", ())) != MEAN:
        raise ValueError(f"checkpoint mean metadata is unexpected: {path.name}")
    if tuple(float(value) for value in data_config.get("std", ())) != STD:
        raise ValueError(f"checkpoint std metadata is unexpected: {path.name}")
    state = payload.get("model")
    if not isinstance(state, Mapping):
        raise ValueError(f"checkpoint model state is missing: {path.name}")
    model = build_offline_model()
    try:
        incompatible = model.load_state_dict(state, strict=True)
    except RuntimeError as error:
        raise ValueError(f"strict state_dict load failed for {path.name}: {error}") from error
    if incompatible.missing_keys or incompatible.unexpected_keys:
        raise ValueError(f"strict state_dict mismatch for {path.name}")
    del payload, state, data_config, args, model_meta
    return model.to(device).eval()


def scan_input_images(input_dir: Path) -> list[Path]:
    root = input_dir.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"input directory does not exist: {root}")
    paths = sorted(
        [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES],
        key=lambda path: path.name,
    )
    seen: dict[str, Path] = {}
    for path in paths:
        key = path.name.casefold()
        if key in seen:
            raise ValueError(
                f"duplicate filename across input directories: {seen[key].name} and {path.name}"
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
    if not torch.allclose(probabilities.sum(1), torch.ones(len(probabilities)), atol=1e-5):
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
