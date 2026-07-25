"""
RS-01B-3 -- Persistence gating and candidate object ranking.

Pure functions for:
  1. Per-scene change detection (each current scene independently vs same history background)
  2. Persistence statistics (persistence_count, persistence_ratio, first/last_seen_index)
  3. Persistent vs transient classification
  4. Object linking across time (IoU or centroid distance + spatial intersect)
  5. Candidate classification (persistent / transient / uncertain)
  6. Candidate ranking (candidate_rank_score)

Config defaults (all overridable via tool_config):
  persistence:
    minimum_occurrences: 2
    minimum_ratio: 0.67
    transient_policy: retain_as_low_confidence
    require_same_change_type: true
  object_linking:
    minimum_iou: 0.30
    maximum_centroid_distance_m: 50
    require_same_change_type: true
    require_spatial_intersect: false
  ranking:
    weight_persistence_ratio: 0.40
    weight_normalized_robust_z: 0.25
    weight_normalized_area: 0.20
    weight_quality_factor: 0.15

AOI-0 real run (048d188 baseline):
  - 8 history + 2 current scenes
  - 6855 changed pixels -> 156 polygons
  - 656 candidates (97 persistent, 559 transient)

CRS discipline (A0):
  - Spatial linking MUST use a projected CRS (meters), NOT EPSG:4326 (degrees).
  - geometry_crs parameter is required.
  - Geographic CRS -> auto-convert to best UTM zone for centroid.
  - Polygon IoU uses shapely (not bounds-based approximation).
"""

from __future__ import annotations

import hashlib
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Any

import pyproj
from shapely.geometry import shape as shapely_shape
from shapely.ops import transform as shapely_transform

logger = logging.getLogger(__name__)

# ── CRS utils ────────────────────────────────────────────────────


def _find_utm_epsg(lon: float, lat: float) -> str:
    """Find the best UTM EPSG code for a (lon, lat) in WGS84."""
    zone = int((lon + 180) / 6) + 1
    hemisphere = "7" if lat >= 0 else "8"
    return f"EPSG:326{zone:02d}" if hemisphere == "7" else f"EPSG:327{zone:02d}"


def _check_or_convert_crs(
    geometry_crs: str | None,
    features: list[dict],
) -> tuple[str, list[dict]]:
    """
    Validate CRS and return (working_crs, features_in_working_crs).

    - If geometry_crs is projected (meter-based): use as-is.
    - If geometry_crs is geographic (e.g. EPSG:4326):
      auto-compute best UTM zone from centroid and transform all geometries.
    - If geometry_crs is None: raise ValueError.
    """
    if geometry_crs is None:
        raise ValueError(
            "geometry_crs is required for spatial linking. "
            "Use a projected CRS (e.g. EPSG:4545) so centroid distances are in meters."
        )

    raw = pyproj.CRS(geometry_crs)
    if raw.is_projected:
        return geometry_crs, features  # already meters

    if not raw.is_geographic:
        raise ValueError(
            f"geometry_crs='{geometry_crs}' is neither projected nor geographic; "
            "cannot determine spatial unit."
        )

    # Geographic CRS -> compute centroid in WGS84 and pick UTM zone
    all_pts: list[tuple[float, float]] = []
    for feat in features:
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            s = shapely_shape(geom)
            if s.is_empty:
                continue
            c = s.centroid
            if c:
                all_pts.append((c.x, c.y))
        except Exception:
            continue

    if not all_pts:
        raise ValueError(
            f"Cannot auto-convert geographic CRS '{geometry_crs}': "
            "no valid feature geometries found."
        )

    centroid_lon = sum(p[0] for p in all_pts) / len(all_pts)
    centroid_lat = sum(p[1] for p in all_pts) / len(all_pts)
    utm_epsg = _find_utm_epsg(centroid_lon, centroid_lat)
    logger.info(
        "Auto-converting from %s to %s for meter-based linking "
        "(centroid: %.4f, %.4f)",
        geometry_crs, utm_epsg, centroid_lon, centroid_lat,
    )

    src_crs = pyproj.CRS(geometry_crs)
    dst_crs = pyproj.CRS(utm_epsg)
    transformer = pyproj.Transformer.from_crs(src_crs, dst_crs, always_xy=True)

    def _transform_shapely(geom):
        return shapely_transform(transformer.transform, geom)

    converted_features: list[dict] = []
    for feat in features:
        geom = feat.get("geometry")
        if geom:
            try:
                s = shapely_shape(geom)
                s_trans = _transform_shapely(s)
                feat["geometry"] = s_trans.__geo_interface__
            except Exception as exc:
                logger.warning("CRS conversion failed for feature: %s", exc)
        converted_features.append(feat)

    return utm_epsg, converted_features


