"""
B3 — CompetitionMapper 增强

根据 TaskSpec.task_type 决定 payload 类型，支持五类：
- classification
- detection
- segmentation
- change_detection
- anomaly_scoring
"""

from core.schemas.contracts.prediction import (
    PredictionRecord,
    ClassificationPrediction,
    DetectionPrediction,
    SegmentationPrediction,
    ChangePrediction,
    AnomalyScorePrediction,
    PredictionPayload,
)
from core.schemas.contracts.perception import PerceptionResult, ExecutionStatus
from core.schemas.contracts.task import InferenceTask, TaskSpec


class CompetitionMapper:
    """将 PerceptionResult 映射为 PredictionRecord（内部格式）。"""

    def map_result(self, result: PerceptionResult, inference_task: InferenceTask, task_spec: TaskSpec | None = None) -> PredictionRecord:
        payload = self._build_payload(result, task_spec)
        return PredictionRecord(
            record_id=f"pred-{inference_task.task_id}",
            inference_task_ref=inference_task.task_id,
            perception_result_ref=result.perception_result_id,
            execution_status=result.status.value,
            payload=payload,
        )

    def _build_payload(self, result: PerceptionResult, task_spec: TaskSpec | None = None) -> PredictionPayload | None:
        """根据 execution_status 和 task_type 构建 payload。"""
        # NO_DATA / INVALID_INPUT / FAILED → no payload
        if result.status in (
            ExecutionStatus.NO_DATA,
            ExecutionStatus.INVALID_INPUT,
            ExecutionStatus.FAILED,
        ):
            return None

        # SUCCEEDED_EMPTY → 空 payload（不同 task_type 返回对应空结构）
        if result.status == ExecutionStatus.SUCCEEDED_EMPTY:
            return self._empty_payload(task_spec)

        # SUCCEEDED_WITH_OBSERVATIONS → 根据 task_type 构建
        task_type = task_spec.task_type if task_spec else "temporal_change_detection"
        return self._build_payload_by_type(result, task_type)

    def _empty_payload(self, task_spec: TaskSpec | None) -> PredictionPayload | None:
        """任务类型对应的空 payload。"""
        task_type = task_spec.task_type if task_spec else "temporal_change_detection"
        if task_type == "classification":
            return ClassificationPrediction(class_id=0, class_name="", confidence=0.0)
        elif task_type == "detection":
            return DetectionPrediction(detections=[])
        elif task_type == "segmentation":
            return SegmentationPrediction(mask_ref="")
        elif task_type == "anomaly_scoring":
            return AnomalyScorePrediction(mean_score=0.0, threshold=0.0)
        else:  # change_detection
            return ChangePrediction(change_pixels=0)

    def _build_payload_by_type(self, result: PerceptionResult, task_type: str) -> PredictionPayload | None:
        """根据 task_type 构建带观测结果的 payload。"""
        diag = result.diagnostics or {}
        observations = result.observations or []

        if task_type == "classification":
            # 从第一个 observation 获取类别
            label = observations[0].label if observations else "unknown"
            score = observations[0].score if observations else 0.0
            return ClassificationPrediction(class_id=0, class_name=label, confidence=score)

        elif task_type == "detection":
            detections = []
            for obs in observations:
                detections.append({
                    "observation_id": obs.observation_id,
                    "label": obs.label,
                    "score": obs.score,
                    "geometry": obs.geometry,
                })
            return DetectionPrediction(detections=detections or [])

        elif task_type == "segmentation":
            mask_ref = ""
            if result.artifact_refs:
                # 找到第一个掩膜 artifact
                for ref in result.artifact_refs:
                    if "mask" in ref.lower():
                        mask_ref = ref
                        break
                if not mask_ref:
                    mask_ref = result.artifact_refs[0]
            return SegmentationPrediction(mask_ref=mask_ref)

        elif task_type == "anomaly_scoring":
            score_map_ref = result.artifact_refs[0] if result.artifact_refs else None
            return AnomalyScorePrediction(
                score_map_ref=score_map_ref,
                mean_score=diag.get("mean_score", 0.0),
                threshold=diag.get("threshold", 0.0),
            )

        else:  # change_detection (default)
            polygons_ref = None
            if result.artifact_refs:
                # 不通过最后一个元素猜多边形文件，通过 role/type 识别
                for ref in result.artifact_refs:
                    if "candidate" in ref.lower() or "polygon" in ref.lower():
                        polygons_ref = ref
                        break
                if not polygons_ref:
                    polygons_ref = result.artifact_refs[-1] if len(result.artifact_refs) > 1 else result.artifact_refs[0]
            return ChangePrediction(
                change_pixels=int(diag.get("total_changed_pixels", 0)),
                polygons_ref=polygons_ref,
            )
