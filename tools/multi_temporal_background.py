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
    """像素级像元中位数：对历史 VH 堆栈逐像元取中位数。

    NaN (NoData) 被自动忽略。全 NaN 像元返回 NaN。
    """
    return np.nanmedian(vh_stack, axis=0).astype(np.float32)


def compute_mad(
    vh_stack: np.ndarray,      # (N, H, W)
    median: np.ndarray,        # (H, W)
    epsilon: float = 0.001,
) -> np.ndarray:
    """像素级 MAD (中位数绝对偏差)，带稳定缩放和下限保护。

    MAD = median(|x_i - median|) * 1.4826  (正态分布一致性因子)
    下限裁剪: max(mad, epsilon)
    结果不含 NaN 或 Inf。

    Args:
        vh_stack: (N, H, W) VH 历史堆栈
        median: (H, W) 背景中位数
        epsilon: 下限保护值 (dB)

    Returns:
        (H, W) float32 MAD values
    """
    median_2d = median[np.newaxis, :, :]  # (1, H, W)
    abs_dev = np.abs(vh_stack - median_2d)
    raw_mad = np.nanmedian(abs_dev, axis=0)  # (H, W)
    # 稳定性缩放 (正态一致性)
    mad = raw_mad * 1.4826
    # 下限保护
    mad = np.maximum(mad, epsilon)
    # NaN 替换为 epsilon
    mad = np.where(~np.isfinite(mad), epsilon, mad)
    return mad.astype(np.float32)


def compute_valid_count(
    vh_stack: np.ndarray,      # (N, H, W)
    nodata: float = -9999.0,
) -> np.ndarray:
    """像素级有效像元计数：每个像元在历史中非 NoData 的景数。

    有效像元条件：有限 + 非 nodata。
    """
    valid = np.isfinite(vh_stack) & (~np.isclose(vh_stack, nodata, atol=1e-3))
    return valid.sum(axis=0).astype(np.uint16)


def compute_water_occurrence(
    water_stack: np.ndarray,   # (N, H, W), uint8, 0/1
) -> np.ndarray:
    """历史水体出现频率：像素级水体 (1) 的均值。

    Args:
        water_stack: (N, H, W) 二值水体掩膜 (0/1)

    Returns:
        (H, W) float32, 值域 [0, 1]
    """
    return water_stack.mean(axis=0, dtype=np.float32)


# ── 变化检测 ──────────────────────────────────────────────────


def compute_robust_zscore(
    current_vh: np.ndarray,        # (H, W)
    baseline_median: np.ndarray,   # (H, W)
    baseline_mad: np.ndarray,      # (H, W)
) -> np.ndarray:
    """鲁棒 Z-Score: (current - median) / max(mad, epsilon)。

    正值 → current 比背景亮 (SAR: 可能水体消失)
    负值 → current 比背景暗 (SAR: 可能出现水体)

    结果不含 NaN 或 Inf。
    """
    zscore = (current_vh.astype(np.float32) - baseline_median.astype(np.float32)) \
             / np.maximum(baseline_mad.astype(np.float32), 0.001)
    zscore = np.where(~np.isfinite(zscore), 0.0, zscore)
    return zscore.astype(np.float32)


def classify_multitemporal_change(
    current_water: np.ndarray,              # (H, W), uint8, 0/1
    water_occurrence: np.ndarray,           # (H, W), float32, 0-1
    robust_zscore: np.ndarray,              # (H, W), float32
    valid_count: np.ndarray,                # (H, W), uint16
    zscore_threshold: float = 3.0,
    water_occurrence_threshold: float = 0.3,
    min_valid_count: int = 3,
) -> dict:
    """多时相变化像素分类。

    分类规则:
    - water_gain: 当前为水体 AND z < -thr AND 历史水体频率 < w_thr AND valid >= min
    - water_loss: 当前非水 AND z > +thr AND 历史水体频率 > w_thr AND valid >= min
    - sar_backscatter_anomaly: |z| > thr AND 不满足 gain/loss 条件 AND valid >= min
    - (其他: 无变化)

    Returns:
        dict with: water_gain_mask, water_loss_mask, sar_anomaly_mask,
                   final_change_mask, change_type_map
    """
    valid_mask = valid_count >= min_valid_count

    # 水增益: 新水体
    water_gain = (
        (current_water == 1)
        & (robust_zscore < -zscore_threshold)
        & (water_occurrence < water_occurrence_threshold)
        & valid_mask
    ).astype(np.uint8)

    # 水消失: 水体消失
    water_loss = (
        (current_water == 0)
        & (robust_zscore > zscore_threshold)
        & (water_occurrence > water_occurrence_threshold)
        & valid_mask
    ).astype(np.uint8)

    # 异常: 显著 Z-Score 但未满足水增益或水消失
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

    # 类别映射 (用于后续 polygonize 标注类别)
    # 0=no_change, 1=water_gain, 2=water_loss, 3=sar_anomaly, 4=mixed
    change_type_map = np.zeros_like(water_gain, dtype=np.uint8)
    change_type_map[water_gain == 1] = 1
    change_type_map[water_loss == 1] = 2
    change_type_map[sar_anomaly == 1] = 3
    # mixed: gain + loss 同时存在 (冲突: 当前像素同时被标为 gain 和 loss)
    # (正常不应出现, 但保留)
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
        "water_occurrence_threshold": water_occurrence_threshold,
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
    """确保数组不含 NaN 或 Inf，替换为 fill。"""
    mask = ~np.isfinite(arr)
    if mask.any():
        arr = arr.copy()
        arr[mask] = fill
    return arr
