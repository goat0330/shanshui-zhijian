"""
ProductWriter: 将 Pipeline 产物写出为 GeoTIFF / GeoJSON / JSONL / PNG
"""

import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import Affine
from rasterio.crs import CRS
from skimage import exposure


def write_geotiff(
    array: np.ndarray,
    path: str | Path,
    crs: CRS,
    transform: Affine,
    bands: list[str] | None = None,
    nodata: float = -9999.0,
    dtype: str = "float32",
):
    """写出单波段或多波段 GeoTIFF"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if array.ndim == 2:
        array = array[np.newaxis, :, :]

    count = array.shape[0]
    if bands and len(bands) != count:
        raise ValueError(f"波段名数量 ({len(bands)}) 与数组维度 ({count}) 不匹配")

    # uint8 时 nodata 设为 255, float32 时设为 -9999
    actual_nodata = 255 if dtype == "uint8" else nodata
    if dtype == "uint8":
        array = np.clip(array, 0, 255).astype(np.uint8)

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=array.shape[1],
        width=array.shape[2],
        count=count,
        dtype=dtype,
        crs=crs,
        transform=transform,
        nodata=actual_nodata,
        compress="lzw",
    ) as dst:
        for i in range(count):
            dst.write(array[i], i + 1)
            if bands:
                dst.set_band_description(i + 1, bands[i])

    print(f"   GeoTIFF 写出: {path}")


def write_geojson(
    features: list[dict],
    path: str | Path,
):
    """写出 GeoJSON FeatureCollection"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fc = {
        "type": "FeatureCollection",
        "features": features,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)
    print(f"   GeoJSON 写出: {path} ({len(features)} features)")


def write_jsonl(
    records: list[dict],
    path: str | Path,
):
    """写出 JSONL (每行一个 DetectionResult)"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"   JSONL 写出: {path} ({len(records)} records)")


def write_preview(
    array: np.ndarray,
    path: str | Path,
):
    """
    写出 8-bit PNG 预览图
    如果是多波段取前3个波段为RGB，单波段为灰度
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if array.ndim == 3 and array.shape[0] >= 3:
        # RGB: 取前3波段，各拉伸到 0-255
        rgb = array[:3].transpose(1, 2, 0)
        rgb = exposure.rescale_intensity(rgb, out_range=(0, 255)).astype(np.uint8)
    elif array.ndim == 2:
        rgb = exposure.rescale_intensity(array, out_range=(0, 255)).astype(np.uint8)
    else:
        rgb = exposure.rescale_intensity(array[0], out_range=(0, 255)).astype(np.uint8)

    import imageio.v3 as iio
    iio.imwrite(str(path), rgb)
    print(f"   预览图写出: {path}")