def _polygon_iou(geom1: dict, geom2: dict) -> float:
    """Compute real polygon intersection-over-union using shapely.

    Supports Polygon and MultiPolygon. Returns 0 for invalid or empty.
    """
    try:
        s1 = shapely_shape(geom1)
        s2 = shapely_shape(geom2)
        if not s1.is_valid:
            s1 = s1.buffer(0)
        if not s2.is_valid:
            s2 = s2.buffer(0)
        if s1.is_empty or s2.is_empty:
            return 0.0
        intersection = s1.intersection(s2).area
        if intersection <= 0:
            return 0.0
        union = s1.union(s2).area
        return intersection / union if union > 0 else 0.0
    except Exception as exc:
        logger.debug("polygon_iou failed: %s", exc)
        return 0.0


def _polygon_centroid(geometry: dict) -> tuple[float, float] | None:
    """Compute centroid of a Polygon geometry using shapely (in geometry's own CRS)."""
    try:
        s = shapely_shape(geometry)
        if s.is_empty:
            return None
        c = s.centroid
        return (c.x, c.y)
    except Exception:
        return None


# ── Config ──────────────────────────────────────────────────────


def parse_persistence_config(tool_config: dict | None) -> dict:
    """Extract persistence + object_linking + ranking config from tool_config."""
    tc = tool_config or {}
    persistence = tc.get("persistence", {})
    object_linking = tc.get("object_linking", {})
    ranking = tc.get("ranking", {})
    return {
        "persistence": {
            "minimum_occurrences": persistence.get("minimum_occurrences", 2),
            "minimum_ratio": persistence.get("minimum_ratio", 0.67),
            "transient_policy": persistence.get("transient_policy", "retain_as_low_confidence"),
            "require_same_change_type": persistence.get("require_same_change_type", True),
        },
        "object_linking": {
            "minimum_iou": object_linking.get("minimum_iou", 0.30),
            "maximum_centroid_distance_m": object_linking.get("maximum_centroid_distance_m", 50),
            "require_same_change_type": object_linking.get("require_same_change_type", True),
            "require_spatial_intersect": object_linking.get("require_spatial_intersect", False),
        },
        "ranking": {
            "weight_persistence_ratio": ranking.get("weight_persistence_ratio", 0.40),
            "weight_normalized_robust_z": ranking.get("weight_normalized_robust_z", 0.25),
            "weight_normalized_area": ranking.get("weight_normalized_area", 0.20),
            "weight_quality_factor": ranking.get("weight_quality_factor", 0.15),
        },
    }


# ── Per-scene results ────────────────────────────────────────────


