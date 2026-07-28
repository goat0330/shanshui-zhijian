"""ML-B2: Dense (full-image) water probability inference.

Predicts water probability for every pixel in a GeoTIFF using block
processing to avoid memory limits. Outputs a probability GeoTIFF aligned
to the input raster.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ml.data_adapter import _compute_indices, REAL_FEATURE_COLS
from ml.model import BaselineModel


def _pixel_to_geo(row, col, transform):
    """Convert pixel coordinates to geographic coordinates."""
    x, y = transform * (col, row)
    return float(x), float(y)


def infer_dense(
    model: BaselineModel,
    raster_path: Path,
    output_path: Path | None = None,
    block_size: int = 512,
    threshold: float = 0.5,
    prob_band_name: str = "water_prob",
    mask_band_name: str = "water_mask",
) -> dict:
    """Full-image water probability and binary mask prediction.

    Args:
        model: Trained BaselineModel (RandomForest).
        raster_path: Path to 6-band S2 GeoTIFF.
        output_path: Optional path for output GeoTIFF (2 bands: prob, mask).
        block_size: Block dimension for tiled processing.
        threshold: Probability threshold for binary mask.

    Returns:
        dict with keys: prob_map (np.ndarray), mask (np.ndarray),
                        crs, transform, bounds, metadata
    """
    import rasterio

    model_name = model.feature_names or REAL_FEATURE_COLS

    with rasterio.open(raster_path) as src:
        crs = src.crs
        transform = src.transform
        height, width = src.height, src.width
        bounds = src.bounds
        descriptions = list(src.descriptions) if src.descriptions else []
        band_count = src.count
        profile = src.profile

    # Determine band mapping
    has_nir = any("nir" in b.lower() for b in descriptions) or band_count >= 4
    has_green = any("green" in b.lower() for b in descriptions) or band_count >= 2
    has_red = any("red" in b.lower() for b in descriptions) or band_count >= 3
    uses_indices = has_nir and has_green and has_red

    prob_map = np.zeros((height, width), dtype=np.float32)
    valid_map = np.zeros((height, width), dtype=bool)

    for row_start in range(0, height, block_size):
        row_end = min(row_start + block_size, height)
        for col_start in range(0, width, block_size):
            col_end = min(col_start + block_size, width)

            with rasterio.open(raster_path) as src:
                block = src.read(
                    window=(
                        (row_start, row_end),
                        (col_start, col_end),
                    )
                ).astype(np.float32)

            bh, bw = block.shape[1], block.shape[2]

            if uses_indices:
                bmap = {}
                for i, desc in enumerate(descriptions):
                    dl = desc.lower()
                    if "blue" in dl:
                        bmap["blue"] = i
                    elif "green" in dl:
                        bmap["green"] = i
                    elif "red" in dl:
                        bmap["red"] = i
                    elif "nir" in dl:
                        bmap["nir"] = i
                    elif "swir1" in dl:
                        bmap["swir1"] = i
                    elif "swir2" in dl:
                        bmap["swir2"] = i
                if not bmap:
                    bmap = {"blue": 0, "green": 1, "red": 2, "nir": 3, "swir1": 4, "swir2": 5}

                indices = _compute_indices(block, bmap)

                rows_list = []
                for y in range(bh):
                    for x in range(bw):
                        pix = block[:, y, x]
                        if not np.isfinite(pix).all():
                            continue
                        row = {
                            "ndwi": indices["ndwi"][y, x],
                            "mndwi": indices["mndwi"][y, x],
                            "ndvi": indices["ndvi"][y, x],
                        }
                        for bname, bidx in bmap.items():
                            row[bname] = float(block[bidx, y, x])
                        rows_list.append(row)

                if rows_list:
                    feat_df = pd.DataFrame(rows_list)
                    feat_cols = [c for c in model_name if c in feat_df.columns]
                    if feat_cols:
                        probs = model.predict_proba(feat_df[feat_cols])[:, 1]
                        idx = 0
                        for y in range(bh):
                            for x in range(bw):
                                if np.isfinite(block[:, y, x]).all():
                                    prob_map[row_start + y, col_start + x] = probs[idx]
                                    valid_map[row_start + y, col_start + x] = True
                                    idx += 1
            else:
                for y in range(bh):
                    for x in range(bw):
                        pix = block[:, y, x]
                        if not np.isfinite(pix).all():
                            continue
                        row = {f"band_{i}": float(pix[i]) for i in range(band_count)}
                        feat_df = pd.DataFrame([row])
                        prob = model.predict_proba(feat_df)[0, 1]
                        prob_map[row_start + y, col_start + x] = prob
                        valid_map[row_start + y, col_start + x] = True

    mask = (prob_map >= threshold).astype(np.uint8)
    mask[~valid_map] = 255  # nodata for uint8

    result = {
        "prob_map": prob_map,
        "mask": mask,
        "crs": crs,
        "transform": transform,
        "bounds": bounds,
        "height": height,
        "width": width,
        "valid_count": int(valid_map.sum()),
    }

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        out_profile = profile.copy()
        out_profile.update(count=2, dtype=np.float32, compress="lzw", bigtiff="IF_SAFER")
        with rasterio.open(output_path, "w", **out_profile) as dst:
            dst.write(prob_map, 1)
            dst.set_band_description(1, prob_band_name)
            dst.write(mask.astype(np.float32), 2)
            dst.set_band_description(2, mask_band_name)
        result["output_path"] = str(output_path)

    return result
