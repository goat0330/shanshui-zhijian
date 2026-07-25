"""
RS-00 — DetectionCandidate + EvidenceRef

A2 扩展 (2026-07):
  - lifecycle + suppression_reason
  - supersedes / superseded_by
  - score_type + score_components
  - source_modality + persistence fields
  - schema_version 向后兼容
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
    """产品链：一个或多个 Observation 经聚合形成的不可变算法候选。

    Lifecycle (A2):
      - proposed: 刚生成
      - aggregated: 已关联进 Event
      - suppressed: 被抑制（质量/规则）
      - superseded: 被更正候选替代

    Scoring (A3):
      - score: candiate_rank_score (0-1, 运行内排名)
      - score_type: within_run_ranking — 非绝对概率
      - score_components: 分解贡献
    """
    schema_version: str = Field("candidate.v0.2", description="Schema 版本号")
    candidate_id: str = Field(..., min_length=1)
    observation_refs: list[str] = Field(..., min_length=1)
    temporal_extent: dict = Field(..., description='{"start":..., "end":...}')
    candidate_type: str = Field(..., description="water_extent_change / suspected_floating / unknown")
    geometry: dict | None = None
    score: float = Field(..., ge=0.0, le=1.0)
    score_type: str = Field("within_run_ranking",
                            description="score 语义: within_run_ranking | rule_based_ranking | calibrated_confidence")
    score_components: dict | None = Field(None, description="score 分解（权重×归一化值）")
    quality_summary: dict | None = None
    evidence_refs: list[str] = Field(default_factory=list, description="只引用 Evidence ID")
    rule_version: str = Field(..., description="聚合规则版本")

    # A2: lifecycle
    lifecycle: str = Field("proposed",
                            description="proposed | aggregated | suppressed | superseded")
    suppression_reason: str | None = Field(None, description="抑制原因（suppressed时必填）")
    supersedes: str | None = Field(None, description="替代的 Candidate ID")
    superseded_by: str | None = Field(None, description="被哪个 Candidate 替代")

    # A2: source info
    source_modality: str | None = Field(None, description="源模态, e.g. SAR_C")
    persistence_status: str | None = Field(
        None, description="persistent | transient | uncertain | unavailable")
    occurrence_count: int | None = Field(None, ge=0, description="出现景数")
    persistence_ratio: float | None = Field(None, ge=0.0, le=1.0)