def compute_per_scene_change(
    cur_arrays: list[np.ndarray],
    baseline_vh_median: np.ndarray,
    baseline_vh_mad: np.ndarray,
    historical_water_occurrence: np.ndarray,
    history_valid_count: np.ndarray,
    zscore_threshold: float = 3.0,
    stable_land_max: float = 0.2,
    stable_water_min: float = 0.8,
    min_valid_count: int = 3,
) -> list[dict]:
    """
    For each current scene, compute independent change results against
    the SAME history background.

    Returns list of dicts, one per current scene:
      scene_water_mask, scene_robust_zscore,
      scene_water_gain_mask, scene_water_loss_mask,
      scene_sar_anomaly_mask, scene_final_change_mask

    NOTE: classify_multitemporal_change and compute_robust_zscore are
    imported from tools.multi_temporal_background.
    """
    from tools.multi_temporal_background import (
        compute_robust_zscore, classify_multitemporal_change, ensure_no_nan_inf,
    )
    from pipeline.models.baseline_water_sar import predict_vh as sar_water_predict

    results: list[dict] = []
    for i, cur_vh in enumerate(cur_arrays):
        # Robust z-score for this scene vs background
        z = compute_robust_zscore(cur_vh, baseline_vh_median, baseline_vh_mad)
        z[~np.isfinite(cur_vh)] = 0.0
        z = ensure_no_nan_inf(z)

        # Water mask for this scene
        cur_clean = np.where(np.isfinite(cur_vh), cur_vh, -9999.0)
        scene_water, _ = sar_water_predict(cur_clean)

        # Classify change
        change_result = classify_multitemporal_change(
            scene_water, historical_water_occurrence, z,
            history_valid_count,
            zscore_threshold=zscore_threshold,
            stable_land_max=stable_land_max,
            stable_water_min=stable_water_min,
            min_valid_count=min_valid_count,
        )

        results.append({
            "scene_index": i,
            "scene_water_mask": scene_water,
            "scene_robust_zscore": z,
            "scene_water_gain_mask": change_result["water_gain_mask"],
            "scene_water_loss_mask": change_result["water_loss_mask"],
            "scene_sar_anomaly_mask": change_result["sar_anomaly_mask"],
            "scene_final_change_mask": change_result["final_change_mask"],
        })

    return results


# ── Persistence statistics ───────────────────────────────────────


def compute_persistence(
    per_scene_results: list[dict],
    minimum_occurrences: int = 2,
    minimum_ratio: float = 0.67,
) -> dict:
    """
    Compute pixel-level persistence statistics across per_scene final_change_mask.

    Returns:
      persistence_count: uint16 (how many scenes show change at this pixel)
      persistence_ratio: float32 (count / total_current_scenes)
      first_seen_index: uint16 (first scene index with change)
      last_seen_index: uint16 (last scene index with change)
      persistent_change_mask: uint8 (count >= min_occ OR ratio >= min_ratio)
      transient_change_mask: uint8 (count == 1, not persistent)
    """
    n_scenes = len(per_scene_results)
    if n_scenes == 0:
        h, w = 0, 0
        return {
            "persistence_count": np.zeros((h, w), dtype=np.uint16),
            "persistence_ratio": np.zeros((h, w), dtype=np.float32),
            "first_seen_index": np.zeros((h, w), dtype=np.uint16),
            "last_seen_index": np.zeros((h, w), dtype=np.uint16),
            "persistent_change_mask": np.zeros((h, w), dtype=np.uint8),
            "transient_change_mask": np.zeros((h, w), dtype=np.uint8),
            "persistence_status": "no_current_scenes",
            "n_current_scenes": 0,
        }

    # Stack all per-scene final_change_masks
    masks = np.stack([
        r["scene_final_change_mask"].astype(bool) for r in per_scene_results
    ], axis=0)  # (n_scenes, H, W)

    persistence_count = masks.sum(axis=0).astype(np.uint16)
    persistence_ratio = (persistence_count / max(n_scenes, 1)).astype(np.float32)

    # first/last seen
    first_seen = np.full(masks.shape[1:], 0, dtype=np.uint16)
    last_seen = np.full(masks.shape[1:], 0, dtype=np.uint16)
    for i in range(n_scenes):
        m = masks[i]
        not_seen_before = m & (first_seen == 0) & (i == 0)
        first_seen = np.where(m & (first_seen == 0) & (i == 0), i, first_seen)
        # Fix: first_seen should be the first scene where change is detected
        first_seen = np.where(
            m & (first_seen == 0) & (i > 0) & (~masks[:i].any(axis=0)),
            i, first_seen,
        )
        last_seen = np.where(m, i, last_seen)

    # Classify persistent vs transient
    if n_scenes >= 2:
        persistent_mask = (
            (persistence_count >= minimum_occurrences) |
            (persistence_ratio >= minimum_ratio)
        )
        transient_mask = (persistence_count == 1) & ~persistent_mask
        persistence_status = "available"
    else:
        # Single current scene: cannot evaluate persistence
        persistent_mask = np.zeros_like(masks[0], dtype=bool)
        transient_mask = masks[0].astype(bool)
        persistence_status = "unavailable"

    return {
        "persistence_count": persistence_count,
        "persistence_ratio": persistence_ratio,
        "first_seen_index": first_seen.astype(np.uint16),
        "last_seen_index": last_seen.astype(np.uint16),
        "persistent_change_mask": persistent_mask.astype(np.uint8),
        "transient_change_mask": transient_mask.astype(np.uint8),
        "persistence_status": persistence_status,
        "n_current_scenes": n_scenes,
    }


