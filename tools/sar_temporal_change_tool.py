"""
RS-01B-1 — SarTemporalChangeTool (质量门禁版)

Sentinel-1 SAR 双时相变化检测工具。

RS-01A.2 修复:
- CRS 统一：栅格保留目标投影，GeoJSON+Observation→EPSG:4326, geometry_crs
- AssetRegistry 管理全部派生资产 (water_t1/t2, change_mask, candidates, report)
- artifact_refs 可反向解析到真实文件
- 增强绑定校验: before≠after, sequence_index 防重/连续, 未声明 role 拒绝
- 异常→FAILED 结构化 (stage/error_type/message)
- 输出目录: output_dir/run_id/task_id/

RS-01B-1 新增:
- SarMetadata 解析
- 输入质量校验 (同轨/极化/空间/波段)
- SarValidationPolicy (strict/warn/trust)
- QualityReport 完整输出
"""

import json
import sys
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime
import pyproj

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT / "competition" / "spikes" / "chongqing_rs_demo"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

import numpy as np

from core.schemas.contracts import (
    ExecutionStatus, TaskType, ObservationType, ScoreType, AssetRole, Modality,
)
from core.schemas.contracts.asset import AssetRef, SpatialMetadata
from core.schemas.contracts.task import (
    InferenceTask, TaskSpec, RunContext, TaskAssetBinding,
)
from core.schemas.contracts.perception import (
    PerceptionResult, Observation, QualityReport,
)
from core.schemas.contracts.sar_metadata import SarMetadata
from core.schemas.contracts.validation_policy import (
    SarValidationPolicy, PolicyMode,
)
from core.protocols.perception_tool import PerceptionTool
from core.protocols.asset_resolver import AssetRegistry
from tools.sar_quality_validator import (
    compute_input_quality, validate_sar_input, ValidationResult,
)
from pipeline.io.reader import read_geotiff
from pipeline.io.writer import write_geotiff, write_geojson
from pipeline.processing.preprocessor import reproject_to_target, resample_to_grid
from pipeline.models.baseline_water_sar import predict_vh as sar_water_predict
from pipeline.detection.change import detect_change
from pipeline.postprocessing.polygonize import polygonize_change_mask
from tools.multi_temporal_background import (
    compute_median_background, compute_mad, compute_valid_count,
    compute_water_occurrence, compute_robust_zscore,
    classify_multitemporal_change, ensure_no_nan_inf,
)
from tools.persistence_background import (
    parse_persistence_config, compute_per_scene_change, compute_persistence,
    link_objects_across_time, rank_candidates,
    candidates_to_geojson, candidates_to_json,
)


def _sha256_hex(path: Path) -> str:
    """返回完整 64 字符 SHA256 十六进制串。"""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


_CRS_TRANSFORM_CACHE: dict[str, pyproj.Transformer] = {}


def _get_transformer(src_crs: str, dst_crs: str = "EPSG:4326") -> pyproj.Transformer:
    """缓存并返回 pyproj.Transformer。"""
    key = f"{src_crs}->{dst_crs}"
    if key not in _CRS_TRANSFORM_CACHE:
        _CRS_TRANSFORM_CACHE[key] = pyproj.Transformer.from_crs(
            src_crs, dst_crs, always_xy=True,
        )
    return _CRS_TRANSFORM_CACHE[key]


def _reproject_coords(coords: list, transformer: pyproj.Transformer) -> list:
    """重投影坐标列表。"""
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    lons, lats = transformer.transform(xs, ys)
    return [[float(lon), float(lat)] for lon, lat in zip(lons, lats)]


def _to_epsg4326(features: list[dict], src_crs: str) -> list[dict]:
    """将 GeoJSON features 的 geometry 坐标从 src_crs 精确转为 EPSG:4326。"""
    if not features:
        return features
    crs_str = str(src_crs).upper()
    if crs_str == "EPSG:4326":
        return features
    transformer = _get_transformer(crs_str)
    result = []
    for feat in features:
        geom = feat.get("geometry")
        if not geom:
            result.append(feat)
            continue
        gtype = geom.get("type")
        if gtype == "Polygon":
            new_coords = [_reproject_coords(ring, transformer) for ring in geom["coordinates"]]
            new_feat = dict(feat)
            new_feat["geometry"] = {"type": "Polygon", "coordinates": new_coords}
            result.append(new_feat)
        elif gtype == "MultiPolygon":
            new_polys = []
            for poly in geom["coordinates"]:
                new_polys.append([_reproject_coords(ring, transformer) for ring in poly])
            new_feat = dict(feat)
            new_feat["geometry"] = {"type": "MultiPolygon", "coordinates": new_polys}
            result.append(new_feat)
        elif gtype == "Point":
            new_coords = _reproject_coords([geom["coordinates"]], transformer)[0]
            new_feat = dict(feat)
            new_feat["geometry"] = {"type": "Point", "coordinates": new_coords}
            result.append(new_feat)
        else:
            new_feat = dict(feat)
            result.append(new_feat)
    return result


def _convert_candidates_to_4326(
    candidates: list, src_crs
) -> list:
    """Convert CandidateObject geometries from src_crs to EPSG:4326."""
    import copy
    from pyproj import CRS, Transformer

    crs_str = str(src_crs).upper()
    if crs_str == "EPSG:4326" or not candidates:
        return candidates

    transformer = Transformer.from_crs(CRS(crs_str), CRS("EPSG:4326"), always_xy=True)

    def _reproject_geom(geom: dict | None) -> dict | None:
        if not geom:
            return None
        gtype = geom.get("type")
        if gtype == "Polygon":
            new_coords = []
            for ring in geom["coordinates"]:
                xs, ys = zip(*ring)
                lons, lats = transformer.transform(xs, ys)
                new_coords.append([[float(lon), float(lat)] for lon, lat in zip(lons, lats)])
            return {"type": "Polygon", "coordinates": new_coords}
        elif gtype == "MultiPolygon":
            new_polys = []
            for poly in geom["coordinates"]:
                new_poly = []
                for ring in poly:
                    xs, ys = zip(*ring)
                    lons, lats = transformer.transform(xs, ys)
                    new_poly.append([[float(lon), float(lat)] for lon, lat in zip(lons, lats)])
                new_polys.append(new_poly)
            return {"type": "MultiPolygon", "coordinates": new_polys}
        return geom

    result = []
    for c in candidates:
        new_c = copy.copy(c)
        new_c.representative_geometry = _reproject_geom(c.representative_geometry)
        new_c.union_geometry = _reproject_geom(c.union_geometry)
        result.append(new_c)

    return result


def _failed(
    result_id: str, task: InferenceTask, spec: TaskSpec, context: RunContext,
    stage: str, error_type: str, message: str, started_at: str,
) -> PerceptionResult:
    return PerceptionResult(
        perception_result_id=result_id,
        inference_task_ref=task.task_id,
        task_spec_ref=task.task_spec_ref,
        run_id=context.run_id,
        status=ExecutionStatus.FAILED,
        diagnostics={
            "stage": stage, "error_type": error_type, "message": message,
        },
        started_at=started_at, finished_at=datetime.now().isoformat(),
    )


def _is_multi_temporal_mode(spec: TaskSpec) -> bool:
    """检测是否为多时相模式：input_slots 中声明了 HISTORY 或 CURRENT 角色。"""
    declared = {s.role for s in spec.input_slots}
    return AssetRole.HISTORY in declared or AssetRole.CURRENT in declared


def _parse_mt_policy(context: RunContext) -> dict:
    """从 RunContext.tool_config 提取多时相策略参数。"""
    tc = context.tool_config or {}
    mt = tc.get("multi_temporal", {})
    return {
        "insufficient_history_policy": mt.get("insufficient_history_policy", "fallback_to_pair"),
        "min_history_scenes": mt.get("min_history_scenes", 6),
        "max_history_scenes": mt.get("max_history_scenes", 24),
        "min_current_scenes": mt.get("min_current_scenes", 1),
        "max_current_scenes": mt.get("max_current_scenes", 3),
        "valid_count_threshold": mt.get("valid_count_threshold", 3),
        "mad_epsilon": mt.get("mad_epsilon", 0.001),
        "zscore_threshold": mt.get("zscore_threshold", 3.0),
        "water_occurrence_threshold": mt.get("water_occurrence_threshold", 0.3),
        "min_area_m2": mt.get("min_area_m2", 500),
    "pixel_area_m2": mt.get("pixel_area_m2", 100),
    "stable_land_max": mt.get("stable_land_max", 0.2),
    "stable_water_min": mt.get("stable_water_min", 0.8),
    "persistence_config": parse_persistence_config(context.tool_config),
}


