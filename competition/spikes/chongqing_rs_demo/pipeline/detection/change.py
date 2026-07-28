"""
ChangeDetector: 两期水体变化检测

输出:
  - water_gain: 新增水体 (T2有 T1无)
  - water_loss: 消失水体 (T1有 T2无)
  - spectral_change_score: 光谱变化分数 (NDWI差值绝对值)
"""

import numpy as np


def detect_change(
    water_t1: np.ndarray,
    water_t2: np.ndarray,
    ndwi_t1: np.ndarray | None = None,
    ndwi_t2: np.ndarray | None = None,
    min_change_pixels: int = 9,
) -> dict:
    """
    检测两期水体变化

    参数:
        water_t1, water_t2: 水体掩膜 (uint8, 0/1)
        ndwi_t1, ndwi_t2: NDWI 数组 (用于光谱变化分数)
        min_change_pixels: 最小变化连通域像元数

    返回:
        dict with keys: water_gain, water_loss, change_score
    """
    water_gain = (water_t2 == 1) & (water_t1 == 0)
    water_loss = (water_t1 == 1) & (water_t2 == 0)

    # 计算 NDWI 变化绝对值
    if ndwi_t1 is not None and ndwi_t2 is not None:
        change_score = np.abs(ndwi_t2 - ndwi_t1)
    else:
        change_score = np.zeros_like(water_gain, dtype=np.float32)

    # 统计
    gain_pixels = int(water_gain.sum())
    loss_pixels = int(water_loss.sum())
    total_changed = gain_pixels + loss_pixels

    print(f"   水体增加: {gain_pixels} 像元")
    print(f"   水体减少: {loss_pixels} 像元")
    print(f"   变化总计: {total_changed} 像元")

    return {
        "water_gain": water_gain.astype(np.uint8),
        "water_loss": water_loss.astype(np.uint8),
        "change_score": change_score.astype(np.float32),
        "change_mask": np.logical_or(water_gain, water_loss).astype(np.uint8),
        "stats": {
            "gain_pixels": gain_pixels,
            "loss_pixels": loss_pixels,
            "total_changed": total_changed,
        },
    }