# ── Object linking ───────────────────────────────────────────────


@dataclass
class CandidateObject:
    """A linked candidate object across multiple current scenes.

    A2 lifecycle: proposed (默认) → aggregated / suppressed / superseded
    A3 ranking: candidate_rank_score + score_components
    """
    candidate_id: str
    persistence_status: str  # persistent / transient / uncertain
    change_type: str
    occurrence_count: int
    persistence_ratio: float
    first_seen: int
    last_seen: int
    source_scene_indices: list[int]
    source_asset_refs: list[str]
    source_observation_ids: list[str]
    representative_geometry: dict | None = None
    union_geometry: dict | None = None

    # A2: lifecycle
    lifecycle: str = "proposed"  # proposed / suppressed / superseded
    suppression_reason: str | None = None
    supersedes: str | None = None
    superseded_by: str | None = None

    # A2: modality
    source_modality: str = "SAR_C"
    median_area_m2: float = 0.0
    maximum_area_m2: float = 0.0
    robust_z_mean: float = 0.0
    robust_z_max: float = 0.0
    water_occurrence_mean: float = 0.0
    candidate_rank_score: float = 0.0
    score_components: dict = field(default_factory=dict)


def _polygon_area_m2(geometry: dict, pixel_area_m2: float = 100.0) -> float:
    """Approximate area from pixel count stored in properties, or pixel_area * count."""
    # Area is stored in feature properties.area_m2 by polygonize
    # If not available, approximate from geometry extent using shapely
    if not geometry:
        return 0.0
    try:
        s = shapely_shape(geometry)
        return s.area
    except Exception:
        return 0.0


