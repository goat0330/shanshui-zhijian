"""
RS-01A.1 — CompetitionMapper

将 PerceptionResult 映射为 PredictionRecord（内部格式）。
修复: 使用真实判别联合 payload，不通过 len(observations) 猜 change_pixels。
"""

from core.schemas.contracts.prediction import (
    PredictionRecord,
    ChangePrediction,
)
from core.schemas.contracts.perception import PerceptionResult
from core.schemas.contracts.task import InferenceTask


class CompetitionMapper:
    """将 PerceptionResult 映射为 PredictionRecord（内部格式）。"""

    def map_result(self, result: PerceptionResult, inference_task: InferenceTask) -> PredictionRecord:
        payload = self._build_payload(result)
        return PredictionRecord(
            record_id=f"pred-{inference_task.task_id}",
            inference_task_ref=inference_task.task_id,
            perception_result_ref=result.perception_result_id,
            execution_status=result.status.value,
            payload=payload,
        )

    def _build_payload(self, result: PerceptionResult) -> ChangePrediction | None:
        if result.status.value in ("no_data", "invalid_input", "failed"):
            return None
        if result.status.value == "succeeded_empty":
            return ChangePrediction(change_pixels=0)

        diag = result.diagnostics or {}
        area_m2 = diag.get("total_area_m2", 0)
        polygons_ref = None
        if result.artifact_refs:
            polygons_ref = result.artifact_refs[-1] if len(result.artifact_refs) > 1 else result.artifact_refs[0]
        return ChangePrediction(
            change_pixels=int(diag.get("total_changed_pixels", 0)),
            polygons_ref=polygons_ref,
        )
