"""CandidateDeliveryEnvelope — delivery container for G0.3-A candidates."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from core.schemas.contracts.candidate import DetectionCandidate, CANDIDATE_V0_3


_RANKING_DISCLAIMER = (
    "运行内排名，非绝对概率；跨运行不可直接比较"
)


class CandidateDeliveryEnvelope(BaseModel):
    """Delivery envelope for G0.3-A candidates to Agent B / product chain."""
    model_config = dict(frozen=True)

    schema_version: Literal["candidate.v0.3"] = Field(
        default=CANDIDATE_V0_3, description="契约版本 (frozen)"
    )

    run_id: str = Field(..., min_length=1, description="运行 ID")
    scene_index: int = Field(..., ge=0, description="当前场景序号 (0-based)")

    total_candidates: int = Field(..., ge=0, description="候选总数")
    candidates: tuple[DetectionCandidate, ...] = Field(
        default_factory=tuple, description="候选列表 (tuple, 不可变)"
    )

    score_type: str = Field(
        default="within_run_ranking",
        description="评分类型 (固定值)"
    )
    ranking_disclaimer: str = Field(
        default=_RANKING_DISCLAIMER,
        description="排名免责声明"
    )
