"""
FeatureExtractor: 光谱指数计算 (NDWI, MNDWI, NDVI)
"""

import numpy as np
from ..io.reader import RasterInput


def compute_ndwi(ri: RasterInput) -> np.ndarray:
    """
    NDWI = (Green - NIR) / (Green + NIR)
    Sentinel-2: B3 (green), B8 (nir)
    """
    green = ri.array[ri.bands.index("green")]
    nir = ri.array[ri.bands.index("nir")]
    denom = green + nir
    denom = np.where(denom == 0, 1e-10, denom)
    ndwi = (green - nir) / denom
    return ndwi.astype(np.float32)


def compute_mndwi(ri: RasterInput) -> np.ndarray:
    """
    MNDWI = (Green - SWIR1) / (Green + SWIR1)
    Sentinel-2: B3 (green), B11 (swir1)
    对城区水体效果更好
    """
    green = ri.array[ri.bands.index("green")]
    swir1 = ri.array[ri.bands.index("swir1")]
    denom = green + swir1
    denom = np.where(denom == 0, 1e-10, denom)
    mndwi = (green - swir1) / denom
    return mndwi.astype(np.float32)


def compute_ndvi(ri: RasterInput) -> np.ndarray:
    """
    NDVI = (NIR - Red) / (NIR + Red)
    Sentinel-2: B8 (nir), B4 (red)
    """
    nir = ri.array[ri.bands.index("nir")]
    red = ri.array[ri.bands.index("red")]
    denom = nir + red
    denom = np.where(denom == 0, 1e-10, denom)
    ndvi = (nir - red) / denom
    return ndvi.astype(np.float32)


def compute_all_indices(ri: RasterInput) -> dict[str, np.ndarray]:
    """计算全部光谱指数"""
    return {
        "ndwi": compute_ndwi(ri),
        "mndwi": compute_mndwi(ri),
        "ndvi": compute_ndvi(ri),
    }

