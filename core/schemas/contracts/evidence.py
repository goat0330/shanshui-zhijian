"""
C0 — Evidence + EvidenceBundle

Evidence 是不可变观测或证据引用，不得被 ReviewDecision 修改。
EvidenceBundle 聚合多条证据，必须支持单模态 Bundle（缺失不解释为正常）。
"""

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Evidence(BaseModel, frozen=True):
    evidence_id: str = Field(..., min_length=1)
    evidence_type: str = Field(...)
    source_modality: str = Field(...)
    source_asset_ref: str = Field(..., min_length=1)
    derived_asset_ref: str | None = None
    candidate_ref: str | None = None
    captured_at: str | None = None
    geometry: dict | None = None
    geometry_crs: str | None = None
    stance: Literal["supporting","contradicting","mixed","unavailable"] = "supporting"
    quality_summary: dict | None = None
    provenance: dict | None = None
    unavailable_reason: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    @model_validator(mode="after")
    def _check_unavailable(self):
        if self.stance == "unavailable" and not self.unavailable_reason:
            raise ValueError("stance=unavailable 时必填 unavailable_reason")
        return self


class EvidenceBundle(BaseModel, frozen=True):
    bundle_id: str = Field(..., min_length=1)
    candidate_ref: str = Field(..., min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    modalities_present: list[str] = Field(default_factory=list)
    modalities_missing: list[str] = Field(default_factory=list)
    spatial_summary: dict | None = None
    temporal_summary: dict | None = None
    quality_summary: dict | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    assembler_version: str = "1.0.0"
