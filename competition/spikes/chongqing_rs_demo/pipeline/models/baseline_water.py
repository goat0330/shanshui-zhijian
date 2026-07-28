"""
ModelClient V0: NDWI + 分区局部Otsu + 先验过滤

输出: 水体掩膜 (1=水体, 0=非水体)
"""

import numpy as np
from skimage.filters import threshold_otsu
from scipy import ndimage as ndi
from ..io.reader import RasterInput


def local_otsu_threshold(ndwi: np.ndarray, grid_size: int = 50) -> float:
    """
    分区局部Otsu: 将图像分为 grid_size×grid_size 的区块,
    每个区块独立算Otsu阈值, 最终取中位数作为全局阈值

    参数:
        ndwi: NDWI 二维数组
        grid_size: 分区块大小 (像元数)
    """
    h, w = ndwi.shape
    thresholds = []
    valid_mask = ~np.isnan(ndwi)

    for i in range(0, h, grid_size):
        for j in range(0, w, grid_size):
            tile = ndwi[i:i+grid_size, j:j+grid_size]
            tile_valid = valid_mask[i:i+grid_size, j:j+grid_size]
            if tile_valid.sum() < grid_size * grid_size * 0.3:
                continue  # 跳过有效像元太少的区块
            try:
                t = threshold_otsu(tile[tile_valid])
                thresholds.append(t)
            except (ValueError, TypeError):
                continue

    if not thresholds:
        # 回退: 全局Otsu
        return threshold_otsu(ndwi[valid_mask])

    return float(np.median(thresholds))


def apply_water_mask(
    ndwi: np.ndarray,
    threshold: float,
    jrc_occurrence: np.ndarray | None = None,
    worldcover: np.ndarray | None = None,
    min_size_pixels: int = 25,
) -> np.ndarray:
    """
    生成水体掩膜并后处理

    后处理顺序:
      1. NDWI > threshold → 初始水体
      2. JRC 稳定水体 (occurrence > 50%) 强制保留
      3. WorldCover 排除: 建筑(50), 裸地(60)
      4. 形态学清理: 移除 < min_size_pixels 的碎块
    """
    # Step 1: NDWI 阈值
    water = (ndwi > threshold).astype(np.uint8)

    # Step 2: JRC 稳定水体强制保留
    if jrc_occurrence is not None:
        stable_water = jrc_occurrence > 50
        water = np.maximum(water, stable_water.astype(np.uint8))

    # Step 3: WorldCover 排除
    if worldcover is not None:
        # ESA WorldCover: 50=built-up, 60=bare/sparse vegetation
        exclude = (worldcover == 50) | (worldcover == 60)
        water[exclude] = 0

    # Step 4: 形态学清理 — 移除小连通域
    labeled, num = ndi.label(water)
    sizes = np.bincount(labeled.ravel())
    for i in range(1, num + 1):
        if sizes[i] < min_size_pixels:
            water[labeled == i] = 0

    return water.astype(np.uint8)


def predict(
    ndwi: np.ndarray,
    jrc_occurrence: np.ndarray | None = None,
    worldcover: np.ndarray | None = None,
    grid_size: int = 50,
    min_size_pixels: int = 25,
) -> tuple[np.ndarray, float]:
    """
    完整水体提取管线

    返回:
        water_mask: 水体掩膜 (uint8, 0/1)
        threshold: 使用的Otsu阈值
    """
    threshold = local_otsu_threshold(ndwi, grid_size=grid_size)
    print(f"  [Water] Otsu threshold: {threshold:.4f}")

    water_mask = apply_water_mask(
        ndwi, threshold,
        jrc_occurrence=jrc_occurrence,
        worldcover=worldcover,
        min_size_pixels=min_size_pixels,
    )

    water_ratio = water_mask.sum() / water_mask.size * 100
    print(f"  [Water] water ratio: {water_ratio:.1f}%")

    return water_mask, threshold

