"""
RS-03 — 跨时相 track_id 赋值逻辑

对同一 candidate_type（label）且空间重叠的 Observation 赋予相同 track_id。
空间重叠判断：IoU > 0.5 或质心距离 < 100m。

这是确定性逻辑，不依赖外部数据库。
"""

import hashlib
from typing import Callable

from shapely.geometry import shape as shapely_shape
from shapely import centroid as shapely_centroid

from core.schemas.contracts.perception import Observation

# 默认空间重叠参数
DEFAULT_IOU_THRESHOLD = 0.5
DEFAULT_CENTROID_DISTANCE_M = 100.0


def _get_observation_polygon(obs: Observation) -> object | None:
    """从 Observation.geometry 提取 Shapely 几何对象。

    仅支持 Polygon / MultiPolygon 类型，返回 None 表示无法计算空间重叠。
    """
    geom = obs.geometry
    if not geom:
        return None
    gtype = geom.get("type")
    if gtype not in ("Polygon", "MultiPolygon"):
        return None
    try:
        return shapely_shape(geom)
    except Exception:
        return None


def _compute_iou(poly_a, poly_b) -> float:
    """计算两个多边形之间的 IoU (Intersection over Union)。"""
    if poly_a is None or poly_b is None:
        return 0.0
    try:
        intersection = poly_a.intersection(poly_b).area
        union = poly_a.union(poly_b).area
        if union <= 0:
            return 0.0
        return intersection / union
    except Exception:
        return 0.0


def _compute_centroid_distance_m(poly_a, poly_b) -> float | None:
    """计算两个多边形质心之间的距离（米）。

    假设 geometry 使用 EPSG:4326（经纬度），用近似公式估算米距离。
    高精度场景应使用投影坐标。
    """
    if poly_a is None or poly_b is None:
        return None
    try:
        ca = shapely_centroid(poly_a)
        cb = shapely_centroid(poly_b)
        # 近似: 1度经度 ≈ 111320m, 1度纬度 ≈ 111320*cos(lat) m
        lon_scale = 111320.0
        lat_scale = 111320.0 * abs(ca.y) if abs(ca.y) > 0 else 111320.0
        dx = (ca.x - cb.x) * lon_scale
        dy = (ca.y - cb.y) * lat_scale
        return (dx**2 + dy**2) ** 0.5
    except Exception:
        return None


def _make_track_id(label: str, index: int) -> str:
    """生成确定性 track_id。

    track_id 格式: track-{label_hash}-{index}
    其中 label_hash 是 label 的确定性哈希前缀。
    """
    label_hash = hashlib.sha256(label.encode()).hexdigest()[:8]
    return f"track-{label_hash}-{index:04d}"


def assign_track_ids(
    observations: list[Observation],
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
    centroid_distance_m: float = DEFAULT_CENTROID_DISTANCE_M,
    track_id_fn: Callable[[str, int], str] | None = None,
) -> list[Observation]:
    """为 Observation 列表赋予 track_id。

    同一 label（candidate_type）且空间重叠（IoU > iou_threshold
    或质心距离 < centroid_distance_m）的观测共享同一 track_id。

    Args:
        observations: 待赋值的 Observation 列表
        iou_threshold: IoU 阈值（默认 0.5）
        centroid_distance_m: 质心距离阈值（默认 100m）
        track_id_fn: 自定义 track_id 生成函数，签名为 (label, index) -> str

    Returns:
        更新 track_id 后的 Observation 列表（原地修改 + 返回）
    """
    if track_id_fn is None:
        track_id_fn = _make_track_id

    # 按 label 分组
    groups: dict[str, list[Observation]] = {}
    for obs in observations:
        label = obs.label
        if label not in groups:
            groups[label] = []
        groups[label].append(obs)

    # 每一组内：对空间重叠的观测赋予相同 track_id
    for label, group in groups.items():
        if not group:
            continue

        # 预计算几何
        geoms: list[object | None] = [_get_observation_polygon(o) for o in group]

        # 连通区域标记：使用并查集
        n = len(group)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[ry] = rx

        for i in range(n):
            for j in range(i + 1, n):
                if geoms[i] is None or geoms[j] is None:
                    continue
                iou = _compute_iou(geoms[i], geoms[j])
                if iou > iou_threshold:
                    union(i, j)
                    continue
                dist = _compute_centroid_distance_m(geoms[i], geoms[j])
                if dist is not None and dist < centroid_distance_m:
                    union(i, j)

        # 分配 track_id：同一 root 共享相同 ID
        track_id_for_root: dict[int, str] = {}
        # 首先收集所有 root
        cluster_index = 0
        for i in range(n):
            root = find(i)
            if root not in track_id_for_root:
                track_id_for_root[root] = track_id_fn(label, cluster_index)
                cluster_index += 1

        for i, obs in enumerate(group):
            root = find(i)
            obs.track_id = track_id_for_root[root]

    return observations
