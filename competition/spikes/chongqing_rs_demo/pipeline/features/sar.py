"""
SAR 特征提取: 分贝转换、精炼Lee滤波、后向散射统计
"""

import numpy as np
from scipy import ndimage as ndi
from ..io.reader import RasterInput


def to_db(image: np.ndarray, epsilon: float = 1e-10) -> np.ndarray:
    """后向散射系数 (线性幅度) → 分贝 (dB), 处理 0/负值"""
    image = np.maximum(image, epsilon)  # 避免 log10(0) 或 log10(负值)
    return 10.0 * np.log10(image)


def refine_lee_filter(image: np.ndarray, window_size: int = 5, eps: float = 1e-6) -> np.ndarray:
    """
    精炼Lee滤波降噪

    原理: 在均匀区域用均值, 在异质区域保留边缘
    """
    from scipy.ndimage import uniform_filter

    # 均值
    mean = uniform_filter(image, size=window_size)
    # 方差
    mean_sq = uniform_filter(image**2, size=window_size)
    var = mean_sq - mean**2
    var = np.maximum(var, 0)

    # 局部方差系数
    enl = window_size**2
    ci = np.sqrt(var) / (mean + eps)
    cmax = np.sqrt(1 + 2 / enl)

    # 权重
    w = np.exp(-(ci - cmax) / (cmax + eps))
    w = np.clip(w, 0, 1)

    filtered = mean * (1 - w) + image * w
    return filtered.astype(np.float32)


def compute_sar_stats(sar_ri: RasterInput) -> dict:
    """计算 SAR 统计信息 (处理负值/零值)"""
    stats = {}
    for i, band in enumerate(sar_ri.bands):
        arr = sar_ri.array[i]
        valid = np.isfinite(arr) & (arr > 0)
        if valid.sum() > 100:
            mean_val = arr[valid].mean()
            stats[band] = {
                "mean_db": float(10 * np.log10(max(mean_val, 1e-10))),
                "min": float(arr[valid].min()),
                "max": float(arr[valid].max()),
                "mean_linear": float(mean_val),
                "valid_ratio": float(valid.sum() / arr.size),
            }
        else:
            # 如果有效像元太少, 采样检查原始值范围
            flat = arr.ravel()
            stats[band] = {
                "mean_db": None, "valid_ratio": float(valid.sum() / arr.size),
                "note": "insufficient_valid_pixels",
                "sample_values": flat[:10].tolist(),
            }
    return stats
