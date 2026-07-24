"""
RS-00 — CompetitionMapper

将 PerceptionResult 映射为 PredictionRecord。
不涉及官方 Schema（只使用 internal.v0.2）。
"""

from core.schemas.contracts.prediction import (
    PredictionRecord,
    ChangePrediction,
    ClassificationPrediction,
    DetectionPrediction,
    SegmentationPrediction,
    AnomalyScorePrediction,
)
from core.schemas.contracts.perception import PerceptionResult, Observation
from core.schemas.contracts.task import InferenceTask


class CompetitionMapper:
    """将 PerceptionResult 映射为 PredictionRecord（内部格式）。"""

    def map_result(
        self,
        result: PerceptionResult,
        inference_task: InferenceTask,
    ) -> PredictionRecord:
        """一条 InferenceTask → 一条 PredictionRecord（1:1）"""

        # 根据 status 确定 payload
        payload = self._build_payload(result)

        return PredictionRecord(
            record_id=f"pred-{inference_task.task_id}",
            inference_task_ref=inference_task.task_id,
            perception_result_ref=result.perception_result_id,
            execution_status=result.status.value,
            prediction_type=self._detect_prediction_type(result),
            payload=payload,
        )

    def _detect_prediction_type(self, result: PerceptionResult) -> str:
        """从 observations 推断 prediction_type"""
        types = {o.observation_type for o in result.observations if o.observation_type}
        if "change_polygon" in types or "sar_backscatter_change" in types:
            return "change_detection"
        if "water_extent" in types:
            return "segmentation"
        if "object_detection" in types:
            return "detection"
        if "anomaly_score" in types:
            return "anomaly_scoring"
        return "change_detection"

    def _build_payload(self, result: PerceptionResult) -> dict:
        """构建内部判别联合 payload"""
        if result.status.value in ("no_data", "invalid_input", "failed"):
            return {"prediction_type": "change_detection", "note": result.status.value}

        # 默认: 从第一条 Observation 推断
        if not result.observations:
            return {"prediction_type": "change_detection", "change_pixels": 0}

        obs = result.observations[0]
        if obs.observation_type == "sar_backscatter_change":
            return ChangePrediction(
                change_mask_ref=result.artifact_refs[0] if result.artifact_refs else None,
                change_pixels=0,
            ).model_dump()
        if obs.observation_type == "water_extent":
            return SegmentationPrediction(
                mask_ref=result.artifact_refs[0] if result.artifact_refs else "",
            ).model_dump()
        if obs.observation_type == "object_detection":
            return DetectionPrediction(detections=[{"bbox": [], "class_id": 0, "confidence": 0.0}]).model_dump()
        return ChangePrediction().model_dump()
