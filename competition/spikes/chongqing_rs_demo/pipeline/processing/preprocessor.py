"""
Preprocessor: 对齐检查、裁剪、NoData 处理
"""

import numpy as np
from ..io.reader import RasterInput, validate_alignment


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
