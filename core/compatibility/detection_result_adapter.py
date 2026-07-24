"""
RS-00 — DetectionResultAdapter

旧 DetectionResult → 新 PerceptionResult + PredictionRecord
按整条 InferenceTask 聚合，生成一条 PredictionRecord。
不修改旧对象定义。
"""

import json
from datetime import datetime
from core.schemas.contracts import ExecutionStatus, TaskType, ObservationType, ScoreType
from core.schemas.contracts.task import InferenceTask, RunContext
from core.schemas.contracts.perception import Observation, QualityReport, PerceptionResult
from core.schemas.contracts.prediction import PredictionRecord


class DetectionResultAdapter:
    """旧 DetectionResult 格式 → 新 PerceptionResult + PredictionRecord。"""

    @staticmethod
    def to_perception_result(
        dr_list: list[dict],
        inference_task: InferenceTask,
        context: RunContext,
    ) -> PerceptionResult:
        """将一组 DetectionResult 聚合为一个 PerceptionResult。"""
        result_id = f"pr-{inference_task.task_id}"
        observations = []
        artifact_refs: list[str] = []

        for dr in dr_list:
            obs = Observation(
                observation_id=dr.get("detection_id", f"obs-{len(observations)}"),
                perception_result_ref=result_id,
                source_asset_refs=dr.get("source_assets", []),
                source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
                observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
                label=dr.get("category", "candidate"),
                score=dr.get("confidence", 0.5),
                score_type=ScoreType.RULE_BASED,
                geometry=dr.get("geometry"),
                temporal={"start": dr.get("observed_at", ""), "end": ""},
                model_run_ref=context.run_id,
            )
            observations.append(obs)
            # 收集 artifact refs
            for ref in dr.get("evidence_refs", []):
                if ref not in artifact_refs:
                    artifact_refs.append(ref)

        return PerceptionResult(
            perception_result_id=result_id,
            inference_task_ref=inference_task.task_id,
            task_spec_ref=inference_task.task_spec_ref,
            run_id=context.run_id,
            status=ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS if observations else ExecutionStatus.SUCCEEDED_EMPTY,
            observations=observations,
            artifact_refs=artifact_refs,
            quality_report=QualityReport(
                valid_pixel_ratio=1.0,
                reasons=["adapted_from_detection_result"],
            ),
            started_at=datetime.now().isoformat(),
            finished_at=datetime.now().isoformat(),
        )

    @staticmethod
    def to_prediction_record(
        perception_result: PerceptionResult,
        inference_task: InferenceTask,
    ) -> PredictionRecord:
        """按整条 InferenceTask 生成一条 PredictionRecord。"""
        obs = perception_result.observations
        # 构造 payload
        payload = {
            "prediction_type": "change_detection",
            "change_pixels": len(obs),
            "polygons_ref": perception_result.artifact_refs[0] if perception_result.artifact_refs else None,
        }

        return PredictionRecord(
            record_id=f"pred-{inference_task.task_id}",
            inference_task_ref=inference_task.task_id,
            perception_result_ref=perception_result.perception_result_id,
            execution_status=perception_result.status.value,
            prediction_type="change_detection",
            payload=payload,
            model_run_ref=perception_result.run_id,
        )
