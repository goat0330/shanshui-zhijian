"""Water-mask comparison and geospatially correct polygonisation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from rasterio import features
from rasterio.crs import CRS
from rasterio.transform import Affine
from scipy import ndimage as ndi

CHANGE_TYPES = {
    0: "no_change",
    1: "water_increase",
    2: "water_decrease",
    3: "persistent_water",
    255: "nodata",
}


def compute_change_map(water_mask_t1: np.ndarray, water_mask_t2: np.ndarray) -> dict:
    """Compare two masks; only values 0/1 are valid, 255 remains NoData."""
    if water_mask_t1.shape != water_mask_t2.shape:
        raise ValueError(
            f"Water masks must have identical shape: {water_mask_t1.shape} != {water_mask_t2.shape}"
        )
    if water_mask_t1.ndim != 2:
        raise ValueError("Water masks must be two-dimensional")

    valid = np.isin(water_mask_t1, (0, 1)) & np.isin(water_mask_t2, (0, 1))
    increase = (valid & (water_mask_t2 == 1) & (water_mask_t1 == 0)).astype(np.uint8)
    decrease = (valid & (water_mask_t1 == 1) & (water_mask_t2 == 0)).astype(np.uint8)
    persistent = (valid & (water_mask_t1 == 1) & (water_mask_t2 == 1)).astype(np.uint8)

    change_mask = np.full(water_mask_t1.shape, 255, dtype=np.uint8)
    change_mask[valid] = 0
    change_mask[increase == 1] = 1
    change_mask[decrease == 1] = 2
    change_mask[persistent == 1] = 3

    stats = {
        "increase_pixels": int(increase.sum()),
        "decrease_pixels": int(decrease.sum()),
        "persistent_pixels": int(persistent.sum()),
        "total_changed": int(increase.sum() + decrease.sum()),
        "valid_pixels": int(valid.sum()),
        "nodata_pixels": int((~valid).sum()),
        "total_pixels": int(water_mask_t1.size),
    }
    return {
        "change_mask": change_mask,
        "increase": increase,
        "decrease": decrease,
        "persistent": persistent,
        "valid": valid,
        "stats": stats,
    }


def _compute_projected_area(geom: dict, src_crs: CRS, dst_crs: CRS) -> float:
    from rasterio.warp import transform_geom
    from shapely.geometry import shape as shapely_shape

    projected = transform_geom(src_crs, dst_crs, geom, precision=-1)
    return float(shapely_shape(projected).area)


def _native_pixel_area(transform: Affine, crs: CRS) -> float | None:
    if crs.is_projected:
        return abs(float(transform.a * transform.e - transform.b * transform.d))
    return None


def polygonize_change_mask(
    change_mask: np.ndarray,
    transform: Affine,
    crs: CRS,
    min_area_m2: float = 500.0,
    pixel_area_m2: float = 100.0,
    label_map: dict[int, str] | None = None,
    area_crs: CRS | str = "EPSG:4545",
) -> list[dict]:
    """Polygonise gain/loss components and compute area in ``area_crs``."""
    if crs is None:
        raise ValueError("Input CRS is required for polygon area")
    if min_area_m2 < 0:
        raise ValueError("min_area_m2 must be non-negative")
    label_map = label_map or CHANGE_TYPES
    projected_crs = CRS.from_user_input(area_crs)
    native_pixel_area = _native_pixel_area(transform, crs)
    fallback_pixel_area = native_pixel_area or pixel_area_m2
    output: list[dict] = []

    for target_value in (1, 2):
        change_label = label_map.get(target_value, CHANGE_TYPES[target_value])
        mask = change_mask == target_value
        if not mask.any():
            continue
        labelled, component_count = ndi.label(mask)
        for component_index in range(1, component_count + 1):
            component = labelled == component_index
            pixel_count = int(component.sum())
            # Cheap pre-filter. The final decision uses projected geometry area.
            if pixel_count * fallback_pixel_area < min_area_m2:
                continue
            for geom, value in features.shapes(
                component.astype(np.uint8),
                mask=component,
                transform=transform,
            ):
                if not value:
                    continue
                area_m2 = _compute_projected_area(geom, crs, projected_crs)
                if area_m2 < min_area_m2:
                    continue
                rows, cols = np.where(component)
                center_x, center_y = transform * (float(cols.mean()), float(rows.mean()))
                output.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "feature_id": f"CHG-{change_label}-{component_index:04d}",
                        "change_type": change_label,
                        "semantic_label": change_label,
                        "area_m2": round(area_m2, 1),
                        "pixel_count": pixel_count,
                        "center_x": round(float(center_x), 6),
                        "center_y": round(float(center_y), 6),
                        "area_crs": projected_crs.to_string(),
                    },
                })
    return output


def combine_polygons_to_multipolygon(features_list: list[dict]) -> dict | None:
    polygons = []
    for feature in features_list:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        if geometry.get("type") == "Polygon":
            polygons.append(geometry["coordinates"])
        elif geometry.get("type") == "MultiPolygon":
            polygons.extend(geometry["coordinates"])
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
    import rasterio

    change_mask = change_map["change_mask"].astype(np.uint8)
    height, width = change_mask.shape
    profile_use = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "uint8",
        "crs": crs,
        "transform": transform,
        "nodata": 255,
        "compress": "lzw",
    }
    if profile:
        profile_use.update(profile)
        profile_use.update(count=1, dtype="uint8", nodata=255, crs=crs, transform=transform)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_path, "w", **profile_use) as dst:
        dst.write(change_mask, 1)
        dst.set_band_description(1, "change_mask")
        dst.update_tags(**{key: str(value) for key, value in change_map.get("stats", {}).items()})
    return output_path
