"""
RS-01A.1 — SarTemporalChangeTool

Sentinel-1 SAR 双时相变化检测工具。
修复: AssetResolver 解析 URI、真实产物写出、每个图斑一条 Observation。
"""

import json
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT / "competition" / "spikes" / "chongqing_rs_demo"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from core.schemas.contracts import (
    ExecutionStatus, TaskType, ObservationType, ScoreType, AssetRole,
)
from core.schemas.contracts.asset import AssetRef
from core.schemas.contracts.task import InferenceTask, TaskSpec, RunContext
from core.schemas.contracts.perception import PerceptionResult, Observation, QualityReport
from core.protocols.perception_tool import PerceptionTool
from core.protocols.asset_resolver import AssetResolver
from pipeline.io.reader import read_geotiff
from pipeline.io.writer import write_geotiff, write_geojson
from pipeline.processing.preprocessor import reproject_to_target, resample_to_grid
from pipeline.models.baseline_water_sar import predict_vh as sar_water_predict
from pipeline.detection.change import detect_change
from pipeline.postprocessing.polygonize import polygonize_change_mask


class SarTemporalChangeTool(PerceptionTool):
    """
    Sentinel-1 SAR 双时相变化检测工具。
    通过 AssetResolver 解析 asset_id 为 AssetRef.uri。
    输出真实产物到 context.output_dir。
    """

    def __init__(self, resolver: AssetResolver | None = None):
        self._resolver = resolver

    def set_resolver(self, resolver: AssetResolver):
        self._resolver = resolver

    def validate_spec(self, task: InferenceTask, spec: TaskSpec) -> list[str]:
        """校验 task 是否满足 spec。返回错误列表，空=通过。"""
        errors = []
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
        if self._resolver:
            for b in task.asset_bindings:
                try:
                    asset = self._resolver.resolve(b.asset_ref)
                    slot = next((s for s in spec.input_slots if s.role == b.role), None)
                    if slot and asset.modality not in slot.modalities:
                        errors.append(f"asset {b.asset_ref} modality {asset.modality.value} 不在 {[m.value for m in slot.modalities]}")
                except KeyError:
                    errors.append(f"asset_id 未注册: {b.asset_ref}")
        return errors

    def run(self, task: InferenceTask, spec: TaskSpec, context: RunContext) -> PerceptionResult:
        result_id = f"pr-{task.task_id}"
        started_at = datetime.now().isoformat()
        if not self._resolver:
            return PerceptionResult(
                perception_result_id=result_id, inference_task_ref=task.task_id,
                task_spec_ref=task.task_spec_ref, run_id=context.run_id,
                status=ExecutionStatus.FAILED,
                diagnostics={"error": "AssetResolver 未设置"},
                started_at=started_at, finished_at=datetime.now().isoformat())
        errors = self.validate_spec(task, spec)
        if errors:
            return PerceptionResult(
                perception_result_id=result_id, inference_task_ref=task.task_id,
                task_spec_ref=task.task_spec_ref, run_id=context.run_id,
                status=ExecutionStatus.INVALID_INPUT,
                diagnostics={"validation_errors": errors},
                started_at=started_at, finished_at=datetime.now().isoformat())
        try:
            before_ref = self._resolver.resolve(next(b.asset_ref for b in task.asset_bindings if b.role == AssetRole.BEFORE))
            after_ref = self._resolver.resolve(next(b.asset_ref for b in task.asset_bindings if b.role == AssetRole.AFTER))
        except (StopIteration, KeyError) as e:
            return PerceptionResult(
                perception_result_id=result_id, inference_task_ref=task.task_id,
                task_spec_ref=task.task_spec_ref, run_id=context.run_id,
                status=ExecutionStatus.INVALID_INPUT,
                diagnostics={"error": f"缺少 before/after: {e}"},
                started_at=started_at, finished_at=datetime.now().isoformat())
        try:
            sar_t1 = read_geotiff(before_ref.uri, bands=["vv", "vh"])
            sar_t2 = read_geotiff(after_ref.uri, bands=["vv", "vh"])
        except Exception as e:
            return PerceptionResult(
                perception_result_id=result_id, inference_task_ref=task.task_id,
                task_spec_ref=task.task_spec_ref, run_id=context.run_id,
                status=ExecutionStatus.FAILED,
                diagnostics={"error": f"读取 SAR 失败: {e}"},
                started_at=started_at, finished_at=datetime.now().isoformat())
        sar_t1 = reproject_to_target(sar_t1)
        sar_t2 = reproject_to_target(sar_t2)
        ref = sar_t1
        if sar_t2.width != ref.width or sar_t2.height != ref.height:
            sar_t2 = resample_to_grid(sar_t2, ref)
        try:
            vh_idx_t1 = sar_t1.bands.index("vh")
            vh_idx_t2 = sar_t2.bands.index("vh")
            water_t1, thresh_t1 = sar_water_predict(sar_t1.array[vh_idx_t1])
            water_t2, thresh_t2 = sar_water_predict(sar_t2.array[vh_idx_t2])
        except Exception as e:
            return PerceptionResult(
                perception_result_id=result_id, inference_task_ref=task.task_id,
                task_spec_ref=task.task_spec_ref, run_id=context.run_id,
                status=ExecutionStatus.FAILED,
                diagnostics={"error": f"SAR 水体检测失败: {e}"},
                started_at=started_at, finished_at=datetime.now().isoformat())
        change = detect_change(water_t1, water_t2)
        total_changed = change["stats"]["total_changed"]
        features = polygonize_change_mask(change["change_mask"], ref.transform, ref.crs, min_area_m2=500, pixel_area_m2=100)
        output_dir = Path(context.output_dir) if context.output_dir else Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)
        prefix = f"{task.task_id}"
        water_t1_path = output_dir / f"{prefix}_water_t1.tif"
        water_t2_path = output_dir / f"{prefix}_water_t2.tif"
        mask_path = output_dir / f"{prefix}_change_mask.tif"
        cand_path = output_dir / f"{prefix}_candidates.geojson"
        write_geotiff(water_t1, water_t1_path, ref.crs, ref.transform, bands=["water"], dtype="uint8")
        write_geotiff(water_t2, water_t2_path, ref.crs, ref.transform, bands=["water"], dtype="uint8")
        write_geotiff(change["change_mask"], mask_path, ref.crs, ref.transform, bands=["change"], dtype="uint8")
        write_geojson(features, cand_path)
        derived = {}
        if mask_path.exists():
            derived["change_mask"] = AssetRef(asset_id=f"{prefix}_change_mask", uri=str(mask_path), media_type="image/tiff; application=geotiff", modality="mask")
        if cand_path.exists():
            derived["candidates"] = AssetRef(asset_id=f"{prefix}_candidates", uri=str(cand_path), media_type="application/geo+json", modality="vector")
        observations = []
        total_area = 0.0
        for feat in features:
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
                quality={"area_m2": a, "change_type": props.get("change_type", "candidate")},
                model_run_ref=context.run_id,
            ))
        report = {
            "run_id": context.run_id, "task_id": task.task_id,
            "task_spec_ref": task.task_spec_ref,
            "status": "succeeded_with_observations" if observations else "succeeded_empty",
            "total_changed_pixels": int(total_changed),
            "polygon_count": len(features), "total_area_m2": total_area,
        }
        with open(output_dir / f"{prefix}_run_report.json", "w") as f:
            json.dump(report, f, indent=2)
        status = ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS if observations else ExecutionStatus.SUCCEEDED_EMPTY
        return PerceptionResult(
            perception_result_id=result_id, inference_task_ref=task.task_id,
            task_spec_ref=task.task_spec_ref, run_id=context.run_id,
            status=status, observations=observations,
            artifact_refs=[d.asset_id for d in derived.values()],
            diagnostics={"total_changed_pixels": int(total_changed), "polygon_count": len(features), "total_area_m2": total_area},
            started_at=started_at, finished_at=datetime.now().isoformat())
