"""
ModelClient SAR: VH 极化 Otsu 水体检测

SAR 水体检测原理:
  - 平滑水面产生镜面反射 → 后向散射极低 (水体呈暗色)
  - 粗糙陆地产生漫反射 → 后向散射高 (陆地呈亮色)
  - VH 极化对比度优于 VV

注意: Sentinel-1 GRD 在 GEE 中导出的已是 dB 值，不需要二次转换。
  典型值: VH 水体 < -20 dB, VH 陆地 > -10 dB
"""

import numpy as np
from skimage.filters import threshold_otsu
from scipy import ndimage as ndi


def predict_vh(
    vh: np.ndarray,
    nodata: float = -9999.0,
    apply_filter: bool = True,
    min_size_pixels: int = 25,
    vh_water_max_db: float = -15.0,
) -> tuple[np.ndarray, float]:
    """
    基于 VH 极化的水体检测 (输入已是 dB)

    参数:
        vh: VH 极化数组 (dB 值)
        nodata: NoData 标记值
        apply_filter: 是否做精炼Lee滤波
        min_size_pixels: 最小水体连通域
        vh_water_max_db: VH 水体最大 dB 值 (高于此值不可能是水体)

    返回:
        water_mask: 水体掩膜 (uint8, 0/1)
        threshold: 使用的阈值 (dB)
    """
    arr = vh.copy()
    # 排除 nodata
    valid = np.isfinite(arr) & (arr > -100) & (arr != nodata)

    if not valid.any():
        return np.zeros(vh.shape, dtype=np.uint8), 0.0

    # 只对合理 SAR 范围做 Otsu
    valid_values = arr[valid]
    valid_values = valid_values[(valid_values > -50) & (valid_values < 30)]
    if len(valid_values) < 100:
        return np.zeros(vh.shape, dtype=np.uint8), 0.0

    # Otsu 在 dB 域
    threshold = threshold_otsu(valid_values)
    # 约束: 水体后向散射低 → 低于阈值为水体
    threshold = min(threshold, vh_water_max_db)
    water = (arr < threshold).astype(np.uint8)
    water[~valid] = 0

    # 形态学清理
    labeled, num = ndi.label(water)
    sizes = np.bincount(labeled.ravel())
    for i in range(1, num + 1):
        if sizes[i] < min_size_pixels:
            water[labeled == i] = 0

    water_ratio = water.sum() / water.size * 100
    print(f"  [SAR] VH Otsu threshold: {threshold:.2f} dB, water ratio: {water_ratio:.1f}%")

    return water.astype(np.uint8), float(threshold)


def predict_dual_polarization(
    vh: np.ndarray,
    vv: np.ndarray,
    min_size_pixels: int = 25,
) -> tuple[np.ndarray, float]:
    """
    双极化水体检测: VH 为主, VV 辅助 (输入已是 dB)
    """
    water_vh, thresh_vh = predict_vh(vh, min_size_pixels=5)
    water_vv, thresh_vv = predict_vh(vv, min_size_pixels=5)

    water = (water_vh & water_vv).astype(np.uint8)

    labeled, num = ndi.label(water)
    sizes = np.bincount(labeled.ravel())
    for i in range(1, num + 1):
        if sizes[i] < min_size_pixels:
            water[labeled == i] = 0

    print(f"  [SAR] Dual-pol water ratio: {water.sum()/water.size*100:.1f}%")
    return water.astype(np.uint8), (float(thresh_vh), float(thresh_vv))
