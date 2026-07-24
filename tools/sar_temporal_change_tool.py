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
from pathlib import Path
from datetime import datetime

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


def _sha256_hex(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def _to_epsg4326(features: list[dict], src_crs: str) -> list[dict]:
    """将 GeoJSON features 的 geometry 坐标从 src_crs 转为 EPSG:4326。"""
    if not features:
        return features
    crs_str = str(src_crs).upper()
    if crs_str == "EPSG:4326":
        return features
    if crs_str.startswith("EPSG:45"):
        result = []
        for feat in features:
            geom = feat.get("geometry")
            if geom and geom.get("type") == "Polygon":
                coords = []
                for ring in geom["coordinates"]:
                    new_ring = []
                    for pt in ring:
                        # EPSG:4545 → EPSG:4326: 粗略缩放
                        # 重庆 CM 108E, 近似 111km/deg
                        lon = 108.0 + pt[0] / 111000.0
                        lat = 30.0 + pt[1] / 111000.0
                        new_ring.append([lon, lat])
                    coords.append(new_ring)
                new_feat = dict(feat)
                new_feat["geometry"] = {"type": "Polygon", "coordinates": coords}
                result.append(new_feat)
            else:
                result.append(feat)
        return result
    raise NotImplementedError(f"CRS 转换未实现: {src_crs}")


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


class _FallbackToPair(Exception):
    """内部异常：多时相历史景数不足，回退双时相模式。"""
    pass


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
    }


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
        """多时相稳健背景变化检测 (RS-01B-2)。

        流程:
        1. 解析 HISTORY + CURRENT 资产
        2. 检查历史景数，不足则返回 NO_DATA 或抛出用于 fallback
        3. 逐景通过 RS-01B-1 质量门禁
        4. 构建历史 VH 堆栈 + 当前 VH 堆栈
        5. 计算背景统计 (median, MAD, valid_count)
        6. 历史水体检测 → water_occurrence
        7. 当前水体检测
        8. 鲁棒 Z-Score + 变化分类
        9. 多边形化 + Observations
        10. 写出 10 产物 + 注册 AssetRef
        """
        mt_policy = _parse_mt_policy(context)
        has_current = any(b.role == AssetRole.CURRENT for b in task.asset_bindings)

        # 1. 解析资产
        history_bindings, current_bindings = self._resolve_multi_temporal(task, spec)

        n_history = len(history_bindings)
        n_current = len(current_bindings) if has_current else 1

        # 2. 历史景数检查
        if n_history < mt_policy["min_history_scenes"]:
            policy_choice = mt_policy["insufficient_history_policy"]
            if policy_choice == "no_data":
                return _failed(result_id, task, spec, context,
                               "history_check", "insufficient_history",
                               f"历史景数 {n_history} < 最小 {mt_policy['min_history_scenes']} (policy=no_data)",
                               started_at)
            # fallback_to_pair → 抛异常让 run() 去执行 pair 流程
            raise _FallbackToPair(
                f"历史景数 {n_history} < 最小 {mt_policy['min_history_scenes']}, 回退双时相"
            )

        # 3. 质量门禁 (逐景)
        all_bindings = history_bindings + current_bindings
        ref_binding = history_bindings[0]

        try:
            ref_asset = self._registry.resolve(ref_binding.asset_ref)
        except KeyError as e:
            return _failed(result_id, task, spec, context,
                           "resolve_reference", "missing_asset", str(e), started_at)

        for i, b in enumerate(all_bindings):
            try:
                scene_asset = self._registry.resolve(b.asset_ref)
            except KeyError as e:
                return _failed(result_id, task, spec, context,
                               "resolve_scene", "missing_asset",
                               f"scene[{i}] {b.asset_ref}: {e}", started_at)
            if b.asset_ref == ref_binding.asset_ref:
                continue  # 跳过自身
            try:
                scene_data = read_geotiff(scene_asset.uri, bands=["vv", "vh"])
            except Exception as e:
                return _failed(result_id, task, spec, context,
                               "read_scene", type(e).__name__,
                               f"scene[{i}] {scene_asset.uri}: {e}", started_at)

            if policy.mode != PolicyMode.TRUST:
                meta_ref = SarMetadata.from_asset_ref(ref_asset, ref_asset.uri)
                meta_scene = SarMetadata.from_asset_ref(scene_asset, scene_asset.uri)
                ref_data = read_geotiff(ref_asset.uri, bands=["vv", "vh"])
                qm = compute_input_quality(
                    ref_data.array, scene_data.array,
                    ref_data.bands, scene_data.bands,
                )
                validation = validate_sar_input(
                    meta_ref, meta_scene,
                    ref_data.bands, scene_data.bands,
                    qm, policy,
                    ref_data.width, ref_data.height,
                    scene_data.width, scene_data.height,
                )
                if validation.rejected:
                    return _failed(result_id, task, spec, context,
                                   "quality_gate", "scene_rejected",
                                   f"scene[{i}] {b.asset_ref}: {validation.rejection_reason}",
                                   started_at)

        # 4. 构建历史 VH 堆栈
        ref_raster = reproject_to_target(read_geotiff(ref_asset.uri, bands=["vv", "vh"]))
        vh_idx = ref_raster.bands.index("vh")
        history_arrays = []
        history_water = []

        for i, b in enumerate(history_bindings):
            asset = self._registry.resolve(b.asset_ref)
            ri = read_geotiff(asset.uri, bands=["vv", "vh"])
            ri = reproject_to_target(ri)
            if ri.width != ref_raster.width or ri.height != ref_raster.height:
                ri = resample_to_grid(ri, ref_raster)
            vh = ri.array[vh_idx].copy()
            # 标记 NoData 为 NaN
            vh[np.isclose(vh, ri.nodata, atol=1e-3)] = np.nan
            vh[~np.isfinite(vh)] = np.nan
            history_arrays.append(vh)

            # 历史水体掩膜
            wm, _ = sar_water_predict(np.where(np.isfinite(vh), vh, -9999.0))
            history_water.append(wm)

        vh_history_stack = np.stack(history_arrays, axis=0)  # (N, H, W)
        water_history_stack = np.stack(history_water, axis=0)  # (N, H, W)

        # 5. 构建当前 VH
        current_arrays = []
        for i, b in enumerate(current_bindings):
            asset = self._registry.resolve(b.asset_ref)
            ri = read_geotiff(asset.uri, bands=["vv", "vh"])
            ri = reproject_to_target(ri)
            if ri.width != ref_raster.width or ri.height != ref_raster.height:
                ri = resample_to_grid(ri, ref_raster)
            vh = ri.array[vh_idx].copy()
            vh[np.isclose(vh, ri.nodata, atol=1e-3)] = np.nan
            vh[~np.isfinite(vh)] = np.nan
            current_arrays.append(vh)

        current_vh_median = np.nanmedian(np.stack(current_arrays, axis=0), axis=0).astype(np.float32)
        is_single_current = len(current_arrays) == 1

        # 6. 背景统计
        baseline_vh_median = compute_median_background(vh_history_stack)
        baseline_vh_mad = compute_mad(vh_history_stack, baseline_vh_median,
                                       epsilon=mt_policy["mad_epsilon"])
        history_valid_count = compute_valid_count(vh_history_stack)
        historical_water_occurrence = compute_water_occurrence(
            water_history_stack.astype(np.float32)
        )

        # 7. 当前水体
        current_vh_clean = np.where(np.isfinite(current_vh_median), current_vh_median, -9999.0)
        current_water_mask, current_thresh = sar_water_predict(current_vh_clean)

        # 8. 鲁棒 Z-Score + 变化分类
        robust_zscore = compute_robust_zscore(
            current_vh_median, baseline_vh_median, baseline_vh_mad,
        )
        robust_zscore[np.isnan(current_vh_median)] = 0.0
        robust_zscore = ensure_no_nan_inf(robust_zscore)

        change_result = classify_multitemporal_change(
            current_water_mask, historical_water_occurrence, robust_zscore,
            history_valid_count,
            zscore_threshold=mt_policy["zscore_threshold"],
            water_occurrence_threshold=mt_policy["water_occurrence_threshold"],
            min_valid_count=mt_policy["valid_count_threshold"],
        )

        # 9. 保证无 NaN/Inf
        for key in ["baseline_vh_median", "baseline_vh_mad", "history_valid_count",
                     "historical_water_occurrence", "current_vh_median"]:
            arr = locals().get(key)
            if isinstance(arr, np.ndarray):
                if key == "history_valid_count":
                    arr = np.where(np.isfinite(arr), arr, 0).astype(np.uint16)
                else:
                    arr = ensure_no_nan_inf(arr.astype(np.float32))
                locals()[key] = arr

        # Re-bind after potential NaN fix
        baseline_vh_median = ensure_no_nan_inf(baseline_vh_median)
        baseline_vh_mad = ensure_no_nan_inf(baseline_vh_mad)
        history_valid_count = np.where(
            np.isfinite(history_valid_count), history_valid_count, 0
        ).astype(np.uint16)
        historical_water_occurrence = ensure_no_nan_inf(historical_water_occurrence)
        current_vh_median = ensure_no_nan_inf(current_vh_median)

        # 10. 多边形化 (每种变化类型)
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
            feats = polygonize_change_mask(
                ct_mask, ref_raster.transform, ref_raster.crs,
                min_area_m2=mt_policy["min_area_m2"],
                pixel_area_m2=pixel_area,
            )
            for feat in feats:
                feat["properties"]["change_type"] = ct_label
                # 计算图斑内统计量
                geom = feat["geometry"]
                if geom and geom.get("type") == "Polygon":
                    coords = geom["coordinates"][0]
                    xs = [p[0] for p in coords]
                    ys = [p[1] for p in coords]
                    # 像素坐标近似
                    inv_t = ~ref_raster.transform
                    rows = []
                    cols = []
                    for x, y in zip(xs, ys):
                        c, r = inv_t * (x, y)
                        rows.append(int(round(r)))
                        cols.append(int(round(c)))
                    rows = np.clip(rows, 0, ref_raster.height - 1)
                    cols = np.clip(cols, 0, ref_raster.width - 1)
                    if len(rows) > 0 and len(cols) > 0:
                        # 取边界框内统计量
                        r_min, r_max = max(0, min(rows)), min(ref_raster.height, max(rows) + 1)
                        c_min, c_max = max(0, min(cols)), min(ref_raster.width, max(cols) + 1)
                        region_z = robust_zscore[r_min:r_max, c_min:c_max]
                        region_wo = historical_water_occurrence[r_min:r_max, c_min:c_max]
                        feat["properties"]["robust_z_mean"] = round(float(np.nanmean(region_z)), 4)
                        feat["properties"]["robust_z_max"] = round(float(np.nanmax(np.abs(region_z))), 4)
                        feat["properties"]["water_occurrence_mean"] = round(float(np.nanmean(region_wo)), 4)
            all_features.extend(feats)

        # mixed: 同一图斑同时为 gain 和 loss (由 polygonize 合并后判)
        # (保留但概率极低)

        features_4326 = _to_epsg4326(all_features, ref_raster.crs)

        # 11. 输出目录
        root_output = Path(context.output_dir) if context.output_dir else Path.cwd()
        task_output = root_output / context.run_id / task.task_id
        task_output.mkdir(parents=True, exist_ok=True)

        # 12. 写出 10 个栅格产物
        paths: dict[str, Path] = {}

        # 先用 _safe_raster 写辅助函数
        def _write_raster(name: str, arr: np.ndarray, dtype: str = "float32") -> Path:
            p = task_output / f"{name}.tif"
            actual_dtype = dtype
            actual_nodata = -9999.0
            if dtype == "uint16":
                actual_dtype = "float32"  # write_geotiff 不支持 uint16 负值 nodata
                arr = arr.astype(np.float32)
            elif dtype == "uint8":
                arr_out = arr.astype(np.uint8)
            else:
                arr_out = arr.astype(np.float32)
            if dtype == "uint8":
                arr_out = arr.astype(np.uint8)
            else:
                arr_out = arr.astype(np.float32)
            write_geotiff(arr_out, p, ref_raster.crs, ref_raster.transform,
                          bands=[name], dtype=actual_dtype)
            paths[name] = p
            return p

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

        report_path = task_output / "run_report.json"
        total_area = sum(f["properties"].get("area_m2", 0) for f in features_4326)
        report = {
            "run_id": context.run_id, "task_id": task.task_id,
            "task_spec_ref": task.task_spec_ref,
            "mode": "multi_temporal",
            "raster_crs": ref_crs_str,
            "geojson_crs": "EPSG:4326",
            "n_history_scenes": n_history,
            "n_current_scenes": n_current,
            "current_mode": "single" if is_single_current else "multi",
            "change_stats": change_result["stats"],
            "polygon_count": len(features_4326),
            "total_area_m2": total_area,
            "mt_policy": mt_policy,
            "output_dir": str(task_output),
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        paths["run_report"] = report_path

        # 13. 注册派生资产
        ct_map = {"water_gain": 1, "water_loss": 2, "sar_backscatter_anomaly": 3}

        if hasattr(ref_raster.transform, '__iter__'):
            t = ref_raster.transform
            transform_list = [float(t.a), float(t.b), float(t.c),
                              float(t.d), float(t.e), float(t.f)]
        else:
            transform_list = list(ref_raster.transform)[:6]

        derived: list[AssetRef] = []
        raster_names = [
            "baseline_vh_median", "baseline_vh_mad", "history_valid_count",
            "historical_water_occurrence", "current_vh_median", "current_water_mask",
            "robust_zscore", "water_gain_mask", "water_loss_mask", "final_change_mask",
        ]
        for name in raster_names:
            p = paths[name]
            asset_id = f"{task.task_id}_{name}"
            ref = AssetRef(
                asset_id=asset_id, uri=str(p),
                media_type="image/tiff; application=geotiff",
                modality=Modality.MASK if "mask" in name else Modality.SAR,
                spatial=SpatialMetadata(
                    reliability="georeferenced", crs=ref_crs_str,
                    transform=transform_list,
                    width=ref_raster.width, height=ref_raster.height,
                ),
                bands=[name], checksum=_sha256_hex(p),
            )
            self._registry.register(ref)
            derived.append(ref)

        ref_cand = AssetRef(
            asset_id=f"{task.task_id}_candidates", uri=str(cand_path),
            media_type="application/geo+json", modality=Modality.VECTOR,
            checksum=_sha256_hex(cand_path),
        )
        ref_report_asset = AssetRef(
            asset_id=f"{task.task_id}_run_report", uri=str(report_path),
            media_type="application/json", modality=Modality.METADATA,
            checksum=_sha256_hex(report_path),
        )
        for r in [ref_cand, ref_report_asset]:
            self._registry.register(r)
            derived.append(r)

        # 14. Observations
        source_asset_ids = [self._registry.resolve(b.asset_ref).asset_id
                            for b in all_bindings]
        observations: list[Observation] = []
        for feat in features_4326:
            props = feat.get("properties", {})
            a = props.get("area_m2", 0)
            ct = props.get("change_type", "candidate")
            observations.append(Observation(
                observation_id=f"obs-{task.task_id}-{props.get('feature_id', 'p')}",
                perception_result_ref=result_id,
                source_asset_refs=source_asset_ids,
                source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
                observation_type=(
                    ObservationType.SAR_BACKSCATTER_CHANGE if ct == "sar_backscatter_anomaly"
                    else ObservationType.CHANGE_POLYGON
                ),
                label=f"sar_mt_{ct}",
                score=min(1.0, a / 50000.0) if a > 0 else 0.5,
                score_type=ScoreType.RULE_BASED,
                geometry=feat.get("geometry"),
                geometry_crs="EPSG:4326",
                quality={
                    "area_m2": a,
                    "change_type": ct,
                    "pixel_count": props.get("pixel_count", 0),
                    "robust_z_mean": props.get("robust_z_mean", 0),
                    "robust_z_max": props.get("robust_z_max", 0),
                    "water_occurrence_mean": props.get("water_occurrence_mean", 0),
                    "history_scene_count": n_history,
                    "current_scene_count": n_current,
                },
                model_run_ref=context.run_id,
            ))

        # 15. 更新报告
        with open(report_path, "r", encoding="utf-8") as f:
            rpt = json.load(f)
        rpt["status"] = "succeeded_with_observations" if observations else "succeeded_empty"
        rpt["derived_assets"] = [r.asset_id for r in derived]
        rpt["observation_ids"] = [o.observation_id for o in observations]
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(rpt, f, ensure_ascii=False, indent=2)

        # 16. 质量报告
        quality_report = None
        if is_single_current:
            quality_report = QualityReport(
                valid_pixel_ratio=1.0,
                recommendations=["single_current_scene: reliability_reduced"],
                reasons=["current_mode=single: 可靠性降低"],
            )

        status = (ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS
                  if observations else ExecutionStatus.SUCCEEDED_EMPTY)

        return PerceptionResult(
            perception_result_id=result_id,
            inference_task_ref=task.task_id,
            task_spec_ref=task.task_spec_ref,
            run_id=context.run_id,
            status=status,
            observations=observations,
            artifact_refs=[r.asset_id for r in derived],
            quality_report=quality_report,
            diagnostics={
                "mode": "multi_temporal",
                "n_history": n_history,
                "n_current": n_current,
                "current_mode": "single" if is_single_current else "multi",
                "change_stats": change_result["stats"],
                "polygon_count": len(features_4326),
                "total_area_m2": total_area,
                "raster_crs": ref_crs_str,
                "geojson_crs": "EPSG:4326",
            },
            started_at=started_at,
            finished_at=datetime.now().isoformat(),
        )

    # ── pair 双时相 (提取自原 run 逻辑, 供 fallback) ────────────

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
            # 解析策略 (重用在下面 pair 流程中也会用到)
            policy = SarValidationPolicy.default_warn()
            if spec.validation_policy:
                try:
                    policy = SarValidationPolicy(**spec.validation_policy)
                except Exception:
                    pass
            try:
                return self._execute_multi_temporal(
                    task, spec, context, result_id, started_at, policy,
                )
            except _FallbackToPair:
                pass  # 回落至双时相

        # 3. 双时相解析 (原有逻辑)
        try:
            before_binding = next(b for b in task.asset_bindings if b.role == AssetRole.BEFORE)
            after_binding = next(b for b in task.asset_bindings if b.role == AssetRole.AFTER)
            if before_binding.asset_ref == after_binding.asset_ref:
                return _failed(result_id, task, spec, context,
                               "binding_resolve", "same_asset", "before/after 不可引用同一资产", started_at)
            before_ref = self._registry.resolve(before_binding.asset_ref)
            after_ref = self._registry.resolve(after_binding.asset_ref)
        except (StopIteration, KeyError) as e:
            return PerceptionResult(
                perception_result_id=result_id, inference_task_ref=task.task_id,
                task_spec_ref=task.task_spec_ref, run_id=context.run_id,
                status=ExecutionStatus.INVALID_INPUT,
                diagnostics={"error": f"缺少 before/after 资产: {e}"},
                started_at=started_at, finished_at=datetime.now().isoformat())

        # 3. 读取
        try:
            sar_t1 = read_geotiff(before_ref.uri, bands=["vv", "vh"])
            sar_t2 = read_geotiff(after_ref.uri, bands=["vv", "vh"])
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "read", type(e).__name__, str(e), started_at)

        # 4. 质量门禁 (RS-01B-1)
        policy = SarValidationPolicy.default_warn()  # 默认 warn，保持向后兼容
        if spec.validation_policy:
            try:
                policy = SarValidationPolicy(**spec.validation_policy)
            except Exception:
                pass  # 解析失败用默认 warn

        if policy.mode != PolicyMode.TRUST:
            # 构建 SarMetadata (从 AssetRef)
            meta_before = SarMetadata.from_asset_ref(before_ref, before_ref.uri)
            meta_after = SarMetadata.from_asset_ref(after_ref, after_ref.uri)

            # 计算输入质量
            quality_metrics = compute_input_quality(
                sar_t1.array, sar_t2.array,
                sar_t1.bands, sar_t2.bands, nodata=-9999.0,
            )

            # 校验
            validation = validate_sar_input(
                meta_before, meta_after,
                sar_t1.bands, sar_t2.bands,
                quality_metrics, policy,
                sar_t1.width, sar_t1.height,
                sar_t2.width, sar_t2.height,
            )

            if validation.rejected:
                qr = validation.quality
                # 判断是 NO_DATA 还是 INVALID_INPUT
                if quality_metrics.get("valid_pixel_ratio", 0.0) < 0.01:
                    status = ExecutionStatus.NO_DATA
                else:
                    status = ExecutionStatus.INVALID_INPUT
                return PerceptionResult(
                    perception_result_id=result_id,
                    inference_task_ref=task.task_id,
                    task_spec_ref=task.task_spec_ref,
                    run_id=context.run_id,
                    status=status,
                    quality_report=qr,
                    diagnostics={
                        "rejection_reason": validation.rejection_reason,
                        "quality": quality_metrics,
                    },
                    started_at=started_at, finished_at=datetime.now().isoformat(),
                )

            # 未拒绝但可能有警告 — 预存 quality_report
            _quality_report = validation.quality
        else:
            _quality_report = None

        # 5. 重投影
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

        # 5. 水体检测
        try:
            vh_idx_t1 = sar_t1.bands.index("vh")
            vh_idx_t2 = sar_t2.bands.index("vh")
            water_t1, thresh_t1 = sar_water_predict(sar_t1.array[vh_idx_t1])
            water_t2, thresh_t2 = sar_water_predict(sar_t2.array[vh_idx_t2])
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "water_detection", type(e).__name__, str(e), started_at)

        # 6. 变化检测
        try:
            change = detect_change(water_t1, water_t2)
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "change_detection", type(e).__name__, str(e), started_at)

        total_changed = change["stats"]["total_changed"]

        # 7. 多边形化 (在 EPSG:4545 下)
        try:
            features_4545 = polygonize_change_mask(
                change["change_mask"], ref.transform, ref.crs,
                min_area_m2=500, pixel_area_m2=100,
            )
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "polygonize", type(e).__name__, str(e), started_at)

        # 8. GeoJSON geometry → EPSG:4326
        try:
            features_4326 = _to_epsg4326(features_4545, ref.crs)
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "crs_convert", type(e).__name__, str(e), started_at)

        # 9. 输出目录: output_dir/run_id/task_id/
        root_output = Path(context.output_dir) if context.output_dir else Path.cwd()
        task_output = root_output / context.run_id / task.task_id
        task_output.mkdir(parents=True, exist_ok=True)

        # 10. 写出产物 (先写数据，再写报告，后注册)
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

            # 先写一个占位报告 (后面会覆盖)
            report = {
                "run_id": context.run_id, "task_id": task.task_id,
                "task_spec_ref": task.task_spec_ref,
                "raster_crs": str(ref.crs),
                "geojson_crs": "EPSG:4326",
                "total_changed_pixels": int(total_changed),
                "polygon_count": len(features_4326),
                "total_area_m2": 0.0,
                "thresh_t1_db": float(thresh_t1),
                "thresh_t2_db": float(thresh_t2),
                "output_dir": str(task_output),
            }
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except Exception as e:
            return _failed(result_id, task, spec, context,
                           "write", type(e).__name__, str(e), started_at)

        # 11. 注册派生资产到 registry
        prefix = f"{task.task_id}"
        derived_assets: list[AssetRef] = []
        crs_str = str(ref.crs).upper()
        if hasattr(ref.transform, '__iter__'):
            # rasterio Affine → 6-element list [a, b, c, d, e, f]
            t = ref.transform
            transform_list = [float(t.a), float(t.b), float(t.c),
                              float(t.d), float(t.e), float(t.f)]
        else:
            transform_list = list(ref.transform)[:6]
        try:
            ref_water_t1 = AssetRef(
                asset_id=f"{prefix}_water_t1", uri=str(water_t1_path),
                media_type="image/tiff; application=geotiff", modality=Modality.MASK,
                spatial=SpatialMetadata(
                    reliability="georeferenced", crs=crs_str,
                    transform=transform_list,
                    width=ref.width, height=ref.height,
                ),
                bands=["water"], checksum=_sha256_hex(water_t1_path),
            )
            ref_water_t2 = AssetRef(
                asset_id=f"{prefix}_water_t2", uri=str(water_t2_path),
                media_type="image/tiff; application=geotiff", modality=Modality.MASK,
                spatial=SpatialMetadata(
                    reliability="georeferenced", crs=crs_str,
                    transform=transform_list,
                    width=ref.width, height=ref.height,
                ),
                bands=["water"], checksum=_sha256_hex(water_t2_path),
            )
            ref_mask = AssetRef(
                asset_id=f"{prefix}_change_mask", uri=str(mask_path),
                media_type="image/tiff; application=geotiff", modality=Modality.MASK,
                spatial=SpatialMetadata(
                    reliability="georeferenced", crs=crs_str,
                    transform=transform_list,
                    width=ref.width, height=ref.height,
                ),
                bands=["change"], checksum=_sha256_hex(mask_path),
            )
            ref_cand = AssetRef(
                asset_id=f"{prefix}_candidates", uri=str(cand_path),
                media_type="application/geo+json", modality=Modality.VECTOR,
                checksum=_sha256_hex(cand_path),
            )
            ref_report = AssetRef(
                asset_id=f"{prefix}_run_report", uri=str(report_path),
                media_type="application/json", modality=Modality.METADATA,
                checksum=_sha256_hex(report_path),
            )
            for r in [ref_water_t1, ref_water_t2, ref_mask, ref_cand, ref_report]:
                self._registry.register(r)
                derived_assets.append(r)
        except ValueError as e:
            return _failed(result_id, task, spec, context,
                           "register", "duplicate_asset_id", str(e), started_at)

        # 12. Observations
        observations: list[Observation] = []
        total_area = 0.0
        for feat in features_4326:
            props = feat.get("properties", {})
            a = props.get("area_m2", 0)
            total_area += a
            observations.append(Observation(
                observation_id=f"obs-{task.task_id}-{props.get('feature_id', 'p')}",
                perception_result_ref=result_id,
                source_asset_refs=[before_ref.asset_id, after_ref.asset_id],
                source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
                observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
                label="sar_water_extent_change",
                score=min(1.0, a / 50000.0) if a > 0 else 0.5,
                score_type=ScoreType.RULE_BASED,
                geometry=feat.get("geometry"),
                geometry_crs="EPSG:4326",
                quality={"area_m2": a, "change_type": props.get("change_type", "candidate")},
                model_run_ref=context.run_id,
            ))

        # 13. 更新运行报告（追加 final info）
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        report["status"] = "succeeded_with_observations" if observations else "succeeded_empty"
        report["total_area_m2"] = total_area
        report["polygon_count"] = len(features_4326)
        report["derived_assets"] = [r.asset_id for r in derived_assets]
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # 14. 状态判定
        status = ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS if observations else ExecutionStatus.SUCCEEDED_EMPTY
        artifact_ids = [r.asset_id for r in derived_assets]

        return PerceptionResult(
            perception_result_id=result_id,
            inference_task_ref=task.task_id,
            task_spec_ref=task.task_spec_ref,
            run_id=context.run_id,
            status=status,
            observations=observations,
            artifact_refs=artifact_ids,
            diagnostics={
                "total_changed_pixels": int(total_changed),
                "polygon_count": len(features_4326),
                "total_area_m2": total_area,
                "raster_crs": ref.crs,
                "geojson_crs": "EPSG:4326",
            },
            started_at=started_at,
            finished_at=datetime.now().isoformat(),
        )
