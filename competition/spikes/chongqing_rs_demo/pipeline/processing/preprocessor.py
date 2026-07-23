"""
Preprocessor: 对齐检查、重投影、裁剪、NoData 处理
"""

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from ..io.reader import RasterInput, validate_alignment

# 朝天门投影: CGCS2000 / 3-degree Gauss-Kruger CM 108E
# 朝天门位于 106.575°E，EPSG:4545 覆盖 106°30'—109°30'，偏差 < 1.5°
TARGET_CRS = CRS.from_epsg(4545)
TARGET_RES = 10  # 10m


def reproject_to_target(ri: RasterInput) -> RasterInput:
    """
    将 RasterInput 重投影到目标 CRS (EPSG:4545, 10m)

    分类数据用 nearest，连续数据用 bilinear
    """
    from rasterio.warp import calculate_default_transform, reproject

    left, bottom, right, top = ri.bounds
    transform, width, height = calculate_default_transform(
        ri.crs, TARGET_CRS, ri.width, ri.height,
        left=left, bottom=bottom, right=right, top=top,
        resolution=TARGET_RES,
    )

    # 判断数据类型: 分类数据用 nearest, 连续数据用 bilinear
    categorical_bands = {"landcover", "occurrence", "water_mask", "change_mask"}
    is_categorical = any(b in categorical_bands for b in ri.bands)
    resampling = Resampling.nearest if is_categorical else Resampling.bilinear

    dst_array = np.zeros((ri.array.shape[0], height, width), dtype=np.float32)

    for i in range(ri.array.shape[0]):
        reproject(
            ri.array[i],
            dst_array[i],
            src_transform=ri.transform,
            src_crs=ri.crs,
            dst_transform=transform,
            dst_crs=TARGET_CRS,
            resampling=resampling,
            src_nodata=ri.nodata,
            dst_nodata=ri.nodata,
        )

    return RasterInput(
        array=dst_array,
        crs=TARGET_CRS,
        transform=transform,
        bounds=(transform.c, transform.f + transform.e * height,
                transform.c + transform.a * width, transform.f),
        bands=ri.bands,
        width=width,
        height=height,
        nodata=ri.nodata,
        metadata={**ri.metadata, "reprojected": True, "src_crs": str(ri.crs)},
    )


def resample_to_grid(src: RasterInput, ref: RasterInput) -> RasterInput:
    """
    将 src 重采样到 ref 的精确网格 (CRS + transform + size)
    替代 skimage.resize: 保留地理参考一致性
    """
    from rasterio.warp import reproject

    categorical_bands = {"landcover", "occurrence", "water_mask", "change_mask"}
    is_categorical = any(b in categorical_bands for b in src.bands)
    resampling = Resampling.nearest if is_categorical else Resampling.bilinear

    dst_array = np.zeros((src.array.shape[0], ref.height, ref.width), dtype=np.float32)

    for i in range(src.array.shape[0]):
        reproject(
            src.array[i],
            dst_array[i],
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            resampling=resampling,
            src_nodata=src.nodata,
            dst_nodata=src.nodata,
        )

    return RasterInput(
        array=dst_array,
        crs=ref.crs,
        transform=ref.transform,
        bounds=ref.bounds,
        bands=src.bands,
        width=ref.width,
        height=ref.height,
        nodata=src.nodata,
        metadata={**src.metadata, "resampled_to_grid": True, "ref_grid": str(ref.crs)},
    )


def check_and_report(inputs: list[RasterInput], labels: list[str]) -> bool:
    """报告对齐状态"""
    print("  ── 对齐检查 ──")
    ok = validate_alignment(inputs)
    for i, ri in enumerate(inputs):
        print(f"  [{labels[i]}] {ri.width}x{ri.height}, CRS={ri.crs}, "
              f"bands={ri.bands}, nodata={ri.nodata}")
    return ok


def replace_nodata(ri: RasterInput, new_nodata: float = 0.0) -> RasterInput:
    """将 nodata 替换为指定值（用于后续计算）"""
    mask = ri.array == ri.nodata
    arr = ri.array.copy()
    arr[mask] = new_nodata
    return RasterInput(
        array=arr,
        crs=ri.crs,
        transform=ri.transform,
        bounds=ri.bounds,
        bands=ri.bands,
        width=ri.width,
        height=ri.height,
        nodata=new_nodata,
        metadata=ri.metadata,
    )