def link_objects_across_time(
    per_scene_features: list[list[dict]],
    per_scene_asset_refs: list[str],
    min_iou: float = 0.30,
    max_centroid_distance_m: float = 50.0,
    require_same_change_type: bool = True,
    require_spatial_intersect: bool = False,
    geometry_crs: str | None = None,
    pixel_area_m2: float = 100.0,
    n_scene_total: int = 0,
    minimum_occurrences: int = 2,
    minimum_ratio: float = 0.67,
    persistence_status: str = "available",
    n_current_scenes: int = 0,
) -> list[CandidateObject]:
    """
    Link polygons across current scenes into candidate objects.

    CRS discipline (A0):
      - geometry_crs is REQUIRED.
      - EPSG:4326 and other geographic CRS are auto-converted to UTM for meter-based linking.
      - Distances are computed in the working (projected) CRS — always in meters.
      - Polygon IoU uses shapely real polygon intersection (NOT bounds approximation).

    Rules:
      - change_type must be same (if require_same_change_type)
      - polygon_iou >= min_iou
        OR
        centroid_distance_m <= max_centroid_distance_m
          AND (if require_spatial_intersect, geometries must intersect)

    Returns:
      List of CandidateObject with stable candidate_id.
    """
    # ── Step 0: Validate and convert CRS ──
    effective_crs, features_prepped = _check_or_convert_crs(
        geometry_crs, sum(per_scene_features, [])
    )
    # Re-split into per-scene lists
    scene_offsets: list[int] = []
    offset = 0
    for si, feats in enumerate(per_scene_features):
        scene_offsets.append(offset)
        offset += len(feats)
    # flat features_prepped is in same scene order
    per_scene_features_crs = []
    for si, feats in enumerate(per_scene_features):
        start = scene_offsets[si]
        end = start + len(feats)
        per_scene_features_crs.append(features_prepped[start:end])

    # ── Step 1: Build per-scene polygon records ──
    records: list[dict] = []
    for si, feats in enumerate(per_scene_features_crs):
        for fi, feat in enumerate(feats):
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            area = props.get("area_m2", 0.0)
            ct = props.get("change_type", "unknown")
            centroid = _polygon_centroid(geom)
            records.append({
                "scene_idx": si,
                "feat_idx": fi,
                "geometry": geom,
                "area": float(area),
                "change_type": ct,
                "centroid": centroid,
                "robust_z_mean": float(props.get("robust_z_mean", 0)),
                "robust_z_max": float(props.get("robust_z_max", 0)),
                "water_occurrence_mean": float(props.get("water_occurrence_mean", 0)),
                "pixel_count": props.get("pixel_count", 0),
            })

    if not records:
        return []

    # ── Step 2: Union-Find grouping ──
    parent = list(range(len(records)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # ── Step 3: Compare all cross-scene pairs ──
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            ri, rj = records[i], records[j]
            if ri["scene_idx"] == rj["scene_idx"]:
                continue  # same scene, no cross-time linking
            if require_same_change_type and ri["change_type"] != rj["change_type"]:
                continue

            # Real polygon IoU using shapely
            geom_i = ri["geometry"]
            geom_j = rj["geometry"]
            iou_val = _polygon_iou(geom_i, geom_j) if geom_i and geom_j else 0.0

            # Centroid distance in meters (working CRS is projected)
            centroid_match = False
            if ri["centroid"] and rj["centroid"]:
                dx = ri["centroid"][0] - rj["centroid"][0]
                dy = ri["centroid"][1] - rj["centroid"][1]
                dist = np.sqrt(dx**2 + dy**2)  # meters (projected CRS)
                if dist <= max_centroid_distance_m:
                    if require_spatial_intersect:
                        # Also require spatial overlap
                        if iou_val > 0:
                            centroid_match = True
                    else:
                        centroid_match = True

            if iou_val >= min_iou or centroid_match:
                union(i, j)

    # ── Step 4: Group records by root ──
    groups: dict[int, list[int]] = {}
    for i in range(len(records)):
        root = find(i)
        groups.setdefault(root, []).append(i)

    # ── Step 5: Build candidate objects ──
    candidates: list[CandidateObject] = []
    for group_root, member_indices in groups.items():
        members = [records[mi] for mi in member_indices]
        scene_idxs = sorted(set(m["scene_idx"] for m in members))
        occurrence = len(scene_idxs)
        total_scenes = max(n_current_scenes or n_scene_total, 1)
        ratio = occurrence / total_scenes

        # Change types in group
        change_types = set(m["change_type"] for m in members)
        if len(change_types) > 1:
            ct_repr = "mixed"
            status = "uncertain"
        else:
            ct_repr = list(change_types)[0]
            if persistence_status == "unavailable":
                status = "transient"
            elif occurrence >= minimum_occurrences or ratio >= minimum_ratio:
                status = "persistent"
            else:
                status = "transient"

        if persistence_status == "available" and occurrence == 1 and n_current_scenes >= 2:
            status = "transient"

        # Source info
        source_refs = [per_scene_asset_refs[si] for si in scene_idxs
                       if si < len(per_scene_asset_refs)]

        # Areas
        areas = [m["area"] for m in members]
        median_area = float(np.median(areas)) if areas else 0.0
        max_area = float(np.max(areas)) if areas else 0.0

        # z-score / water_occurrence stats
        z_means = [m["robust_z_mean"] for m in members]
        z_maxes = [m["robust_z_max"] for m in members]
        wo_means = [m["water_occurrence_mean"] for m in members]

        # Representative: use the largest area geometry
        largest = max(members, key=lambda m: m["area"])
        rep_geom = largest["geometry"]
        union_geom = rep_geom  # simplified; could be cascaded union

        # Stable candidate_id: hash of scene indices + change_type + centroid + crs
        if largest["centroid"]:
            id_str = (
                f"{'-'.join(str(s) for s in scene_idxs)}"
                f"|{ct_repr}"
                f"|{largest['centroid'][0]:.4f},{largest['centroid'][1]:.4f}"
                f"|{effective_crs}"
            )
        else:
            id_str = f"{'-'.join(str(s) for s in scene_idxs)}|{ct_repr}|{len(members)}|{effective_crs}"
        cid = f"cand-{hashlib.md5(id_str.encode()).hexdigest()[:12]}"

        candidates.append(CandidateObject(
            candidate_id=cid,
            persistence_status=status,
            change_type=ct_repr,
            occurrence_count=occurrence,
            persistence_ratio=round(ratio, 4),
            first_seen=scene_idxs[0],
            last_seen=scene_idxs[-1],
            source_scene_indices=scene_idxs,
            source_asset_refs=source_refs,
            source_observation_ids=[],
            representative_geometry=rep_geom,
            union_geometry=union_geom,
            median_area_m2=median_area,
            maximum_area_m2=max_area,
            robust_z_mean=round(float(np.mean(z_means)) if z_means else 0.0, 4),
            robust_z_max=round(float(np.max(z_maxes)) if z_maxes else 0.0, 4),
            water_occurrence_mean=round(float(np.mean(wo_means)) if wo_means else 0.0, 4),
            candidate_rank_score=0.0,
            score_components={},
        ))

    return candidates


# ── Candidate ranking ────────────────────────────────────────────


def rank_candidates(
    candidates: list[CandidateObject],
    history_scene_count: int = 0,
    current_scene_count: int = 0,
    weights: dict | None = None,
) -> list[CandidateObject]:
    """
    Compute candidate_rank_score for each candidate.

    A3 重构:
      - persistence_ratio + quality_factor 不再近似重复
      - quality_factor 使用正交质量: occurrence 覆盖之外的质量
      - score_type: within_run_ranking (非概率)
      - 跨运行不可比: 使用运行内 max 归一化

    score = w_persistence * persistence_ratio
          + w_robust_z * normalized_robust_z
          + w_area * normalized_area
          + w_quality * quality_factor

    score_type = within_run_ranking — 仅在本次运行内可比。
    """
    if not candidates:
        return candidates

    w = weights or {
        "weight_persistence_ratio": 0.40,
        "weight_normalized_robust_z": 0.25,
        "weight_normalized_area": 0.20,
        "weight_quality_factor": 0.15,
    }

    # Normalize robust_z and area to [0, 1]
    all_z = [c.robust_z_max for c in candidates]
    all_area = [c.median_area_m2 for c in candidates]
    max_z = max(all_z) if all_z and max(all_z) > 0 else 1.0
    max_area = max(all_area) if all_area and max(all_area) > 0 else 1.0

    for c in candidates:
        persistence_ratio = c.persistence_ratio
        norm_z = min(c.robust_z_max / max_z, 1.0) if max_z > 0 else 0.0
        norm_area = min(c.median_area_m2 / max_area, 1.0) if max_area > 0 else 0.0

        # A3: quality_factor 使用正交质量指标，不再近似 persistence
        # 基于 pixel_count 合理性和水出现率稳定性
        # 如果 pixel_count > 0, 有效像元占比高 => 质量好
        quality_factor = 0.5  # 默认中等
        if c.water_occurrence_mean > 0:
            # 水出现率适中 (0.2-0.8) 的检测更可靠 — 排除稳定水体和陆地
            quality_factor = 1.0 - abs(c.water_occurrence_mean - 0.5) * 2.0
            quality_factor = max(0.0, min(1.0, quality_factor))
        # robust_z_mean 越大说明变化越显著, 但也要有上限
        z_quality = min(abs(c.robust_z_mean) / 10.0, 1.0) if c.robust_z_mean else 0.5
        quality_factor = (quality_factor + z_quality) / 2.0

        score = (
            w.get("weight_persistence_ratio", 0.40) * persistence_ratio
            + w.get("weight_normalized_robust_z", 0.25) * norm_z
            + w.get("weight_normalized_area", 0.20) * norm_area
            + w.get("weight_quality_factor", 0.15) * quality_factor
        )

        c.candidate_rank_score = round(float(score), 6)
        c.score_components = {
            "persistence_ratio": {
                "raw": round(float(persistence_ratio), 4),
                "contribution": round(float(w.get("weight_persistence_ratio", 0.40) * persistence_ratio), 6),
            },
            "normalized_robust_z": {
                "raw": round(float(norm_z), 4),
                "contribution": round(float(w.get("weight_normalized_robust_z", 0.25) * norm_z), 6),
            },
            "normalized_area": {
                "raw": round(float(norm_area), 4),
                "contribution": round(float(w.get("weight_normalized_area", 0.20) * norm_area), 6),
            },
            "quality_factor": {
                "raw": round(float(quality_factor), 4),
                "contribution": round(float(w.get("weight_quality_factor", 0.15) * quality_factor), 6),
                "description": "正交质量: water_occurrence_stability + robust_z_confidence",
            },
            "score_type": "within_run_ranking",
            "disclaimer": "运行内排名，非绝对概率；跨运行不可直接比较",
        }

    # Sort by score descending
    candidates.sort(key=lambda c: c.candidate_rank_score, reverse=True)
    return candidates


# ── Candidate to GeoJSON + JSON ──────────────────────────────────


def candidates_to_geojson(candidates: list[CandidateObject]) -> list[dict]:
    """Convert candidate objects to GeoJSON FeatureCollection (EPSG:4326)."""
    features = []
    for c in candidates:
        geom = c.representative_geometry
        if not geom:
            continue
        props = {
            "candidate_id": c.candidate_id,
            "persistence_status": c.persistence_status,
            "change_type": c.change_type,
            "occurrence_count": c.occurrence_count,
            "persistence_ratio": c.persistence_ratio,
            "first_seen": c.first_seen,
            "last_seen": c.last_seen,
            "source_scene_indices": c.source_scene_indices,
            "source_asset_refs": c.source_asset_refs,
            "source_observation_ids": c.source_observation_ids,
            "median_area_m2": c.median_area_m2,
            "maximum_area_m2": c.maximum_area_m2,
            "robust_z_mean": c.robust_z_mean,
            "robust_z_max": c.robust_z_max,
            "water_occurrence_mean": c.water_occurrence_mean,
            "candidate_rank_score": c.candidate_rank_score,
            "score_components": c.score_components,
            "score_type": "within_run_ranking",
            # A2 lifecycle
            "lifecycle": c.lifecycle,
            "suppression_reason": c.suppression_reason,
            "supersedes": c.supersedes,
            "superseded_by": c.superseded_by,
            "source_modality": c.source_modality,
        }
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": props,
        })
    return features


