"""ML-B2: Change detection between two water masks with polygonization.

Computes water gain/loss/persistent from two binary water masks and
converts the change raster to GeoJSON polygons.
"""

from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from rasterio import features
from rasterio.transform import Affine
from rasterio.crs import CRS


CHANGE_TYPES = {
    0: "no_change",
    1: "water_gain",
    2: "water_loss",
    3: "persistent_water",
}


def compute_change_map(
    water_mask_t1: np.ndarray,
    water_mask_t2: np.ndarray,
) -> dict:
    """Compare two binary water masks and produce change maps.

    Args:
        water_mask_t1: Binary water mask at T1 (uint8, 0/1)
        water_mask_t2: Binary water mask at T2 (uint8, 0/1)

    Returns:
        dict with keys:
            change_mask (uint8): 0=no_change, 1=gain, 2=loss, 3=persistent
            gain (uint8): 1=new water at T2
            loss (uint8): 1=water lost at T2
            persistent (uint8): 1=water at both times
            stats: dict of pixel counts
    """
    gain = ((water_mask_t2 == 1) & (water_mask_t1 == 0)).astype(np.uint8)
    loss = ((water_mask_t1 == 1) & (water_mask_t2 == 0)).astype(np.uint8)
    persistent = ((water_mask_t1 == 1) & (water_mask_t2 == 1)).astype(np.uint8)

    change_mask = np.zeros_like(water_mask_t1, dtype=np.uint8)
    change_mask[gain == 1] = 1
    change_mask[loss == 1] = 2
    change_mask[persistent == 1] = 3

    stats = {
        "gain_pixels": int(gain.sum()),
        "loss_pixels": int(loss.sum()),
        "persistent_pixels": int(persistent.sum()),
        "total_changed": int(gain.sum()) + int(loss.sum()),
        "total_pixels": int(water_mask_t1.size),
    }

    return {
        "change_mask": change_mask,
        "gain": gain,
        "loss": loss,
        "persistent": persistent,
        "stats": stats,
    }


def polygonize_change_mask(
    change_mask: np.ndarray,
    transform: Affine,
    crs: CRS,
    min_area_m2: float = 500.0,
    pixel_area_m2: float = 100.0,
    label_map: dict[int, str] | None = None,
) -> list[dict]:
    """Convert a change mask (0/1/2/3) to a list of GeoJSON Features.

    Each connected component of gain (1) and loss (2) becomes a Feature
    with its change type, area, and centroid.

    Args:
        change_mask: uint8 raster with values 0-3.
        transform: Affine transform of the raster.
        crs: CRS of the raster.
        min_area_m2: Minimum polygon area in square meters.
        pixel_area_m2: Area of one pixel in square meters.
        label_map: Map of raster value to change type string.

    Returns:
        List of GeoJSON Feature dicts.
    """
    if label_map is None:
        label_map = CHANGE_TYPES

    features_list = []
    # Process gain (1) and loss (2) separately
    for target_value, change_label in [(1, "water_gain"), (2, "water_loss")]:
        mask = (change_mask == target_value).astype(np.uint8)
        if mask.sum() == 0:
            continue

        labeled, num_features = ndi.label(mask)

        for i in range(1, num_features + 1):
            feature_mask = (labeled == i).astype(np.uint8)
            pixel_count = int(feature_mask.sum())
            area_m2 = pixel_count * pixel_area_m2

            if area_m2 < min_area_m2:
                continue

            shapes_generator = features.shapes(
                feature_mask,
                mask=feature_mask,
                transform=transform,
            )
            for geom, value in shapes_generator:
                if value == 0:
                    continue

                rows, cols = np.where(feature_mask > 0)
                center_row, center_col = rows.mean(), cols.mean()
                center_x, center_y = transform * (center_col, center_row)

                feat = {
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "feature_id": f"CHG-{change_label}-{i:04d}",
                        "change_type": change_label,
                        "area_m2": round(area_m2, 1),
                        "pixel_count": pixel_count,
                        "center_x": round(center_x, 6),
                        "center_y": round(center_y, 6),
                    },
                }
                features_list.append(feat)

    return features_list


def change_map_to_geotiff(
    change_map: dict,
    output_path: Path,
    transform: Affine,
    crs: CRS,
    profile: dict | None = None,
):
    """Write the change mask as a GeoTIFF with descriptive band names."""
    import rasterio

    change_mask = change_map["change_mask"]
    height, width = change_mask.shape

    profile_use = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": change_mask.dtype,
        "crs": crs,
        "transform": transform,
        "compress": "lzw",
    }
    if profile:
        profile_use.update(profile)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(output_path, "w", **profile_use) as dst:
        dst.write(change_mask, 1)
        dst.set_band_description(1, "change_mask")
    return output_path
