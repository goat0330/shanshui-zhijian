"""
RS-00 — DetectionCandidate + EvidenceRef

G0.3-A: candidate.v0.3 — frozen=True, enum-constrained fields,
        TemporalExtent with index/time split, content-addressed ID.
"""

from __future__ import annotations

import copy
import hashlib
import json
from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator, ConfigDict


CANDIDATE_V0_3 = "candidate.v0.3"


# ── Enums ─────────────────────────────────────────────────────


class CandidateLifecycle(str, Enum):
    PROPOSED = "proposed"
    SUPPRESSED = "suppressed"
    SUPERSEDED = "superseded"
    AGGREGATED = "aggregated"


class ScoreType(str, Enum):
    """score_type 固定在 within_run_ranking。"""
    WITHIN_RUN_RANKING = "within_run_ranking"


class CandidateStatus(str, Enum):
    PERSISTENT = "persistent"
    TRANSIENT = "transient"
    UNCERTAIN = "uncertain"


# ── TemporalExtent model ─────────────────────────────────────


class TemporalExtent(BaseModel):
    """时间范围：gauge 场次序号 (index) + 绝对时间 (time)，各自独立。"""
    model_config = ConfigDict(frozen=True)

    start_index: int = Field(..., description="起始 gauge 场次序号 (0-based)")
    end_index: int = Field(..., description="结束 gauge 场次序号 (inclusive)")
    start_time: str | float | None = Field(
        None, description="ISO-8601 或 unix-ts 首观测时间"
    )
    end_time: str | float | None = Field(
        None, description="ISO-8601 或 unix-ts 末观测时间"
    )

    @model_validator(mode="after")
    def _validate_indices(self) -> Self:
        if self.end_index < self.start_index:
            raise ValueError(
                f"end_index ({self.end_index}) < start_index ({self.start_index})"
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
    """产品链：不可变算法候选 (Contract v0.3)。

    G0.3-A:
    - schema_version=Literal["candidate.v0.3"]
    - frozen=True + tuple obs_refs + deep copy geometry/quality
    - candidate_id (SHA256 content) + candidate_track_id (stable spatial)
    - per-type quality_factor
    """

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    # ── Version ──
    schema_version: Literal[CANDIDATE_V0_3] = Field(
        default=CANDIDATE_V0_3, description="契约版本 (frozen)"
    )

    # ── Identity ──
    candidate_id: str = Field(..., min_length=1, description="内容 SHA256 哈希")
    candidate_track_id: str = Field(..., min_length=1, description="稳定空间对象 ID (跨运行不变)")

    # ── References ──
    observation_refs: tuple[str, ...] = Field(
        ..., description="源 Observation ID 列表 (tuple, 不可变)"
    )
    evidence_refs: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Evidence ID 引用 (不可变)",
    )

    # ── Temporal ──
    temporal_extent: TemporalExtent = Field(
        ..., description="时间范围 (index + timestamp)"
    )

    # ── Classification ──
    candidate_type: str = Field(
        ..., description="water_gain / water_loss / sar_backscatter_anomaly"
    )
    source_modality: Literal["SAR_C", "OPTICAL_MULTI", "SAR_X"] | None = Field(
        None, description="源数据模态"
    )

    # ── Geometry ──
    geometry: dict | None = None
    representative_geometry: dict | None = None
    union_geometry: dict | None = None

    # ── Scoring ──
    score: float = Field(..., ge=0.0, le=1.0)
    score_type: ScoreType = Field(
        ScoreType.WITHIN_RUN_RANKING, description="评分类型"
    )
    score_components: dict | None = None

    # ── Quality ──
    quality_summary: dict | None = None
    quality_factor: dict | None = Field(
        None, description="Per-type quality: water_gain/water_loss/anomaly"
    )

    # ── Lifecycle ──
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

    # ── Persistence (跨场景跟踪) ──
    persistence_status: CandidateStatus | None = Field(
        None, description="persistent / transient / uncertain"
    )
    occurrence_count: int | None = Field(None, ge=0, description="出现次数（跨当前场景）")
    persistence_ratio: float | None = Field(None, ge=0.0, le=1.0)

    # ── Provenance ──
    rule_version: str = Field(..., description="聚合规则版本")

    # ── Model Validators ──────────────────────────────────────

    @model_validator(mode="before")
    @classmethod
    def _deep_copy_mutable_fields(cls, data: dict) -> dict:
        """Deep copy geometry and quality fields to prevent external mutation."""
        for key in (
            "geometry", "representative_geometry", "union_geometry",
            "quality_summary", "quality_factor", "score_components",
        ):
            if key in data and data[key] is not None:
                data[key] = copy.deepcopy(data[key])
        return data

    @model_validator(mode="before")
    @classmethod
    def _coerce_refs_to_tuple(cls, data: dict) -> dict:
        """Ensure observation_refs and evidence_refs are tuples."""
        refs = data.get("observation_refs")
        if refs is not None and not isinstance(refs, tuple):
            data["observation_refs"] = tuple(refs)
        erefs = data.get("evidence_refs")
        if erefs is not None and not isinstance(erefs, tuple):
            data["evidence_refs"] = tuple(erefs)
        return data

    @model_validator(mode="after")
    def _validate_observation_refs_unique(self) -> Self:
        """observation_refs must not contain duplicates."""
        if len(self.observation_refs) != len(set(self.observation_refs)):
            dups = [r for r in self.observation_refs
                    if self.observation_refs.count(r) > 1]
            raise ValueError(f"Duplicate observation_refs found: {dups}")
        return self

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
