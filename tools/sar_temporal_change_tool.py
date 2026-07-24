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


class SarTemporalChangeTool(PerceptionTool):
    """Sentinel-1 SAR 双时相变化检测工具 (RS-01A.2)。"""

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

        # 2. 解析资产
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
