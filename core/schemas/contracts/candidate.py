"""
RS-00 — DetectionCandidate + EvidenceRef
"""

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    """证据引用。指向源资产或派生资产，用于产品研判阶段。"""
    evidence_id: str = Field(..., min_length=1)
    source_asset_ref: str = Field(..., min_length=1, description="源资产 ID")
    derived_asset_ref: str | None = Field(None, description="派生资产 ID")
    evidence_type: str = Field(..., description="rgb_tile / ndwi / change_mask / sar_vh / dem")
    spatial_window: dict | None = None
    temporal_window: dict | None = None
    description: str | None = None
    provenance: dict | None = None


class DetectionCandidate(BaseModel):
    """产品链：一个或多个 Observation 经聚合形成的不可变算法候选。"""
    candidate_id: str = Field(..., min_length=1)
    observation_refs: list[str] = Field(..., min_length=1)
    temporal_extent: dict = Field(..., description='{"start":..., "end":...}')
    candidate_type: str = Field(..., description="water_extent_change / suspected_floating / unknown")
    geometry: dict | None = None
    score: float = Field(..., ge=0.0, le=1.0)
    quality_summary: dict | None = None
    evidence_refs: list[str] = Field(default_factory=list, description="只引用 Evidence ID")
    rule_version: str = Field(..., description="聚合规则版本")
