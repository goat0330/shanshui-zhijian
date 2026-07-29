"""Vectorised, block-wise dense water inference for aligned Sentinel-2 rasters."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ml.data_adapter import REAL_FEATURE_COLS, RealDataError, _compute_indices, _resolve_band_map
from ml.model import BaselineModel


def _pixel_to_geo(row, col, transform):
    x, y = transform * (col, row)
    return float(x), float(y)


def _feature_frame(block: np.ndarray, valid: np.ndarray, band_map: dict[str, int]) -> pd.DataFrame:
    indices = _compute_indices(block, band_map)
    flat_valid = valid.ravel()
    data: dict[str, np.ndarray] = {
        "ndwi": indices["ndwi"].ravel()[flat_valid],
        "mndwi": indices["mndwi"].ravel()[flat_valid],
        "ndvi": indices["ndvi"].ravel()[flat_valid],
    }
    for band_name, band_index in band_map.items():
        data[band_name] = block[band_index].ravel()[flat_valid]
    return pd.DataFrame(data)


def infer_dense(
    model: BaselineModel,
    raster_path: Path,
    output_path: Path | None = None,
    block_size: int = 512,
    threshold: float = 0.5,
    prob_band_name: str = "water_prob",
    mask_band_name: str = "water_mask",
) -> dict:
    """Predict every valid pixel while retaining exact raster georeferencing."""
    import rasterio
    from rasterio.windows import Window

    raster_path = Path(raster_path)
    if not raster_path.is_file():
        raise FileNotFoundError(raster_path)
    if model.model is None:
        raise RuntimeError("Model not trained")
    if block_size <= 0:
        raise ValueError("block_size must be positive")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0, 1]")

    model_features = list(model.feature_names or REAL_FEATURE_COLS)
    missing_model_features = set(REAL_FEATURE_COLS) - set(model_features)
    if missing_model_features:
        raise RealDataError(
            "Dense S2 inference requires a real-water model with features "
            f"{REAL_FEATURE_COLS}; missing={sorted(missing_model_features)}"
        )

    with rasterio.open(raster_path) as src:
        if src.crs is None:
            raise RealDataError(f"Raster has no CRS: {raster_path}")
        crs = src.crs
        transform = src.transform
        height, width = src.height, src.width
        bounds = src.bounds
        profile = src.profile.copy()
        band_map = _resolve_band_map(src.descriptions, src.count)
        prob_map = np.full((height, width), np.nan, dtype=np.float32)
        valid_map = np.zeros((height, width), dtype=bool)

        for row_start in range(0, height, block_size):
            block_height = min(block_size, height - row_start)
            for col_start in range(0, width, block_size):
                block_width = min(block_size, width - col_start)
                window = Window(col_start, row_start, block_width, block_height)
                masked = src.read(window=window, masked=True).astype(np.float32)
                block = np.asarray(masked.filled(np.nan), dtype=np.float32)
                dataset_valid = src.dataset_mask(window=window) > 0
                valid = dataset_valid & np.isfinite(block).all(axis=0)
                if not valid.any():
                    continue

                frame = _feature_frame(block, valid, band_map)
                missing = set(model_features) - set(frame.columns)
                if missing:
                    raise RealDataError(f"Raster cannot provide model features: {sorted(missing)}")
                probabilities = model.predict_proba(frame[model_features])[:, 1].astype(np.float32)

                local_prob = np.full(valid.shape, np.nan, dtype=np.float32)
                local_prob.ravel()[valid.ravel()] = probabilities
                row_end = row_start + block_height
                col_end = col_start + block_width
                prob_map[row_start:row_end, col_start:col_end] = local_prob
                valid_map[row_start:row_end, col_start:col_end] = valid

    mask = np.full((height, width), 255, dtype=np.uint8)
    mask[valid_map] = (prob_map[valid_map] >= threshold).astype(np.uint8)
    result = {
        "prob_map": prob_map,
        "mask": mask,
        "valid_map": valid_map,
        "crs": crs,
        "transform": transform,
        "bounds": bounds,
        "height": height,
        "width": width,
        "valid_count": int(valid_map.sum()),
        "nodata_count": int((~valid_map).sum()),
    }

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        out_profile = profile.copy()
        out_profile.update(
            driver="GTiff",
            count=2,
            dtype="float32",
            nodata=-9999.0,
            compress="lzw",
            bigtiff="IF_SAFER",
        )
        with rasterio.open(output_path, "w", **out_profile) as dst:
            dst.write(np.where(valid_map, prob_map, -9999.0).astype(np.float32), 1)
            dst.set_band_description(1, prob_band_name)
            dst.write(np.where(valid_map, mask, -9999.0).astype(np.float32), 2)
            dst.set_band_description(2, mask_band_name)
            dst.update_tags(
                inference_threshold=str(threshold),
                valid_pixels=str(result["valid_count"]),
            )
        result["output_path"] = str(output_path)
    return result
