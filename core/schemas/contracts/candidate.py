"""
RS-00 — DetectionCandidate + EvidenceRef

G0.2-A: candidate.v0.3 — frozen model, TemporalExtent, Enum lifecycle/score_type.
"""

from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator, ConfigDict


# ── Enums ─────────────────────────────────────────────────────


class CandidateLifecycle(str, Enum):
    PROPOSED = "proposed"
    SUPPRESSED = "suppressed"
    SUPERSEDED = "superseded"
    AGGREGATED = "aggregated"


class ScoreType(str, Enum):
    WITHIN_RUN_RANKING = "within_run_ranking"
    PROBABILITY = "probability"
    CONFIDENCE = "confidence"
    RAW_SCORE = "raw_score"


class CandidateStatus(str, Enum):
    PERSISTENT = "persistent"
    TRANSIENT = "transient"
    UNCERTAIN = "uncertain"


# ── TemporalExtent model (not bare dict) ─────────────────────


class TemporalExtent(BaseModel):
    """时间范围：start/end 为场景索引、时间戳或 ISO 日期字符串。"""
    start: int | float | str = Field(..., description="起始场景索引、时间戳或 ISO 日期")
    end: int | float | str = Field(..., description="结束场景索引、时间戳或 ISO 日期")

    @model_validator(mode="after")
    def _start_not_after_end(self) -> Self:
        """仅当均为数字时校验 start <= end。"""
        if isinstance(self.start, (int, float)) and isinstance(self.end, (int, float)):
            if self.start > self.end:
                raise ValueError(
                    f"temporal_extent.start ({self.start}) > "
                    f"temporal_extent.end ({self.end})"
                )
        return self


# ── EvidenceRef ──────────────────────────────────────────────


class EvidenceRef(BaseModel):
    """证据引用。指向源资产或派生资产，用于产品研判阶段。"""
    evidence_id: str = Field(..., min_length=1)
    source_asset_ref: str = Field(..., min_length=1, description="源资产 ID")
    derived_asset_ref: str | None = Field(None, description="派生资产 ID")
    evidence_type: str = Field(
        ..., description="rgb_tile / ndwi / change_mask / sar_vh / dem"
    )
    spatial_window: dict | None = None
    temporal_window: dict | None = None
    description: str | None = None
    provenance: dict | None = None


# ── DetectionCandidate (v0.3 frozen) ──────────────────────────


class DetectionCandidate(BaseModel):
    """产品链：一个或多个 Observation 经聚合形成的不可变算法候选。

    candidate.v0.3 — frozen=True, Enum fields, TemporalExtent model.
    """

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    schema_version: str | None = Field("candidate.v0.3", description="契约版本")
    candidate_id: str = Field(..., min_length=1)
    observation_refs: list[str] = Field(..., min_length=1)
    temporal_extent: TemporalExtent = Field(
        ..., description="跨当前场景的时间范围"
    )
    candidate_type: str = Field(
        ..., description="water_gain / water_loss / sar_backscatter_anomaly"
    )
    geometry: dict | None = None
    representative_geometry: dict | None = None
    union_geometry: dict | None = None
    score: float = Field(..., ge=0.0, le=1.0)
    score_type: ScoreType = Field(
        ScoreType.WITHIN_RUN_RANKING, description="评分类型"
    )
    score_components: dict | None = None
    quality_summary: dict | None = None
    persistence_status: CandidateStatus | None = Field(
        None, description="persistent / transient / uncertain"
    )
    occurrence_count: int | None = Field(
        None, ge=0, description="出现次数（跨当前场景）"
    )
    persistence_ratio: float | None = Field(None, ge=0.0, le=1.0)
    lifecycle: CandidateLifecycle | None = Field(
        CandidateLifecycle.PROPOSED,
        description="proposed / suppressed / superseded / aggregated",
    )
    suppression_reason: str | None = Field(
        None, description="当 lifecycle=suppressed 时必须提供"
    )
    supersedes: str | None = Field(
        None, description="替代的前一个 candidate_id"
    )
    superseded_by: str | None = Field(
        None, description="被哪个 candidate_id 替代"
    )
    source_modality: Literal["SAR_C", "OPTICAL_MULTI", "SAR_X"] | None = Field(
        None, description="源数据模态"
    )
    rule_version: str = Field(..., description="聚合规则版本")

    # ── Lifecycle cross-validation ──────────────────────────

    @model_validator(mode="after")
    def _validate_lifecycle(self) -> Self:
        """Suppressed requires reason; superseded requires superseded_by."""
        if self.lifecycle == CandidateLifecycle.SUPPRESSED:
            if not self.suppression_reason:
                raise ValueError(
                    "suppression_reason is required when "
                    "lifecycle='suppressed'"
                )
        if self.lifecycle == CandidateLifecycle.SUPERSEDED:
            if not self.superseded_by:
                raise ValueError(
                    "superseded_by is required when "
                    "lifecycle='superseded'"
                )
        return self

    @model_validator(mode="after")
    def _validate_observation_refs_unique(self) -> Self:
        """observation_refs must not contain duplicates."""
        refs = self.observation_refs
        if len(refs) != len(set(refs)):
            dups = [r for r in refs if refs.count(r) > 1]
            raise ValueError(
                f"Duplicate observation_refs found: {dups}"
            )
        return self
