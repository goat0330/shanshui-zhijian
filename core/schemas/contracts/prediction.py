"""
RS-00 — PredictionRecord + 五类判别联合 PredictionPayload

PredictionRecord 是比赛评测链的核心记录。
一条 InferenceTask 对应一条 PredictionRecord（1:1）。
"""

from typing import Annotated, Any
from pydantic import BaseModel, Field
from typing import Literal


# ── 五类 PredictionPayload ─────────────────────────────────────

class ClassificationPrediction(BaseModel):
    prediction_type: Literal["classification"] = "classification"
    class_id: int = Field(..., ge=0)
    class_name: str = ""
    confidence: float = Field(..., ge=0.0, le=1.0)


class DetectionPrediction(BaseModel):
    prediction_type: Literal["detection"] = "detection"
    detections: list[dict] = Field(..., min_length=1)


class SegmentationPrediction(BaseModel):
    prediction_type: Literal["segmentation"] = "segmentation"
    mask_ref: str = Field(..., min_length=1)
    class_map: dict[str, int] = Field(default_factory=dict)


class ChangePrediction(BaseModel):
    prediction_type: Literal["change_detection"] = "change_detection"
    change_mask_ref: str | None = None
    polygons_ref: str | None = None
    change_pixels: int | None = None


class AnomalyScorePrediction(BaseModel):
    prediction_type: Literal["anomaly_scoring"] = "anomaly_scoring"
    score_map_ref: str | None = None
    mean_score: float | None = Field(None, ge=0.0, le=1.0)
    threshold: float | None = Field(None, ge=0.0, le=1.0)


# ── PredictionPayload 判别联合 ─────────────────────────────────

PredictionPayload = Annotated[
    ClassificationPrediction
    | DetectionPrediction
    | SegmentationPrediction
    | ChangePrediction
    | AnomalyScorePrediction,
    Field(discriminator="prediction_type"),
]


# ── PredictionRecord ────────────────────────────────────────────

class PredictionRecord(BaseModel):
    """比赛评测链预测记录。一条 InferenceTask 对应一条。"""
    schema_version: str = "rs-contract.v0.2"
    record_id: str = Field(..., min_length=1)
    inference_task_ref: str = Field(..., min_length=1, description="关联 InferenceTask ID（1:1）")
    perception_result_ref: str | None = None
    execution_status: str = Field(..., description="继承自 PerceptionResult.status")
    prediction_type: str = Field(..., description="change_detection / classification / detection / segmentation / anomaly_scoring")
    payload: dict = Field(..., description="PredictionPayload（判别联合序列化后）")
    model_run_ref: str | None = None
