"""
Fusion: SAR 为主、光学为辅的水体融合层

规则:
  - S1 双时相 → L1 水体变化主结果
  - S2 T1 → 光学水体与 RGB 辅助证据
  - S2 T2 无效 → optical_t2_status = no_data
"""

import numpy as np


def fuse_water_extent(
    sar_water_t1: np.ndarray,
    sar_water_t2: np.ndarray,
    optical_water_t1: np.ndarray | None = None,
    optical_water_t2: np.ndarray | None = None,
    sar_confidence: float = 0.8,
    optical_confidence: float = 0.6,
) -> dict:
    """
    SAR 为主、光学为辅融合

    返回:
        water_t1, water_t2: 融合后的水体掩膜
        change_mask: 变化区域
        confidence: 逐像元置信度
    """
    # SAR 主水体
    water_t1 = sar_water_t1.astype(np.float32) * sar_confidence
    water_t2 = sar_water_t2.astype(np.float32) * sar_confidence

    # 光学辅助: 有数据时加权叠加
    if optical_water_t1 is not None:
        water_t1 = np.maximum(water_t1, optical_water_t1.astype(np.float32) * optical_confidence)
    if optical_water_t2 is not None:
        water_t2 = np.maximum(water_t2, optical_water_t2.astype(np.float32) * optical_confidence)

    # 变化检测
    water_t1_binary = (water_t1 > 0.5).astype(np.uint8)
    water_t2_binary = (water_t2 > 0.5).astype(np.uint8)

    gain = ((water_t2_binary == 1) & (water_t1_binary == 0)).astype(np.uint8)
    loss = ((water_t1_binary == 1) & (water_t2_binary == 0)).astype(np.uint8)
    change_mask = np.maximum(gain, loss)

    return {
        "water_t1": water_t1_binary,
        "water_t2": water_t2_binary,
        "gain": gain,
        "loss": loss,
        "change_mask": change_mask,
        "confidence_map": np.maximum(water_t1, water_t2),
    }
