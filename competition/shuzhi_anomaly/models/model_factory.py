"""Verified local timm model factory for the six-class task."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import timm
from torch import nn


@dataclass(frozen=True)
class ModelSpec:
    timm_name: str
    image_size: int
    local_pretrained_cfg: str


# These names were checked in the current local timm environment.
MODEL_SPECS = {
    "convnext_tiny_384": ModelSpec(
        timm_name="convnext_tiny",
        image_size=384,
        local_pretrained_cfg="timm/convnext_tiny.in12k_ft_in1k",
    ),
    "efficientnetv2_rw_s": ModelSpec(
        timm_name="efficientnetv2_rw_s",
        image_size=288,
        local_pretrained_cfg="timm/efficientnetv2_rw_s.ra2_in1k",
    ),
}


def build_classifier(
    model_key: str,
    num_classes: int = 6,
    pretrained: bool = True,
    cache_dir: str | Path = "weights/timm",
) -> tuple[nn.Module, dict[str, Any], ModelSpec]:
    if model_key not in MODEL_SPECS:
        raise ValueError(f"Unknown model_key={model_key!r}; available={sorted(MODEL_SPECS)}")
    spec = MODEL_SPECS[model_key]
    model = timm.create_model(
        spec.timm_name,
        pretrained=pretrained,
        num_classes=num_classes,
        cache_dir=str(cache_dir),
    )
    data_config = dict(timm.data.resolve_model_data_config(model))
    data_config["project_image_size"] = spec.image_size
    data_config["local_pretrained_cfg"] = spec.local_pretrained_cfg
    return model, data_config, spec