def candidates_to_json(candidates: list[CandidateObject],
                       history_scene_count: int = 0,
                       current_scene_count: int = 0) -> dict:
    """Convert candidate objects to detailed JSON with full time series."""
    return {
        "schema_version": "candidate.v0.2",
        "history_scene_count": history_scene_count,
        "current_scene_count": current_scene_count,
        "total_candidates": len(candidates),
        "score_type": "within_run_ranking",
        "ranking_disclaimer": "运行内排名，非绝对概率；跨运行不可直接比较",
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "persistence_status": c.persistence_status,
                "change_type": c.change_type,
                "occurrence_count": c.occurrence_count,
                "persistence_ratio": c.persistence_ratio,
                "first_seen": c.first_seen,
                "last_seen": c.last_seen,
                "source_scene_indices": c.source_scene_indices,
                "source_asset_refs": c.source_asset_refs,
                "source_observation_ids": c.source_observation_ids,
                "median_area_m2": c.median_area_m2,
                "maximum_area_m2": c.maximum_area_m2,
                "robust_z_mean": c.robust_z_mean,
                "robust_z_max": c.robust_z_max,
                "water_occurrence_mean": c.water_occurrence_mean,
                "candidate_rank_score": c.candidate_rank_score,
                "score_components": c.score_components,
                "score_type": "within_run_ranking",
                "lifecycle": c.lifecycle,
                "suppression_reason": c.suppression_reason,
                "supersedes": c.supersedes,
                "superseded_by": c.superseded_by,
                "source_modality": c.source_modality,
                "representative_geometry": c.representative_geometry,
                "union_geometry": c.union_geometry,
            }
            for c in candidates
        ],
    }