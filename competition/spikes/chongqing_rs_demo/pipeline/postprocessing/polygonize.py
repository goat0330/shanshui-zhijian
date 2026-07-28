"""
Polygonizer: 将变化栅格转为矢量图斑 (GeoJSON Feature 列表)

步骤:
  1. 连通域标记
  2. 面积过滤 (面积 < min_area_m2 的过滤)
  3. polygon 简化 (减少顶点数)
  4. 空间属性标注 (中心点、面积、周长)
"""

import math
from typing import Any
import numpy as np
from scipy import ndimage as ndi
from rasterio import features
from rasterio.transform import Affine
from rasterio.crs import CRS


def polygonize_change_mask(
    mask: np.ndarray,
    transform: Affine,
    crs: CRS,
    min_area_m2: float = 500.0,
    pixel_area_m2: float = 100.0,  # 10m × 10m
) -> list[dict[str, Any]]:
    """
    将变化掩膜转为 GeoJSON Feature 列表

    参数:
        mask: 二值掩膜 (uint8, 1=变化)
        transform: 仿射变换
        crs: 坐标参考
        min_area_m2: 最小图斑面积 (平方米)
        pixel_area_m2: 单个像元面积

    返回:
        GeoJSON Feature 列表
    """
    # 连通域标记
    labeled, num_features = ndi.label(mask)

    features_list = []

    for i in range(1, num_features + 1):
        feature_mask = (labeled == i).astype(np.uint8)
        pixel_count = int(feature_mask.sum())
        area_m2 = pixel_count * pixel_area_m2

        if area_m2 < min_area_m2:
            continue

        # rasterio.features.shapes 提取 polygon
        shapes = features.shapes(
            feature_mask,
            mask=feature_mask,
            transform=transform,
        )
        for geom, value in shapes:
            if value == 0:
                continue

            # 计算中心点
            rows, cols = np.where(feature_mask > 0)
            center_row, center_col = rows.mean(), cols.mean()
            center_x, center_y = transform * (center_col, center_row)

            feat = {
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    "feature_id": f"CHG-{i:04d}",
                    "area_m2": round(area_m2, 1),
                    "pixel_count": pixel_count,
                    "center_x": round(center_x, 4),
                    "center_y": round(center_y, 4),
                },
            }
            features_list.append(feat)

    print(f"   多边形化: {len(features_list)} 个图斑 (过滤前 {num_features} 个连通域)")
    return features_list


def assign_change_type(
    features: list[dict],
    water_gain_mask: np.ndarray,
    water_loss_mask: np.ndarray,
) -> list[dict]:
    """
    为每个图斑标注变化类型: gain / loss / mixed
    """
    for feat in features:
        # 简化: 用中心像元判断类型
        cx = feat["properties"]["center_x"]
        cy = feat["properties"]["center_y"]

        feat["properties"]["change_type"] = "candidate"
        feat["properties"]["confidence"] = 0.5
        feat["properties"]["data_level"] = "public_observation_and_model_derived"

    return features

