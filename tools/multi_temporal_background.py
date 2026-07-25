"""
RS-01B-2 — 多时相 SAR 稳健背景统计

纯函数模块：从历史 VH 堆栈计算背景中位数、MAD、有效像元计数、
水体出现频率和鲁棒 Z-Score。

无工具/管线依赖，输入输出均为 numpy 数组。
"""

import numpy as np


# ── 核心统计 ──────────────────────────────────────────────────


def compute_median_background(
    vh_stack: np.ndarray,      # (N, H, W), float32, NoData = NaN
) -> np.ndarray:
    """像素级像元中位数：对历史 VH 堆栈逐像元取中位数。"""
    return np.nanmedian(vh_stack, axis=0).astype(np.float32)


def compute_mad(
    vh_stack: np.ndarray,      # (N, H, W)
    median: np.ndarray,        # (H, W)
    epsilon: float = 0.001,
) -> np.ndarray:
    """像素级 MAD，稳定缩放 + 下限保护。"""
    median_2d = median[np.newaxis, :, :]
    abs_dev = np.abs(vh_stack - median_2d)
    raw_mad = np.nanmedian(abs_dev, axis=0)
    mad = raw_mad * 1.4826
    mad = np.maximum(mad, epsilon)
    mad = np.where(~np.isfinite(mad), epsilon, mad)
    return mad.astype(np.float32)


def compute_valid_count(
    vh_stack: np.ndarray,
    nodata: float = -9999.0,
) -> np.ndarray:
    """像素级有效像元计数。"""
    valid = np.isfinite(vh_stack) & (~np.isclose(vh_stack, nodata, atol=1e-3))
    return valid.sum(axis=0).astype(np.uint16)


def compute_water_occurrence(
    water_stack: np.ndarray,    # (N, H, W), uint8, 0/1
    valid_stack: np.ndarray,    # (N, H, W), bool (True=有效)
) -> np.ndarray:
    """历史水体出现频率 (以有效像元为分母)。

    occurrence = sum(valid_water) / sum(valid_mask)
    当 sum(valid_mask)==0 时返回 0。
    """
    valid_water = water_stack.astype(bool) & valid_stack
    water_sum = valid_water.sum(axis=0).astype(np.float32)
    valid_sum = valid_stack.sum(axis=0).astype(np.float32)
    valid_sum = np.maximum(valid_sum, 1e-10)  # 防除零
    occ = water_sum / valid_sum
    occ[valid_sum < 1] = 0.0  # 无有效像元时频率为 0
    return occ


# ── 变化检测 ──────────────────────────────────────────────────


def compute_robust_zscore(
    current_vh: np.ndarray,
    baseline_median: np.ndarray,
    baseline_mad: np.ndarray,
) -> np.ndarray:
    """鲁棒 Z-Score: (current - median) / max(mad, epsilon)。"""
    zscore = (current_vh.astype(np.float32) - baseline_median.astype(np.float32)) \
             / np.maximum(baseline_mad.astype(np.float32), 0.001)
    zscore = np.where(~np.isfinite(zscore), 0.0, zscore)
    return zscore.astype(np.float32)


def classify_multitemporal_change(
    current_water: np.ndarray,       # (H, W), uint8, 0/1
    water_occurrence: np.ndarray,    # (H, W), float32, 0-1
    robust_zscore: np.ndarray,       # (H, W), float32
    valid_count: np.ndarray,         # (H, W), uint16
    zscore_threshold: float = 3.0,
    stable_land_max: float = 0.2,
    stable_water_min: float = 0.8,
    min_valid_count: int = 3,
) -> dict:
    """多时相变化像素分类（双阈值）。

    分类规则:
    - water_gain:  当前=水 AND occ < stable_land_max AND z < -thr AND valid
    - water_loss:  当前=非水 AND occ > stable_water_min AND z > +thr AND valid
    - uncertain_zone:  occ 在 [stable_land_max, stable_water_min] 之间
        → 不直接判 gain/loss (判为 sar_anomaly 或 no_change)
    - sar_anomaly: |z| > thr AND 不满足 gain/loss AND valid
    - mixed: 同一图斑内含 gain+loss (由 polygonize 标注)
    """
    valid_mask = valid_count >= min_valid_count

    # 增益: 历史为稳定陆地 → 当前出现水体
    water_gain = (
        (current_water == 1)
        & (water_occurrence < stable_land_max)
        & (robust_zscore < -zscore_threshold)
        & valid_mask
    ).astype(np.uint8)

    # 损失: 历史为稳定水体 → 当前消失
    water_loss = (
        (current_water == 0)
        & (water_occurrence > stable_water_min)
        & (robust_zscore > zscore_threshold)
        & valid_mask
    ).astype(np.uint8)

    # 异常: 显著 Z-Score 但不满足 gain/loss
    # (包括 uncertain_zone 像素 + gain/loss 未覆盖的高 zscore 像素)
    sar_anomaly = (
        (np.abs(robust_zscore) > zscore_threshold)
        & (water_gain == 0)
        & (water_loss == 0)
        & valid_mask
    ).astype(np.uint8)

    # 合并
    final_change = np.logical_or.reduce([
        water_gain.astype(bool),
        water_loss.astype(bool),
        sar_anomaly.astype(bool),
    ]).astype(np.uint8)

    # 类别映射: 0=no_change 1=water_gain 2=water_loss 3=sar_anomaly 4=mixed
    change_type_map = np.zeros_like(water_gain, dtype=np.uint8)
    change_type_map[water_gain == 1] = 1
    change_type_map[water_loss == 1] = 2
    change_type_map[sar_anomaly == 1] = 3
    mixed = (water_gain == 1) & (water_loss == 1)
    change_type_map[mixed] = 4

    stats = {
        "water_gain_pixels": int(water_gain.sum()),
        "water_loss_pixels": int(water_loss.sum()),
        "sar_anomaly_pixels": int(sar_anomaly.sum()),
        "mixed_pixels": int(mixed.sum()),
        "total_changed_pixels": int(final_change.sum()),
        "valid_pixel_count": int(valid_mask.sum()),
        "zscore_threshold": zscore_threshold,
        "stable_land_max": stable_land_max,
        "stable_water_min": stable_water_min,
        "min_valid_count": min_valid_count,
    }

    return {
        "water_gain_mask": water_gain,
        "water_loss_mask": water_loss,
        "sar_anomaly_mask": sar_anomaly,
        "final_change_mask": final_change,
        "change_type_map": change_type_map,
        "stats": stats,
    }


def ensure_no_nan_inf(arr: np.ndarray, fill: float = 0.0) -> np.ndarray:
    """确保数组不含 NaN 或 Inf。"""
    mask = ~np.isfinite(arr)
    if mask.any():
        arr = arr.copy()
        arr[mask] = fill
    return arr
