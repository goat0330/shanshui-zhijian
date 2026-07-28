"""
RS-01A.1 — CompetitionMapper (G0)

Maps PerceptionResult → PredictionRecord using TaskType enum dispatch.
TaskType enum is the single source of truth for prediction type.

TaskType → PredictionRecord mapping:
  CLASSIFICATION          → ClassificationPrediction
  OBJECT_DETECTION        → DetectionPrediction
  WATER_EXTRACTION        → SegmentationPrediction
  TEMPORAL_CHANGE_DETECTION → ChangePrediction
  ANOMALY_SCORING         → AnomalyScorePrediction

Empty results:
  succeeded_empty → payload=None (status carries the "no result" semantics)
  no_data/invalid_input/failed → payload=None
  succeeded_with_observations → payload present with observations

One InferenceTask → exactly one PredictionRecord.
Review data does NOT participate in mapping.
"""

from core.schemas.contracts import TaskType
from core.schemas.contracts.prediction import (
    PredictionRecord,
    ClassificationPrediction,
    DetectionPrediction,
    SegmentationPrediction,
    ChangePrediction,
    AnomalyScorePrediction,
)
from core.schemas.contracts.perception import PerceptionResult
from core.schemas.contracts.task import InferenceTask


class CompetitionMapper:
    """将 PerceptionResult 映射为 PredictionRecord。

    Uses TaskType enum dispatch for correct payload type.
    """

    TASK_TYPE_PAYLOAD_MAP: dict[TaskType, str] = {
        TaskType.CLASSIFICATION: "classification",
        TaskType.OBJECT_DETECTION: "detection",
        TaskType.WATER_EXTRACTION: "segmentation",
        TaskType.TEMPORAL_CHANGE_DETECTION: "change_detection",
        TaskType.ANOMALY_SCORING: "anomaly_scoring",
    }

    def map_result(self, result: PerceptionResult, inference_task: InferenceTask,
                   task_type: TaskType | None = None) -> PredictionRecord:
        if task_type is None:
            raise ValueError(
                "map_result: task_type is required. "
                "Pass an explicit TaskType (e.g., TaskType.TEMPORAL_CHANGE_DETECTION). "
                "The default was removed to prevent silent wrong-payload-type bugs."
            )
        payload = self._build_payload(result, task_type)
        return PredictionRecord(
            record_id=f"pred-{inference_task.task_id}",
            inference_task_ref=inference_task.task_id,
            perception_result_ref=result.perception_result_id,
            execution_status=result.status.value,
            payload=payload,
        )

    def _build_payload(self, result: PerceptionResult, task_type: TaskType):
        """Build correct payload based on status and TaskType.

        Empty results (succeeded_empty, no_data, failed) → None payload.
        The execution_status field carries the semantic meaning.
        """
        # Status-based: no_data/invalid_input/failed → no payload
        if result.status.value in ("no_data", "invalid_input", "failed"):
            return None

        # SUCCEEDED_EMPTY → None payload (status carries the semantics)
        if result.status.value == "succeeded_empty":
            return None

        # SUCCEEDED_WITH_OBSERVATIONS → build payload from task type
        return self._payload_from_observations(result, task_type)

    def _payload_from_observations(self, result: PerceptionResult, task_type: TaskType):
        """Build payload from observations, diagnostics, and artifacts."""
        diag = result.diagnostics or {}

        if task_type == TaskType.TEMPORAL_CHANGE_DETECTION:
            polygons_ref = None
            if result.artifact_refs:
                for aid in result.artifact_refs:
                    if "polygon" in aid.lower() or "candidate" in aid.lower():
                        polygons_ref = aid
                        break
                if not polygons_ref:
                    polygons_ref = result.artifact_refs[-1] if result.artifact_refs else None
            return ChangePrediction(
                change_pixels=int(diag.get("total_changed_pixels", 0)),
                polygons_ref=polygons_ref,
            )

        elif task_type == TaskType.CLASSIFICATION:
            obs = result.observations[0] if result.observations else None
            return ClassificationPrediction(
                class_id=int(diag.get("class_id", 0)),
                class_name=diag.get("class_name", ""),
                confidence=obs.score if obs else 0.0,
            )

        elif task_type == TaskType.OBJECT_DETECTION:
            detections = []
            for obs in result.observations:
                if obs.geometry:
                    detections.append({
                        "geometry": obs.geometry,
                        "label": obs.label,
                        "score": obs.score,
                    })
            return DetectionPrediction(detections=detections or [])

        elif task_type == TaskType.WATER_EXTRACTION:
            mask_ref = None
            if result.artifact_refs:
                for aid in result.artifact_refs:
                    if "mask" in aid.lower():
                        mask_ref = aid
                        break
            return SegmentationPrediction(
                mask_ref=mask_ref or (result.artifact_refs[0] if result.artifact_refs else ""),
            )

        elif task_type == TaskType.ANOMALY_SCORING:
            return AnomalyScorePrediction(
                score_map_ref=result.artifact_refs[0] if result.artifact_refs else None,
                mean_score=diag.get("mean_anomaly_score", 0.0),
                threshold=diag.get("anomaly_threshold", 0.0),
            )

        raise ValueError(f"Unknown task_type: {task_type}. Cannot build payload.")
