"""
InputAdapter: 将 GeoTIFF 读为标准 RasterInput 对象
"""

from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine


@dataclass
class RasterInput:
    """统一的栅格输入对象"""
    array: np.ndarray          # (C, H, W), float32
    crs: CRS
    transform: Affine
    bounds: tuple
    bands: list[str]           # 波段名称列表
    width: int
    height: int
    nodata: float = -9999.0
    metadata: dict = field(default_factory=dict)


def read_geotiff(path: str | Path, bands: list[str] | None = None) -> RasterInput:
    """
    读取 GeoTIFF 为 RasterInput

    参数:
        path: GeoTIFF 文件路径
        bands: 波段命名列表，None 则自动编号
    """
    path = Path(path)
    with rasterio.open(path) as src:
        array = src.read().astype(np.float32)
        crs = src.crs
        transform = src.transform
        bounds = src.bounds
        height = src.height
        width = src.width
        nodata = src.nodata or -9999.0

        if bands is None:
            bands = [f"b{i+1}" for i in range(array.shape[0])]

        metadata = {
            "file": str(path),
            "driver": src.driver,
            "dtype": str(src.dtypes[0]),
            "band_count": src.count,
        }

    return RasterInput(
        array=array,
        crs=crs,
        transform=transform,
        bounds=bounds,
        bands=bands,
        width=width,
        height=height,
        nodata=float(nodata),
        metadata=metadata,
    )


def validate_alignment(inputs: list[RasterInput], label: str = "") -> bool:
    """
    校验多个 RasterInput 是否在同一个空间网格上
    """
    if len(inputs) < 2:
        return True

    ref = inputs[0]
    ok = True
    for i, ri in enumerate(inputs[1:], 1):
        if ri.crs != ref.crs:
            print(f"  ⚠️  {label}[{i}] CRS 不一致: {ri.crs} vs {ref.crs}")
            ok = False
        if ri.width != ref.width or ri.height != ref.height:
            print(f"  [!] {label}[{i}] 尺寸不一致: {ri.width}x{ri.height} vs {ref.width}x{ref.height}")
            ok = False
        if ri.transform != ref.transform:
            print(f"  [!] {label}[{i}] transform 不一致")
            ok = False
    return ok

