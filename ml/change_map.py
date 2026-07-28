"""ML-B2: Change detection between two water masks with polygonization.

Computes water increase/decrease from two binary water masks and
converts the change raster to GeoJSON polygons with proper semantic labels.
"""

from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from rasterio import features
from rasterio.transform import Affine
from rasterio.crs import CRS


CHANGE_TYPES = {
    0: "no_change",
    1: "water_increase",
    2: "water_decrease",
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
            change_mask (uint8): 0=no_change, 1=increase, 2=decrease, 3=persistent
            increase (uint8): 1=new water at T2
            decrease (uint8): 1=water lost at T2
            persistent (uint8): 1=water at both times
            stats: dict of pixel counts
    """
    increase = ((water_mask_t2 == 1) & (water_mask_t1 == 0)).astype(np.uint8)
    decrease = ((water_mask_t1 == 1) & (water_mask_t2 == 0)).astype(np.uint8)
    persistent = ((water_mask_t1 == 1) & (water_mask_t2 == 1)).astype(np.uint8)

    change_mask = np.zeros_like(water_mask_t1, dtype=np.uint8)
    change_mask[increase == 1] = 1
    change_mask[decrease == 1] = 2
    change_mask[persistent == 1] = 3

    stats = {
        "increase_pixels": int(increase.sum()),
        "decrease_pixels": int(decrease.sum()),
        "persistent_pixels": int(persistent.sum()),
        "total_changed": int(increase.sum()) + int(decrease.sum()),
        "total_pixels": int(water_mask_t1.size),
    }

    return {
        "change_mask": change_mask,
        "increase": increase,
        "decrease": decrease,
        "persistent": persistent,
        "stats": stats,
    }


def _compute_projected_area(
    geom: dict,
    src_crs: CRS,
    dst_crs: CRS = CRS.from_epsg(4545),
) -> float:
    """Reproject a polygon to a projected CRS and compute area in m2."""
    try:
        from rasterio.warp import transform_geom
        import pyproj
        projected = transform_geom(
            src_crs.to_dict() if hasattr(src_crs, 'to_dict') else str(src_crs),
            dst_crs.to_dict() if hasattr(dst_crs, 'to_dict') else str(dst_crs),
            geom,
        )
        from shapely.geometry import shape as shapely_shape
        s = shapely_shape(projected)
        return float(s.area)
    except Exception:
        return 0.0


def polygonize_change_mask(
    change_mask: np.ndarray,
    transform: Affine,
    crs: CRS,
    min_area_m2: float = 500.0,
    pixel_area_m2: float = 100.0,
    label_map: dict[int, str] | None = None,
) -> list[dict]:
    """Convert a change mask (0/1/2/3) to a list of GeoJSON Features.

    Each connected component of increase (1) and decrease (2) becomes a Feature
    with its semantic change type, proper CRS area, and centroid.

    Args:
        change_mask: uint8 raster with values 0-3.
        transform: Affine transform of the raster.
        crs: CRS of the raster.
        min_area_m2: Minimum polygon area in square meters.
        pixel_area_m2: Area of one pixel in square meters (fallback).
        label_map: Map of raster value to change type string.

    Returns:
        List of GeoJSON Feature dicts.
    """
    if label_map is None:
        label_map = CHANGE_TYPES

    features_list = []
    projected_crs = CRS.from_epsg(4545)

    for target_value, change_label in [(1, "water_increase"), (2, "water_decrease")]:
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

                area_proper = _compute_projected_area(geom, crs, projected_crs)
                area_used = area_proper if area_proper > 0 else area_m2

                feat = {
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "feature_id": f"CHG-{change_label}-{i:04d}",
                        "change_type": change_label,
                        "semantic_label": change_label,
                        "area_m2": round(area_used, 1),
                        "pixel_count": pixel_count,
                        "center_x": round(center_x, 6),
                        "center_y": round(center_y, 6),
                    },
                }
                features_list.append(feat)

    return features_list


def combine_polygons_to_multipolygon(
    features_list: list[dict],
) -> dict | None:
    """Combine multiple polygon features into a single MultiPolygon geometry.

    Args:
        features_list: List of GeoJSON Feature dicts.

    Returns:
        GeoJSON geometry dict (MultiPolygon), or None if empty.
    """
    polygons = []
    for feat in features_list:
        g = feat.get("geometry")
        if g is None:
            continue
        if g["type"] == "Polygon":
            polygons.append(g["coordinates"])
        elif g["type"] == "MultiPolygon":
            polygons.extend(g["coordinates"])

    if not polygons:
        return None
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


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
