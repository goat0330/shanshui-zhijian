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


# ── Helper Functions ────────────────────────────────────────────


def compute_candidate_id(
    *,
    candidate_type: str,
    observation_refs: list[str] | tuple[str, ...],
    temporal_extent: dict | None = None,
    geometry: dict | None = None,
    quality_summary: dict | None = None,
    **extra_content: object,
) -> str:
    """Compute content-addressed candidate_id (SHA256).

    Any change in content → different hash. This indexes the *candidate content*,
    not the spatial object identity.
    """
    payload: dict = {
        "candidate_type": candidate_type,
        "observation_refs": sorted(observation_refs) if observation_refs else [],
    }
    if temporal_extent is not None:
        payload["temporal_extent"] = temporal_extent
    if geometry is not None:
        payload["geometry"] = geometry
    if quality_summary is not None:
        payload["quality_summary"] = quality_summary
    payload.update(extra_content)

    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_candidate_track_id(
    *,
    representative_geometry: dict | None = None,
    union_geometry: dict | None = None,
    candidate_type: str | None = None,
    **extra_stable: object,
) -> str:
    """Compute stable candidate_track_id from spatial identity.

    This indexes the *spatial object*, not the content. Same object across
    scenes/runs → same track_id.
    """
    geom = representative_geometry or union_geometry or {}
    payload: dict = {
        "geometry": json.dumps(geom, sort_keys=True, default=str),
    }
    if candidate_type is not None:
        payload["candidate_type"] = candidate_type
    payload.update(extra_stable)

    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_quality_factor(
    *,
    candidate_type: str,
    water_occurrence_mean: float | None = None,
    water_occurrence_std: float | None = None,
    valid_pixel_ratio: float | None = None,
    registration_quality: float | None = None,
    metadata_quality: float | None = None,
    **extra: float,
) -> dict:
    """Build per-type quality_factor dict.

    water_gain:
        stable_land_persistence = water_occurrence_mean
        (higher = more stable land → more confident gain)
    water_loss:
        stable_water_persistence = 1 - water_occurrence_mean
        (higher = more stable water → more confident loss)
    sar_backscatter_anomaly:
        Composite of valid_pixel_ratio + registration + metadata
    """
    qf: dict = {}

    if candidate_type == "water_gain":
        if water_occurrence_mean is None:
            raise ValueError("water_gain requires water_occurrence_mean")
        if valid_pixel_ratio is not None:
            raise ValueError("water_gain does not use valid_pixel_ratio")
        qf["stable_land_persistence"] = round(water_occurrence_mean, 4)
        qf["strength"] = round(water_occurrence_mean, 4)

    elif candidate_type == "water_loss":
        if water_occurrence_mean is None:
            raise ValueError("water_loss requires water_occurrence_mean")
        if valid_pixel_ratio is not None:
            raise ValueError("water_loss does not use valid_pixel_ratio")
        stability = 1.0 - water_occurrence_mean
        qf["stable_water_persistence"] = round(stability, 4)
        qf["strength"] = round(stability, 4)

    elif candidate_type == "sar_backscatter_anomaly":
        if valid_pixel_ratio is None:
            raise ValueError("anomaly requires valid_pixel_ratio")
        qf["valid_pixel_ratio"] = round(valid_pixel_ratio, 4)
        if registration_quality is not None:
            qf["registration_quality"] = round(registration_quality, 4)
        if metadata_quality is not None:
            qf["metadata_quality"] = round(metadata_quality, 4)
        # Composite strength: product of all available components
        components = [v for k, v in qf.items()
                      if k != "strength" and isinstance(v, (int, float))]
        strength = 1.0
        for v in components:
            strength *= v
        qf["strength"] = round(strength, 4)

    else:
        raise ValueError(f"Unknown candidate_type: {candidate_type}")

    qf.update(extra)
    return qf