def _write_synth_pair(path: Path, vv: np.ndarray, vh: np.ndarray,
                       crs, transform) -> Path:
    """写入合成 SAR 对 (用于 pair_fallback)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.stack([vv.astype(np.float32), vh.astype(np.float32)])
    import rasterio
    H, W = vh.shape
    with rasterio.open(path, "w", driver="GTiff", height=H, width=W, count=2,
                       dtype="float32", crs=crs, transform=transform, nodata=-9999.0,
                       compress="lzw") as dst:
        dst.write(data[0], 1)
        dst.write(data[1], 2)
        dst.set_band_description(1, "vv")
        dst.set_band_description(2, "vh")
    return path


class SarTemporalChangeTool(PerceptionTool):
    """Sentinel-1 SAR 双时相变化检测工具 (RS-01A.2 + RS-01B-2 多时相)。"""

    def __init__(self, registry: AssetRegistry | None = None):
        self._registry = registry

    def set_registry(self, registry: AssetRegistry):
        self._registry = registry

    # ── 绑定校验 ────────────────────────────────────────────────

    def _validate_bindings(self, task: InferenceTask, spec: TaskSpec) -> list[str]:
        """增强绑定校验: sequence_index, before≠after, 未声明 role。"""
        errors: list[str] = []

        # 1. before ≠ after (不得引用同一资产)
        before_ids = {b.asset_ref for b in task.asset_bindings if b.role == AssetRole.BEFORE}
        after_ids = {b.asset_ref for b in task.asset_bindings if b.role == AssetRole.AFTER}
        same = before_ids & after_ids
        if same:
            errors.append(f"before/after 不得引用同一资产: {same}")

        # 2. 未声明 role 拒绝
        declared_roles = {s.role for s in spec.input_slots}
        for b in task.asset_bindings:
            if b.role not in declared_roles:
                errors.append(f"role={b.role.value} 未在 input_slots 中声明")

        # 3. sequence_index 防重 + 连续性 (仅 max_items > 1 的角色强制)
        for role in {b.role for b in task.asset_bindings}:
            bindings = [b for b in task.asset_bindings if b.role == role]
            slot = next((s for s in spec.input_slots if s.role == role), None)
            max_items = slot.max_items if slot else 999
            if len(bindings) <= 1 and max_items <= 1:
                continue  # 单绑定 + 单槽位: sequence_index 可选
            indices = [b.sequence_index for b in bindings]
            if any(i is None for i in indices):
                errors.append(f"role={role.value} 多地绑定但存在缺失 sequence_index 的绑定")
                continue
            if len(set(indices)) != len(indices):
                errors.append(f"role={role.value} sequence_index 重复: {indices}")
            expected = list(range(min(indices), min(indices) + len(indices)))
            if indices != expected:
                errors.append(f"role={role.value} sequence_index 不连续: {indices}, 期望 {expected}")

        return errors

    def validate_spec(self, task: InferenceTask, spec: TaskSpec) -> list[str]:
        errors: list[str] = []
        expected = f"{spec.task_spec_id}@{spec.version}"
        if task.task_spec_ref != expected:
            errors.append(f"task_spec_ref 不匹配: 期望 {expected}, 收到 {task.task_spec_ref}")
        if spec.task_type != TaskType.TEMPORAL_CHANGE_DETECTION:
            errors.append(f"task_type 不支持: {spec.task_type}")
        for slot in spec.input_slots:
            matched = [b for b in task.asset_bindings if b.role == slot.role]
            if len(matched) < slot.min_items:
                errors.append(f"role={slot.role.value} 数量不足: 需要 {slot.min_items}, 实际 {len(matched)}")
            if slot.max_items > 0 and len(matched) > slot.max_items:
                errors.append(f"role={slot.role.value} 数量过多: 最多 {slot.max_items}, 实际 {len(matched)}")
        if self._registry:
            for b in task.asset_bindings:
                try:
                    asset = self._registry.resolve(b.asset_ref)
                    slot = next((s for s in spec.input_slots if s.role == b.role), None)
                    if slot and asset.modality not in slot.modalities:
                        errors.append(
                            f"asset {b.asset_ref} modality {asset.modality.value} "
                            f"不在 {[m.value for m in slot.modalities]}"
                        )
                except KeyError:
                    errors.append(f"asset_id 未注册: {b.asset_ref}")
        errors.extend(self._validate_bindings(task, spec))
        return errors

    # ── 多时相解析 ──────────────────────────────────────────────

    def _resolve_multi_temporal(
        self, task: InferenceTask, spec: TaskSpec,
    ) -> tuple[list[TaskAssetBinding], list[TaskAssetBinding]]:
        """解析多时相资产绑定，按 sequence_index + acquisition_time 排序。

        Returns:
            (history_bindings, current_bindings) - 排序后的绑定列表
        """
        history = [b for b in task.asset_bindings if b.role == AssetRole.HISTORY]
        current = [b for b in task.asset_bindings if b.role == AssetRole.CURRENT]

        def _sort_key(b: TaskAssetBinding) -> str:
            """排序键: sequence_index 优先，然后是 acquisition_time。"""
            seq = b.sequence_index if b.sequence_index is not None else 0
            try:
                ref = self._registry.resolve(b.asset_ref)
                t = ref.acquisition_time or ""
            except KeyError:
                t = ""
            return f"{seq:04d}_{t}"

        history.sort(key=_sort_key)
        current.sort(key=_sort_key)
        return history, current

    # ── 主运行 ──────────────────────────────────────────────────

    def _execute_multi_temporal(
        self, task: InferenceTask, spec: TaskSpec, context: RunContext,
        result_id: str, started_at: str, policy: SarValidationPolicy,
    ) -> PerceptionResult:
        """多时相稳健背景变化检测 (RS-01B-2，验收版)。"""
        mt_policy = _parse_mt_policy(context)

        # 1. 解析资产
        history_bindings, current_bindings = self._resolve_multi_temporal(task, spec)
        n_history = len(history_bindings)
        n_current = len(current_bindings)

        # 2. 历史景数检查
        if n_history < mt_policy["min_history_scenes"]:
            pc = mt_policy["insufficient_history_policy"]
            if pc == "no_data":
                return PerceptionResult(
                    perception_result_id=result_id,
                    inference_task_ref=task.task_id,
                    task_spec_ref=task.task_spec_ref,
                    run_id=context.run_id,
                    status=ExecutionStatus.NO_DATA,
                    diagnostics={
                        "stage": "history_check",
                        "error_type": "insufficient_history",
                        "message": f"历史景数 {n_history} < {mt_policy['min_history_scenes']} (policy=no_data)",
                    },
                    started_at=started_at,
                    finished_at=datetime.now().isoformat(),
                )
            # pair_fallback: 从最后历史 + 当前中位数合成 before/after
            try:
                last_hist_binding = history_bindings[-1]
                if n_current == 0:
                    return _failed(result_id, task, spec, context,
                                   "pair_fallback", "no_current",
                                   "pair_fallback 需要至少 1 景当前", started_at)
                # 合成 current_median → 写出临时文件，注册为 after
                import tempfile
                tmp_dir = Path(tempfile.mkdtemp(prefix="mt_fb_"))
                cur_arrays = []
                for b in current_bindings:
                    asset = self._registry.resolve(b.asset_ref)
                    ri = read_geotiff(asset.uri, bands=["vv", "vh"])
                    ri = reproject_to_target(ri)
                    vh = ri.array[ri.bands.index("vh")]
                    vh[np.isclose(vh, ri.nodata, atol=1e-3)] = np.nan
                    cur_arrays.append(vh)
                if cur_arrays:
                    cur_median = np.nanmedian(np.stack(cur_arrays, axis=0), axis=0).astype(np.float32)
                    cur_median = np.where(np.isfinite(cur_median), cur_median, ri.nodata)
                    vv_median = cur_median + 3.0  # 近似 VV
                    fake_after_path = tmp_dir / "pair_fallback_after.tif"
                    _write_synth_pair(fake_after_path, vv_median, cur_median, ri.crs, ri.transform)
                    fake_after_ref = AssetRef(
                        asset_id=f"{task.task_id}_pair_fallback_after",
                        uri=str(fake_after_path),
                        media_type="image/tiff; application=geotiff",
                        modality=Modality.SAR,
                        spatial=SpatialMetadata(reliability="georeferenced", crs=str(ri.crs).upper(),
                                                 width=ri.width, height=ri.height),
                        bands=["vv", "vh"],
                    )
                    self._registry.register(fake_after_ref)
                    # 构造 before binding: 使用最后一个历史场景
                    # 构造 after binding: 使用合成的 after
                    fb_before = TaskAssetBinding(
                        asset_ref=last_hist_binding.asset_ref, role=AssetRole.BEFORE,
                        sequence_index=last_hist_binding.sequence_index,
                    )
                    fb_after = TaskAssetBinding(
                        asset_ref=fake_after_ref.asset_id, role=AssetRole.AFTER,
                    )
                    return self._execute_pair(task, spec, context, result_id, started_at,
                                               policy, fb_before, fb_after, actual_mode="pair_fallback")
            except Exception as e:
                return _failed(result_id, task, spec, context,
                               "pair_fallback", type(e).__name__, str(e), started_at)

        # 3. 质量门禁 + 场景结果聚合
        scene_quality: list[dict] = []
        accepted = 0
        rejected = 0
        warned = 0
        accepted_history = 0
        accepted_current = 0
        rejected_history = 0
        rejected_current = 0
        warned_history = 0
        warned_current = 0
        dropped_refs: list[str] = []
        all_warnings: list[str] = []
        all_bindings = history_bindings + current_bindings
        min_valid_pixel_ratio = 1.0

        ref_binding = history_bindings[0]
        try:
            ref_asset = self._registry.resolve(ref_binding.asset_ref)
        except KeyError as e:
            return _failed(result_id, task, spec, context,
                           "resolve_reference", "missing_asset", str(e), started_at)

        for i, b in enumerate(all_bindings):
            sq = {"binding_index": i, "asset_ref": b.asset_ref, "role": b.role.value,
                  "accepted": True, "rejected": False, "reason": None, "warnings": []}
            is_history = b.role == AssetRole.HISTORY
            try:
                scene_asset = self._registry.resolve(b.asset_ref)
            except KeyError as e:
                sq["accepted"] = False; sq["rejected"] = True
                sq["reason"] = f"missing_asset: {e}"
                rejected += 1
                if is_history: rejected_history += 1
                else: rejected_current += 1
                dropped_refs.append(b.asset_ref)
                scene_quality.append(sq); continue
            if b.asset_ref == ref_binding.asset_ref:
                sq["role"] = "history_ref"
                scene_quality.append(sq)
                accepted += 1
                accepted_history += 1
                continue

            try:
                scene_data = read_geotiff(scene_asset.uri, bands=["vv", "vh"])
            except Exception as e:
                sq["accepted"] = False; sq["rejected"] = True
                sq["reason"] = f"read_error: {e}"
                rejected += 1
                if is_history: rejected_history += 1
                else: rejected_current += 1
                dropped_refs.append(b.asset_ref)
                scene_quality.append(sq); continue

            # 参考场景自检
            try:
                ref_data = read_geotiff(ref_asset.uri, bands=["vv", "vh"])
                # 检查 VV/VH 波段存在
                assert "vv" in ref_data.bands and "vh" in ref_data.bands, \
                    f"参考场景缺少 VV/VH 波段"
                # 检查非空、非常数
                ref_vh = ref_data.array[ref_data.bands.index("vh")]
                assert ref_vh.size > 0, "参考场景 VH 为空"
                ref_valid = np.isfinite(ref_vh) & ~np.isclose(ref_vh, ref_data.nodata, atol=1e-3)
                assert ref_valid.sum() > 0, "参考场景无有效像素"
                vh_range = np.nanmax(ref_vh) - np.nanmin(ref_vh)
                assert vh_range > 0.01, f"参考场景 VH 接近常数 (range={vh_range:.3f})"
            except Exception as e:
                sq["accepted"] = False; sq["rejected"] = True
                sq["reason"] = f"ref_self_check: {e}"
                rejected += 1
                if is_history: rejected_history += 1
                else: rejected_current += 1
                dropped_refs.append(b.asset_ref)
                scene_quality.append(sq); continue

            if policy.mode != PolicyMode.TRUST:
                meta_ref = SarMetadata.from_asset_ref(ref_asset, ref_asset.uri)
                meta_scene = SarMetadata.from_asset_ref(scene_asset, scene_asset.uri)
                qm = compute_input_quality(ref_data.array, scene_data.array,
                                            ref_data.bands, scene_data.bands)
                min_valid_pixel_ratio = min(min_valid_pixel_ratio,
                                             qm.get("valid_pixel_ratio", 0.0))
                validation = validate_sar_input(meta_ref, meta_scene,
                                                 ref_data.bands, scene_data.bands,
                                                 qm, policy, ref_data.width, ref_data.height,
                                                 scene_data.width, scene_data.height)
                if validation.rejected:
                    sq["accepted"] = False; sq["rejected"] = True
                    sq["reason"] = validation.rejection_reason
                    sq["quality"] = {k: v for k, v in qm.items()
                                     if not isinstance(v, tuple)}
                    rejected += 1
                    if is_history: rejected_history += 1
                    else: rejected_current += 1
                    dropped_refs.append(b.asset_ref)
                if validation.quality.recommendations:
                    sq["warnings"] = validation.quality.recommendations
                    if not validation.rejected:
                        warned += 1
                        if is_history: warned_history += 1
                        else: warned_current += 1
                    all_warnings.extend(validation.quality.recommendations)
            scene_quality.append(sq)
            if sq["accepted"]:
                accepted += 1
                if is_history: accepted_history += 1
                else: accepted_current += 1

        if rejected > 0 and policy.rejects_on():
            return PerceptionResult(
                perception_result_id=result_id, inference_task_ref=task.task_id,
                task_spec_ref=task.task_spec_ref, run_id=context.run_id,
                status=ExecutionStatus.INVALID_INPUT,
                diagnostics={
                    "stage": "quality_gate",
                    "accepted": accepted, "rejected": rejected,
                    "accepted_history": accepted_history,
                    "accepted_current": accepted_current,
                    "rejected_history": rejected_history,
                    "rejected_current": rejected_current,
                    "warned": warned,
                    "warned_history": warned_history,
                    "warned_current": warned_current,
                    "dropped_asset_refs": dropped_refs,
                    "warnings": all_warnings,
                    "min_valid_pixel_ratio": min_valid_pixel_ratio,
                    "scene_quality": scene_quality,
                },
                started_at=started_at, finished_at=datetime.now().isoformat(),
            )

        # 4-5. 构建历史/当前堆栈 (统一到 ref_raster 网格)
        try:
            ref_raster = reproject_to_target(read_geotiff(ref_asset.uri, bands=["vv", "vh"]))
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "reproject_reference", type(e).__name__, str(e), started_at)
        vh_idx = ref_raster.bands.index("vh")

        def _read_to_stack(bindings, ref_rast):
            arrays, water_masks, valid_masks = [], [], []
            for b in bindings:
                try:
                    asset_obj = self._registry.resolve(b.asset_ref)
                    ri = read_geotiff(asset_obj.uri, bands=["vv", "vh"])
                    ri = reproject_to_target(ri)
                    if ri.width != ref_rast.width or ri.height != ref_rast.height:
                        ri = resample_to_grid(ri, ref_rast)
                except Exception as e:
                    raise RuntimeError(f"stack_build_error({b.asset_ref}): {e}") from e
                vh = ri.array[vh_idx].copy()
                valid = np.isfinite(vh) & ~np.isclose(vh, ri.nodata, atol=1e-3)
                vh[~valid] = np.nan
                wm, _ = sar_water_predict(np.where(valid, vh, -9999.0))
                arrays.append(vh)
                water_masks.append(wm)
                valid_masks.append(valid)
            return np.stack(arrays, axis=0), np.stack(water_masks, axis=0), np.stack(valid_masks, axis=0)

        try:
            vh_history_stack, water_history_stack, valid_history_stack = _read_to_stack(
                history_bindings, ref_raster)
            cur_arrays, cur_waters, cur_valids = [], [], []
            for b in current_bindings:
                try:
                    asset_obj = self._registry.resolve(b.asset_ref)
                    ri = read_geotiff(asset_obj.uri, bands=["vv", "vh"])
                    ri = reproject_to_target(ri)
                    if ri.width != ref_raster.width or ri.height != ref_raster.height:
                        ri = resample_to_grid(ri, ref_raster)
                except Exception as e:
                    raise RuntimeError(f"cur_stack_build_error({b.asset_ref}): {e}") from e
                vh = ri.array[vh_idx].copy()
                valid = np.isfinite(vh) & ~np.isclose(vh, ri.nodata, atol=1e-3)
                vh[~valid] = np.nan
                cur_arrays.append(vh)
                cur_waters.append(
                    sar_water_predict(np.where(valid, vh, -9999.0))[0]
                )
                cur_valids.append(valid)
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "stack_build", type(e).__name__, str(e), started_at)

        # 6. 背景统计
        try:
            baseline_vh_median = compute_median_background(vh_history_stack)
            baseline_vh_mad = compute_mad(vh_history_stack, baseline_vh_median,
                                           epsilon=mt_policy["mad_epsilon"])
            history_valid_count = compute_valid_count(vh_history_stack)
            historical_water_occurrence = compute_water_occurrence(
                water_history_stack.astype(np.float32), valid_history_stack)
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "statistics", type(e).__name__, str(e), started_at)

        # 7. 当前水体
        is_single_current = len(current_bindings) <= 1
        try:
            if len(cur_arrays) > 1:
                current_vh_median = np.nanmedian(np.stack(cur_arrays, axis=0), axis=0).astype(np.float32)
            else:
                current_vh_median = cur_arrays[0].astype(np.float32) if cur_arrays else np.full_like(baseline_vh_median, np.nan)
            current_vh_clean = np.where(np.isfinite(current_vh_median), current_vh_median, -9999.0)
            current_water_mask, current_thresh = sar_water_predict(current_vh_clean)
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "current_water", type(e).__name__, str(e), started_at)

        # 8. Z-Score + 变化分类
        try:
            robust_zscore = compute_robust_zscore(current_vh_median, baseline_vh_median, baseline_vh_mad)
            robust_zscore[~np.isfinite(current_vh_median)] = 0.0
            robust_zscore = ensure_no_nan_inf(robust_zscore)
            change_result = classify_multitemporal_change(
                current_water_mask, historical_water_occurrence, robust_zscore,
                history_valid_count,
                zscore_threshold=mt_policy["zscore_threshold"],
                stable_land_max=mt_policy["stable_land_max"],
                stable_water_min=mt_policy["stable_water_min"],
                min_valid_count=mt_policy["valid_count_threshold"],
            )
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "change_classify", type(e).__name__, str(e), started_at)

        # 确保无 NaN/Inf
        for name in ["baseline_vh_median", "baseline_vh_mad",
                      "historical_water_occurrence", "current_vh_median", "robust_zscore"]:
            arr = locals()[name]
            if isinstance(arr, np.ndarray):
                locals()[name] = ensure_no_nan_inf(arr)
        history_valid_count = np.where(np.isfinite(history_valid_count), history_valid_count, 0).astype(np.uint16)

        # ── RS-01B-3: Per-scene persistence + candidate objects ──────
        persistence_data = {}
        candidate_objects = []
        candidate_features_4326 = []
        candidate_json_data = {}
        try:
            p_cfg = mt_policy["persistence_config"]
            # 1. Per-scene change results
            per_scene = compute_per_scene_change(
                cur_arrays, baseline_vh_median, baseline_vh_mad,
                historical_water_occurrence, history_valid_count,
                zscore_threshold=mt_policy["zscore_threshold"],
                stable_land_max=mt_policy["stable_land_max"],
                stable_water_min=mt_policy["stable_water_min"],
                min_valid_count=mt_policy["valid_count_threshold"],
            )

            # 2. Persistence statistics
            persistence = compute_persistence(
                per_scene,
                minimum_occurrences=p_cfg["persistence"]["minimum_occurrences"],
                minimum_ratio=p_cfg["persistence"]["minimum_ratio"],
            )
            persistence_data = persistence

            # 3. Per-scene polygonize for object linking + Observation generation
            per_scene_features_proj: list[list[dict]] = []
            per_scene_features_4326: list[list[dict]] = []
            per_scene_asset_refs_list: list[str] = []
            per_scene_observations: list[list[Observation]] = []  # A1: per-scene Observations
            for si, scene_res in enumerate(per_scene):
                scene_feats: list[dict] = []
                scene_observations: list[Observation] = []
                # Determine scene source asset and acquisition time
                scene_asset_id: str | None = None
                scene_acq_time: str | None = None
                if si < len(current_bindings):
                    try:
                        cur_asset = self._registry.resolve(current_bindings[si].asset_ref)
                        scene_asset_id = cur_asset.asset_id
                        scene_acq_time = getattr(cur_asset, "acquisition_time", None)
                    except KeyError:
                        scene_asset_id = f"current_{si}"
                else:
                    scene_asset_id = f"current_{si}"

                for ct_mask, ct_label in [
                    (scene_res["scene_water_gain_mask"], "water_gain"),
                    (scene_res["scene_water_loss_mask"], "water_loss"),
                    (scene_res["scene_sar_anomaly_mask"], "sar_backscatter_anomaly"),
                ]:
                    if ct_mask.sum() == 0:
                        continue
                    feats = polygonize_change_mask(
                        ct_mask, ref_raster.transform, ref_raster.crs,
                        min_area_m2=mt_policy["min_area_m2"],
                        pixel_area_m2=mt_policy["pixel_area_m2"],
                    )
                    for f in feats:
                        f["properties"]["change_type"] = ct_label
                        f["properties"]["scene_index"] = si
                        # Add z-score and water occurrence stats
                        if f.get("geometry", {}).get("type") in ("Polygon", "MultiPolygon"):
                            try:
                                coords_list = f["geometry"]["coordinates"]
                                if f["geometry"]["type"] == "Polygon":
                                    rings = [coords_list[0]]
                                else:
                                    rings = []
                                    for poly_coords in coords_list:
                                        if poly_coords:
                                            rings.append(poly_coords[0])
                                for ring in rings:
                                    inv_t = ~ref_raster.transform
                                    rows, cols = [], []
                                    for x, y in ring:
                                        c, r = inv_t * (x, y)
                                        rows.append(int(round(r))); cols.append(int(round(c)))
                                    if rows:
                                        rows = np.clip(rows, 0, ref_raster.height - 1)
                                        cols = np.clip(cols, 0, ref_raster.width - 1)
                                        r_min, r_max = max(0, min(rows)), min(ref_raster.height, max(rows) + 1)
                                        c_min, c_max = max(0, min(cols)), min(ref_raster.width, max(cols) + 1)
                                        sz = scene_res["scene_robust_zscore"][r_min:r_max, c_min:c_max]
                                        sw = historical_water_occurrence[r_min:r_max, c_min:c_max]
                                        f["properties"]["robust_z_mean"] = round(float(np.nanmean(sz)), 4)
                                        f["properties"]["robust_z_max"] = round(float(np.nanmax(np.abs(sz))), 4)
                                        f["properties"]["water_occurrence_mean"] = round(float(np.nanmean(sw)), 4)
                            except Exception:
                                pass
                    scene_feats.extend(feats)
                # Keep projected features for CRS-correct linking (A0)
                per_scene_features_proj.append(scene_feats)
                # Also keep 4326 copies for GeoJSON output
                scene_feats_4326 = _to_epsg4326(scene_feats, ref_raster.crs)
                per_scene_features_4326.append(scene_feats_4326)
                per_scene_asset_refs_list.append(scene_asset_id or f"current_{si}")

                # A1: Create stable per-scene Observations
                for fi, feat in enumerate(scene_feats_4326):
                    props = feat.get("properties", {})
                    geom = feat.get("geometry", {})
                    change_type = props.get("change_type", "unknown")
                    area_m2 = float(props.get("area_m2", 0))
                    pix_count = int(props.get("pixel_count", 0))

                    # Stable observation_id: task_id + scene_index + change_type + geometry hash
                    geom_str = hashlib.md5(
                        str(geom.get("coordinates", "")).encode()
                    ).hexdigest()[:8]
                    obs_id = (
                        f"obs-{task.task_id}"
                        f"-s{si}"
                        f"-{change_type}"
                        f"-{geom_str}"
                    )

                    obs = Observation(
                        observation_id=obs_id,
                        perception_result_ref=result_id,
                        source_asset_refs=[scene_asset_id] if scene_asset_id else [],
                        source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
                        observation_type=(
                            ObservationType.SAR_BACKSCATTER_CHANGE
                            if change_type == "sar_backscatter_anomaly"
                            else ObservationType.CHANGE_POLYGON
                        ),
                        label=f"sar_scene{si}_{change_type}",
                        score=min(1.0, area_m2 / 50000.0) if area_m2 > 0 else 0.5,
                        score_type=ScoreType.RULE_BASED,
                        geometry=geom,
                        geometry_crs="EPSG:4326",
                        temporal={
                            "scene_index": si,
                            "acquisition_time": scene_acq_time or "",
                            "first_seen": si,
                            "last_seen": si,
                        },
                        quality={
                            "area_m2": area_m2,
                            "pixel_count": pix_count,
                            "robust_z_mean": float(props.get("robust_z_mean", 0)),
                            "robust_z_max": float(props.get("robust_z_max", 0)),
                            "water_occurrence_mean": float(props.get("water_occurrence_mean", 0)),
                            "spatial_reliability": "georeferenced",
                            "valid_pixel_ratio": min(1.0, pix_count / max(area_m2 / 100.0, 1)),
                            "quality_flags": [],
                            "change_type": change_type,
                            "history_scene_count": n_history,
                            "current_scene_count": n_current,
                        },
                        model_run_ref=context.run_id,
                        coordinate_space="geographic",
                    )
                    scene_observations.append(obs)
                    # Store obs_id on feature for later linking
                    feat["properties"]["observation_id"] = obs_id

                per_scene_observations.append(scene_observations)

            # 4. Link objects across time (in projected CRS — meters)
            ol_cfg = p_cfg["object_linking"]
            linking_crs = str(ref_raster.crs) if ref_raster and ref_raster.crs else None
            candidate_objects_proj = link_objects_across_time(
                per_scene_features_proj, per_scene_asset_refs_list,
                min_iou=ol_cfg["minimum_iou"],
                max_centroid_distance_m=ol_cfg["maximum_centroid_distance_m"],
                require_same_change_type=ol_cfg.get("require_same_change_type", True),
                require_spatial_intersect=ol_cfg.get("require_spatial_intersect", False),
                geometry_crs=linking_crs,
                pixel_area_m2=mt_policy["pixel_area_m2"],
                minimum_occurrences=p_cfg["persistence"]["minimum_occurrences"],
                minimum_ratio=p_cfg["persistence"]["minimum_ratio"],
                persistence_status=persistence["persistence_status"],
                n_current_scenes=len(current_bindings),
            )
            # Convert candidate geometries to EPSG:4326 for output
            candidate_objects = _convert_candidates_to_4326(
                candidate_objects_proj, ref_raster.crs
            )

            # 5. Rank candidates
            rk_cfg = p_cfg["ranking"]
            candidate_objects = rank_candidates(
                candidate_objects,
                history_scene_count=n_history,
                current_scene_count=len(current_bindings),
                weights=rk_cfg,
            )

            # 6. Convert to GeoJSON + JSON
            candidate_features_4326 = candidates_to_geojson(candidate_objects)
            candidate_json_data = candidates_to_json(
                candidate_objects,
                history_scene_count=n_history,
                current_scene_count=len(current_bindings),
            )
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "persistence", type(e).__name__, str(e), started_at)

        # 9. 多边形化 (按变化类型)
        try:
            all_features: list[dict] = []
            ref_crs_str = str(ref_raster.crs).upper()
            pixel_area = mt_policy["pixel_area_m2"]

            for ct_mask, ct_label in [
                (change_result["water_gain_mask"], "water_gain"),
                (change_result["water_loss_mask"], "water_loss"),
                (change_result["sar_anomaly_mask"], "sar_backscatter_anomaly"),
            ]:
                if ct_mask.sum() == 0:
                    continue
                feats = polygonize_change_mask(ct_mask, ref_raster.transform, ref_raster.crs,
                                                min_area_m2=mt_policy["min_area_m2"],
                                                pixel_area_m2=pixel_area)
                for feat in feats:
                    feat["properties"]["change_type"] = ct_label
                    geom = feat.get("geometry")
                    if geom and geom.get("type") == "Polygon":
                        coords = geom["coordinates"][0]
                        inv_t = ~ref_raster.transform
                        rows, cols = [], []
                        for x, y in coords:
                            c, r = inv_t * (x, y)
                            rows.append(int(round(r))); cols.append(int(round(c)))
                        rows = np.clip(rows, 0, ref_raster.height - 1)
                        cols = np.clip(cols, 0, ref_raster.width - 1)
                        r_min, r_max = max(0, min(rows)), min(ref_raster.height, max(rows) + 1)
                        c_min, c_max = max(0, min(cols)), min(ref_raster.width, max(cols) + 1)
                        rz = robust_zscore[r_min:r_max, c_min:c_max]
                        rw = historical_water_occurrence[r_min:r_max, c_min:c_max]
                        feat["properties"]["robust_z_mean"] = round(float(np.nanmean(rz)), 4)
                        feat["properties"]["robust_z_max"] = round(float(np.nanmax(np.abs(rz))), 4)
                        feat["properties"]["water_occurrence_mean"] = round(float(np.nanmean(rw)), 4)
                all_features.extend(feats)

            features_4326 = _to_epsg4326(all_features, ref_raster.crs)
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "polygonize_crs", type(e).__name__, str(e), started_at)

        # 10. 输出目录
        root_output = Path(context.output_dir) if context.output_dir else Path.cwd()
        task_output = root_output / context.run_id / task.task_id
        task_output.mkdir(parents=True, exist_ok=True)

        # 11. 写出产物的前置检查
        paths: dict[str, Path] = {}

        def _write_raster(name: str, arr: np.ndarray, dtype: str = "float32") -> Path:
            p = task_output / f"{name}.tif"
            if dtype == "uint8":
                out = arr.astype(np.uint8)
                write_geotiff(out, p, ref_raster.crs, ref_raster.transform,
                              bands=[name], dtype="uint8")
            elif dtype == "uint16":
                write_geotiff(arr.astype(np.float32), p, ref_raster.crs, ref_raster.transform,
                              bands=[name], dtype="float32")
            else:
                write_geotiff(arr.astype(np.float32), p, ref_raster.crs, ref_raster.transform,
                              bands=[name], dtype="float32")
            paths[name] = p
            return p

        try:
            _write_raster("baseline_vh_median", baseline_vh_median)
            _write_raster("baseline_vh_mad", baseline_vh_mad)
            _write_raster("history_valid_count", history_valid_count, dtype="uint16")
            _write_raster("historical_water_occurrence", historical_water_occurrence)
            _write_raster("current_vh_median", current_vh_median)
            _write_raster("current_water_mask", current_water_mask, dtype="uint8")
            _write_raster("robust_zscore", robust_zscore)
            _write_raster("water_gain_mask", change_result["water_gain_mask"], dtype="uint8")
            _write_raster("water_loss_mask", change_result["water_loss_mask"], dtype="uint8")
            _write_raster("final_change_mask", change_result["final_change_mask"], dtype="uint8")

            cand_path = task_output / "candidates.geojson"
            write_geojson(features_4326, cand_path)
            paths["candidates"] = cand_path

            # RS-01B-3: Write persistence artifacts
            if persistence_data:
                _write_raster("persistence_count", persistence_data["persistence_count"], dtype="uint16")
                _write_raster("persistence_ratio", persistence_data["persistence_ratio"])
                _write_raster("persistent_change_mask", persistence_data["persistent_change_mask"], dtype="uint8")
                _write_raster("transient_change_mask", persistence_data["transient_change_mask"], dtype="uint8")
            if candidate_features_4326:
                cand_obj_path = task_output / "candidate_objects.geojson"
                write_geojson(candidate_features_4326, cand_obj_path)
                paths["candidate_objects"] = cand_obj_path
            if candidate_json_data:
                cand_json_path = task_output / "candidate_objects.json"
                with open(cand_json_path, "w", encoding="utf-8") as f:
                    json.dump(candidate_json_data, f, ensure_ascii=False, indent=2)
                paths["candidate_objects_json"] = cand_json_path
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "write_rasters", type(e).__name__, str(e), started_at)

        # 12. 运行报告 (最终版本，再计算 checksum)
        total_area = sum(f["properties"].get("area_m2", 0) for f in features_4326)
        report = {
            "run_id": context.run_id, "task_id": task.task_id,
            "task_spec_ref": task.task_spec_ref,
            "actual_mode": "multi_temporal",
            "raster_crs": ref_crs_str, "geojson_crs": "EPSG:4326",
            "n_history_scenes": n_history, "n_current_scenes": n_current,
            "current_mode": "single" if is_single_current else "multi",
            "change_stats": change_result["stats"],
            "polygon_count": len(features_4326), "total_area_m2": total_area,
            "mt_policy": mt_policy,
            "scene_quality": {
                "accepted": accepted, "rejected": rejected,
                "accepted_history": accepted_history,
                "accepted_current": accepted_current,
                "rejected_history": rejected_history,
                "rejected_current": rejected_current,
                "warned": warned,
                "warned_history": warned_history,
                "warned_current": warned_current,
                "dropped_asset_refs": dropped_refs,
                "warnings": all_warnings,
                "min_valid_pixel_ratio": min_valid_pixel_ratio,
            },
            "output_dir": str(task_output),
        }
        report_path = task_output / "run_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        paths["run_report"] = report_path
        # 报告已最终化，计算 checksum
        report_checksum = _sha256_hex(report_path)

        # 13. 注册派生资产 (含 candidates 的 bounds)
        try:
            t = ref_raster.transform
            transform_list = [float(t.a), float(t.b), float(t.c),
                              float(t.d), float(t.e), float(t.f)]
            derived: list[AssetRef] = []
            raster_names = [
                "baseline_vh_median", "baseline_vh_mad", "history_valid_count",
                "historical_water_occurrence", "current_vh_median", "current_water_mask",
                "robust_zscore", "water_gain_mask", "water_loss_mask", "final_change_mask",
            ]
            # RS-01B-3: Add persistence rasters
            if persistence_data:
                raster_names.extend([
                    "persistence_count", "persistence_ratio",
                    "persistent_change_mask", "transient_change_mask",
                ])
            for name in raster_names:
                p = paths[name]
                aid = f"{task.task_id}_{name}"
                ref = AssetRef(asset_id=aid, uri=str(p),
                               media_type="image/tiff; application=geotiff",
                               modality=Modality.MASK if "mask" in name else Modality.SAR,
                               spatial=SpatialMetadata(
                                   reliability="georeferenced", crs=ref_crs_str,
                                   transform=transform_list,
                                   width=ref_raster.width, height=ref_raster.height),
                               bands=[name], checksum=_sha256_hex(p))
                self._registry.register(ref); derived.append(ref)

            # candidates spatial bounds — 聚合全部 Feature，支持 Polygon/MultiPolygon
            cand_bounds = None
            if features_4326:
                all_xs, all_ys = [], []
                for feat in features_4326:
                    geom = feat.get("geometry") or {}
                    coords = geom.get("coordinates", [])
                    gtype = geom.get("type", "")
                    # Polygon → [ring, ...]; MultiPolygon → [[ring, ...], ...]
                    rings: list = []
                    if gtype == "Polygon":
                        rings = coords  # list of rings
                    elif gtype == "MultiPolygon":
                        for poly in coords:
                            rings.extend(poly)  # flattened rings
                    for ring in rings:
                        for pt in ring:
                            if len(pt) >= 2:
                                all_xs.append(pt[0])
                                all_ys.append(pt[1])
                if all_xs and all_ys:
                    cand_bounds = [min(all_xs), min(all_ys), max(all_xs), max(all_ys)]

            ref_cand = AssetRef(
                asset_id=f"{task.task_id}_candidates", uri=str(cand_path),
                media_type="application/geo+json", modality=Modality.VECTOR,
                spatial=SpatialMetadata(
                    reliability="georeferenced", crs="EPSG:4326",
                    bounds=cand_bounds) if cand_bounds else None,
                checksum=_sha256_hex(cand_path),
            )
            ref_report_asset = AssetRef(
                asset_id=f"{task.task_id}_run_report", uri=str(report_path),
                media_type="application/json", modality=Modality.METADATA,
                checksum=report_checksum,
            )
            for r in [ref_cand, ref_report_asset]:
                self._registry.register(r); derived.append(r)

            # RS-01B-3: Register candidate objects artifacts
            if "candidate_objects" in paths:
                cand_obj_bounds = None
                if candidate_features_4326:
                    all_xs, all_ys = [], []
                    for feat in candidate_features_4326:
                        geom = feat.get("geometry") or {}
                        coords = geom.get("coordinates", [])
                        rings: list = []
                        if geom.get("type") == "Polygon":
                            rings = coords
                        elif geom.get("type") == "MultiPolygon":
                            for poly in coords:
                                rings.extend(poly)
                        for ring in rings:
                            for pt in ring:
                                if len(pt) >= 2:
                                    all_xs.append(pt[0]); all_ys.append(pt[1])
                    if all_xs and all_ys:
                        cand_obj_bounds = [min(all_xs), min(all_ys), max(all_xs), max(all_ys)]
                ref_cand_obj = AssetRef(
                    asset_id=f"{task.task_id}_candidate_objects",
                    uri=str(paths["candidate_objects"]),
                    media_type="application/geo+json", modality=Modality.VECTOR,
                    spatial=SpatialMetadata(
                        reliability="georeferenced", crs="EPSG:4326",
                        bounds=cand_obj_bounds) if cand_obj_bounds else None,
                    checksum=_sha256_hex(paths["candidate_objects"]),
                )
                self._registry.register(ref_cand_obj); derived.append(ref_cand_obj)
            if "candidate_objects_json" in paths:
                ref_cand_json = AssetRef(
                    asset_id=f"{task.task_id}_candidate_objects_json",
                    uri=str(paths["candidate_objects_json"]),
                    media_type="application/json", modality=Modality.METADATA,
                    checksum=_sha256_hex(paths["candidate_objects_json"]),
                )
                self._registry.register(ref_cand_json); derived.append(ref_cand_json)
        except ValueError as e:
            return _failed(result_id, task, spec, context,
                           "register", "duplicate_asset_id", str(e), started_at)

        # 14. Observations — A1: per-scene observations + aggregate mask observations
        source_asset_ids = []
        for b in all_bindings:
            try:
                source_asset_ids.append(self._registry.resolve(b.asset_ref).asset_id)
            except KeyError:
                pass
        observations: list[Observation] = []
        # Add per-scene Observations first (A1 stable)
        for scene_obs_list in per_scene_observations:
            observations.extend(scene_obs_list)
        # Add aggregate change mask observations
        for feat in features_4326:
            props = feat.get("properties", {})
            a = props.get("area_m2", 0)
            ct = props.get("change_type", "candidate")
            observations.append(Observation(
                observation_id=f"obs-{task.task_id}-{props.get('feature_id', 'p')}",
                perception_result_ref=result_id,
                source_asset_refs=source_asset_ids,
                source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
                observation_type=(ObservationType.SAR_BACKSCATTER_CHANGE
                                   if ct == "sar_backscatter_anomaly"
                                   else ObservationType.CHANGE_POLYGON),
                label=f"sar_mt_{ct}",
                score=min(1.0, a / 50000.0) if a > 0 else 0.5,
                score_type=ScoreType.RULE_BASED,
                geometry=feat.get("geometry"), geometry_crs="EPSG:4326",
                quality={"area_m2": a, "change_type": ct,
                         "pixel_count": props.get("pixel_count", 0),
                         "robust_z_mean": props.get("robust_z_mean", 0),
                         "robust_z_max": props.get("robust_z_max", 0),
                         "water_occurrence_mean": props.get("water_occurrence_mean", 0),
                         "history_scene_count": n_history,
                         "current_scene_count": n_current},
                model_run_ref=context.run_id,
            ))

        # A2: Link candidates to their per-scene Observations
        # Candidates reference the per-scene Observation IDs, not self-created IDs
        for cand in candidate_objects:
            # Find Observation IDs from per_scene_observations that match this candidate's
            # source_scene_indices and change_type
            candidate_obs_ids: list[str] = []
            for si in cand.source_scene_indices:
                if si < len(per_scene_observations):
                    for obs in per_scene_observations[si]:
                        if obs.label.endswith(f"_{cand.change_type}"):
                            candidate_obs_ids.append(obs.observation_id)
            if not candidate_obs_ids:
                # Fallback: use first observation from each scene
                for si in cand.source_scene_indices:
                    if si < len(per_scene_observations) and per_scene_observations[si]:
                        candidate_obs_ids.append(
                            per_scene_observations[si][0].observation_id
                        )
            cand.source_observation_ids = candidate_obs_ids

        # 15. 质量报告 (始终创建聚合报告)
        quality_recommendations = []
        quality_reasons = []
        if is_single_current:
            quality_recommendations.append("single_current_scene: reliability_reduced")
            quality_reasons.append("current_mode=single: 可靠性降低")
        if n_history < mt_policy["min_history_scenes"]:
            quality_recommendations.append("insufficient_history: pair_fallback_used")
            quality_reasons.append(f"history={n_history} < {mt_policy['min_history_scenes']}")
        if rejected > 0:
            quality_recommendations.append(f"{rejected} scene(s) rejected by quality gate")
            quality_reasons.append(f"rejected={rejected}, accepted={accepted}")
        if all_warnings:
            quality_recommendations.extend(
                r for r in all_warnings if r not in quality_recommendations
            )
        quality_report = QualityReport(
            valid_pixel_ratio=float(min_valid_pixel_ratio) if min_valid_pixel_ratio < 1.0 else 1.0,
            accepted_scenes=accepted,
            rejected_scenes=rejected,
            warned_count=warned,
            recommendations=quality_recommendations or [],
            reasons=quality_reasons or [],
        )

        status = (ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS
                  if observations else ExecutionStatus.SUCCEEDED_EMPTY)

        return PerceptionResult(
            perception_result_id=result_id, inference_task_ref=task.task_id,
            task_spec_ref=task.task_spec_ref, run_id=context.run_id,
            status=status, observations=observations,
            artifact_refs=[r.asset_id for r in derived],
            quality_report=quality_report,
            diagnostics={
                "actual_mode": "multi_temporal",
                "n_history": n_history, "n_current": n_current,
                "current_mode": "single" if is_single_current else "multi",
                "change_stats": change_result["stats"],
                "polygon_count": len(features_4326),
                "total_area_m2": total_area,
                "raster_crs": ref_crs_str, "geojson_crs": "EPSG:4326",
                "scene_quality": {
                    "accepted": accepted, "rejected": rejected,
                    "accepted_history": accepted_history,
                    "accepted_current": accepted_current,
                    "rejected_history": rejected_history,
                    "rejected_current": rejected_current,
                    "warned": warned,
                    "warned_history": warned_history,
                    "warned_current": warned_current,
                    "dropped_asset_refs": dropped_refs,
                    "warnings": all_warnings,
                    "min_valid_pixel_ratio": min_valid_pixel_ratio,
                },
                "persistence": persistence_data.get("persistence_status", "unknown") if persistence_data else "disabled",
                "persistence_stats": {
                    "persistence_status": persistence_data.get("persistence_status", "disabled") if persistence_data else "disabled",
                    "n_current_scenes": persistence_data.get("n_current_scenes", 0) if persistence_data else 0,
                    "persistent_pixels": int(persistence_data.get("persistent_change_mask", np.zeros(0)).sum()) if persistence_data else 0,
                    "transient_pixels": int(persistence_data.get("transient_change_mask", np.zeros(0)).sum()) if persistence_data else 0,
                },
                "candidate_stats": {
                    "total_candidates": len(candidate_objects),
                    "persistent_count": sum(1 for c in candidate_objects if c.persistence_status == "persistent"),
                    "transient_count": sum(1 for c in candidate_objects if c.persistence_status == "transient"),
                    "uncertain_count": sum(1 for c in candidate_objects if c.persistence_status == "uncertain"),
                },
            },
            started_at=started_at, finished_at=datetime.now().isoformat(),
        )

    # ── pair 执行 (供 run() 和 pair_fallback 共用) ────────────

    def _execute_pair(
        self, task: InferenceTask, spec: TaskSpec, context: RunContext,
        result_id: str, started_at: str, policy: SarValidationPolicy,
        before_binding: TaskAssetBinding, after_binding: TaskAssetBinding,
        actual_mode: str = "pair",
    ) -> PerceptionResult:
        """双时相核心算法。pair_fallback 也经过此路径。"""
        try:
            before_ref = self._registry.resolve(before_binding.asset_ref)
            after_ref = self._registry.resolve(after_binding.asset_ref)
        except KeyError as e:
            return _failed(result_id, task, spec, context,
                           "resolve", "missing_asset", str(e), started_at)

        # 读取
        try:
            sar_t1 = read_geotiff(before_ref.uri, bands=["vv", "vh"])
            sar_t2 = read_geotiff(after_ref.uri, bands=["vv", "vh"])
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "read", type(e).__name__, str(e), started_at)

        # 质量门禁
        try:
            meta_before = SarMetadata.from_asset_ref(before_ref, before_ref.uri)
            meta_after = SarMetadata.from_asset_ref(after_ref, after_ref.uri)
        except Exception as e:
            meta_before = None
            meta_after = None

        if policy.mode != PolicyMode.TRUST and meta_before and meta_after:
            qm = compute_input_quality(sar_t1.array, sar_t2.array, sar_t1.bands, sar_t2.bands)
            validation = validate_sar_input(meta_before, meta_after, sar_t1.bands, sar_t2.bands,
                                             qm, policy, sar_t1.width, sar_t1.height,
                                             sar_t2.width, sar_t2.height)
            if validation.rejected:
                status = ExecutionStatus.NO_DATA if qm.get("valid_pixel_ratio", 0.0) < 0.01 else ExecutionStatus.INVALID_INPUT
                return PerceptionResult(
                    perception_result_id=result_id, inference_task_ref=task.task_id,
                    task_spec_ref=task.task_spec_ref, run_id=context.run_id,
                    status=status, quality_report=validation.quality,
                    diagnostics={"rejection_reason": validation.rejection_reason,
                                 "quality": qm}, started_at=started_at,
                    finished_at=datetime.now().isoformat())

        # 重投影
        try:
            sar_t1 = reproject_to_target(sar_t1)
            sar_t2 = reproject_to_target(sar_t2)
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "reproject", type(e).__name__, str(e), started_at)

        ref = sar_t1
        if sar_t2.width != ref.width or sar_t2.height != ref.height:
            try:
                sar_t2 = resample_to_grid(sar_t2, ref)
            except Exception as e:
                return _failed(result_id, task, spec, context,
                               "resample", type(e).__name__, str(e), started_at)

        # 水体检测
        try:
            vh_idx_t1 = sar_t1.bands.index("vh")
            vh_idx_t2 = sar_t2.bands.index("vh")
            water_t1, thresh_t1 = sar_water_predict(sar_t1.array[vh_idx_t1])
            water_t2, thresh_t2 = sar_water_predict(sar_t2.array[vh_idx_t2])
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "water_detection", type(e).__name__, str(e), started_at)

        # 变化检测
        try:
            change = detect_change(water_t1, water_t2)
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "change_detection", type(e).__name__, str(e), started_at)

        total_changed = change["stats"]["total_changed"]

        # 多边形化
        try:
            features_4545 = polygonize_change_mask(change["change_mask"], ref.transform, ref.crs,
                                                    min_area_m2=500, pixel_area_m2=100)
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "polygonize", type(e).__name__, str(e), started_at)

        # CRS 转换
        try:
            features_4326 = _to_epsg4326(features_4545, ref.crs)
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "crs_convert", type(e).__name__, str(e), started_at)

        # 输出目录
        root_output = Path(context.output_dir) if context.output_dir else Path.cwd()
        task_output = root_output / context.run_id / task.task_id
        task_output.mkdir(parents=True, exist_ok=True)

        # 写出产物
        try:
            water_t1_path = task_output / "water_t1.tif"
            water_t2_path = task_output / "water_t2.tif"
            mask_path = task_output / "change_mask.tif"
            cand_path = task_output / "candidates.geojson"
            report_path = task_output / "run_report.json"

            write_geotiff(water_t1, water_t1_path, ref.crs, ref.transform, bands=["water"], dtype="uint8")
            write_geotiff(water_t2, water_t2_path, ref.crs, ref.transform, bands=["water"], dtype="uint8")
            write_geotiff(change["change_mask"], mask_path, ref.crs, ref.transform, bands=["change"], dtype="uint8")
            write_geojson(features_4326, cand_path)

            total_area = sum(f["properties"].get("area_m2", 0) for f in features_4326)
            report = {
                "run_id": context.run_id, "task_id": task.task_id,
                "task_spec_ref": task.task_spec_ref,
                "actual_mode": actual_mode,
                "raster_crs": str(ref.crs).upper(), "geojson_crs": "EPSG:4326",
                "total_changed_pixels": int(total_changed),
                "polygon_count": len(features_4326),
                "total_area_m2": total_area,
                "thresh_t1_db": float(thresh_t1), "thresh_t2_db": float(thresh_t2),
                "status": "succeeded_with_observations" if features_4326 else "succeeded_empty",
            }
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "write", type(e).__name__, str(e), started_at)

        # 修正 checksum: 报告已最终化，计算 checksum
        report_checksum = _sha256_hex(report_path)

        # 派生资产
        derived: list[AssetRef] = []
        t = ref.transform
        transform_list = [float(t.a), float(t.b), float(t.c), float(t.d), float(t.e), float(t.f)]
        crs_str = str(ref.crs).upper()

        def _raster_ref(aid, uri, bands, desc):
            r = AssetRef(asset_id=aid, uri=str(uri),
                         media_type="image/tiff; application=geotiff", modality=Modality.MASK,
                         spatial=SpatialMetadata(reliability="georeferenced", crs=crs_str,
                                                  transform=transform_list,
                                                  width=ref.width, height=ref.height),
                         bands=bands, checksum=_sha256_hex(uri))
            self._registry.register(r)
            derived.append(r)

        try:
            _raster_ref(f"{task.task_id}_water_t1", water_t1_path, ["water"], None)
            _raster_ref(f"{task.task_id}_water_t2", water_t2_path, ["water"], None)
            _raster_ref(f"{task.task_id}_change_mask", mask_path, ["change"], None)

            ref_cand = AssetRef(asset_id=f"{task.task_id}_candidates", uri=str(cand_path),
                                media_type="application/geo+json", modality=Modality.VECTOR,
                                spatial=SpatialMetadata(reliability="georeferenced", crs="EPSG:4326",
                                                         bounds=[f["bbox"] if "bbox" in f else None for f in features_4326[:1]][0] if features_4326 else None),
                                checksum=_sha256_hex(cand_path))
            ref_report = AssetRef(asset_id=f"{task.task_id}_run_report", uri=str(report_path),
                                  media_type="application/json", modality=Modality.METADATA,
                                  checksum=report_checksum)
            for r in [ref_cand, ref_report]:
                self._registry.register(r)
                derived.append(r)
        except ValueError as e:
            return _failed(result_id, task, spec, context,
                           "register", "duplicate_asset_id", str(e), started_at)

        # Observations
        observations: list[Observation] = []
        before_aid = self._registry.resolve(before_binding.asset_ref).asset_id
        after_aid = self._registry.resolve(after_binding.asset_ref).asset_id
        for feat in features_4326:
            props = feat.get("properties", {})
            a = props.get("area_m2", 0)
            observations.append(Observation(
                observation_id=f"obs-{task.task_id}-{props.get('feature_id', 'p')}",
                perception_result_ref=result_id,
                source_asset_refs=[before_aid, after_aid],
                source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
                observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
                label="sar_water_extent_change",
                score=min(1.0, a / 50000.0) if a > 0 else 0.5,
                score_type=ScoreType.RULE_BASED,
                geometry=feat.get("geometry"), geometry_crs="EPSG:4326",
                quality={"area_m2": a, "change_type": props.get("change_type", "candidate")},
                model_run_ref=context.run_id,
            ))

        status = ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS if observations else ExecutionStatus.SUCCEEDED_EMPTY

        return PerceptionResult(
            perception_result_id=result_id, inference_task_ref=task.task_id,
            task_spec_ref=task.task_spec_ref, run_id=context.run_id,
            status=status, observations=observations,
            artifact_refs=[r.asset_id for r in derived],
            diagnostics={"total_changed_pixels": int(total_changed),
                         "polygon_count": len(features_4326),
                         "total_area_m2": total_area,
                         "raster_crs": crs_str, "geojson_crs": "EPSG:4326",
                         "actual_mode": actual_mode},
            started_at=started_at, finished_at=datetime.now().isoformat(),
        )

    # ── 主运行 ──────────────────────────────────────────────────

    def run(self, task: InferenceTask, spec: TaskSpec, context: RunContext) -> PerceptionResult:
        result_id = f"pr-{task.task_id}"
        started_at = datetime.now().isoformat()

        # 0. 前置检查
        if not self._registry:
            return _failed(result_id, task, spec, context,
                           "pre_check", "missing_registry",
                           "AssetRegistry 未设置", started_at)

        # 1. 校验
        errors = self.validate_spec(task, spec)
        if errors:
            return PerceptionResult(
                perception_result_id=result_id, inference_task_ref=task.task_id,
                task_spec_ref=task.task_spec_ref, run_id=context.run_id,
                status=ExecutionStatus.INVALID_INPUT,
                diagnostics={"validation_errors": errors},
                started_at=started_at, finished_at=datetime.now().isoformat())

        # 2. 多时相路由 (RS-01B-2)
        if _is_multi_temporal_mode(spec):
            policy = SarValidationPolicy.default_warn()
            if spec.validation_policy:
                try:
                    policy = SarValidationPolicy(**spec.validation_policy)
                except Exception:
                    pass
            return self._execute_multi_temporal(
                task, spec, context, result_id, started_at, policy,
            )

        # 3. 双时相 (纯 BEFORE+AFTER 模式)
        try:
            before_binding = next(b for b in task.asset_bindings if b.role == AssetRole.BEFORE)
            after_binding = next(b for b in task.asset_bindings if b.role == AssetRole.AFTER)
        except StopIteration:
            return PerceptionResult(
                perception_result_id=result_id, inference_task_ref=task.task_id,
                task_spec_ref=task.task_spec_ref, run_id=context.run_id,
                status=ExecutionStatus.INVALID_INPUT,
                diagnostics={"error": "缺少 before/after 绑定"},
                started_at=started_at, finished_at=datetime.now().isoformat())

        policy = SarValidationPolicy.default_warn()
        if spec.validation_policy:
            try:
                policy = SarValidationPolicy(**spec.validation_policy)
            except Exception:
                pass

        return self._execute_pair(task, spec, context, result_id, started_at,
                                   policy, before_binding, after_binding, actual_mode="pair")

