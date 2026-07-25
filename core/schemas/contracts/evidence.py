"""
C0 — Evidence + EvidenceBundle

Evidence 是不可变观测或证据引用，不得被 ReviewDecision 修改。
EvidenceBundle 聚合多条证据，必须支持单模态 Bundle（缺失不解释为正常）。
"""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """不可变观测或证据引用。

    不得被 ReviewDecision 修改。
    引用源资产或派生资产，用于产品研判阶段。
    """
    evidence_id: str = Field(..., min_length=1, description="证据 ID")
    evidence_type: str = Field(..., description="证据类型: rgb_tile / change_mask / sar_vh / dem / ndwi / change_polygon")
    source_modality: str = Field(..., description="源模态: SAR_C / OPTICAL_MULTI / DEM / VIDEO / UNKNOWN")
    source_asset_ref: str = Field(..., min_length=1, description="源资产 ID")
    derived_asset_ref: str | None = Field(None, description="派生资产 ID（裁剪/切片/渲染）")
    candidate_ref: str | None = Field(None, description="关联 Candidate ID（可空，证据可独立存在）")
    captured_at: str | None = Field(None, description="捕获/采集时间 (RFC 3339)")
    geometry: dict | None = Field(None, description="GeoJSON 几何")
    geometry_crs: str | None = Field(None, description="geometry 的 CRS，如 EPSG:4326")
    stance: Literal["supporting", "contradicting", "mixed", "unavailable"] = Field(
        "supporting", description="证据立场"
    )
    quality_summary: dict | None = Field(None, description="证据质量摘要（不压缩为单一 good/bad）")
    provenance: dict | None = Field(None, description="派生方式/工具版本/处理链")
    unavailable_reason: str | None = Field(
        None, description="当 stance=unavailable 时，说明不可用原因"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="创建时间 (RFC 3339)",
    )


class EvidenceBundle(BaseModel):
    """证据包：对一个 Candidate 的所有证据的聚合。

    必须支持单模态 EvidenceBundle。
    缺失另一模态不能被解释为"正常"；必须显式记录 modalities_missing。
    """
    bundle_id: str = Field(..., min_length=1, description="证据包 ID")
    candidate_ref: str = Field(..., min_length=1, description="关联 Candidate ID")
    evidence_refs: list[str] = Field(default_factory=list, description="Evidence ID 列表")
    modalities_present: list[str] = Field(
        default_factory=list,
        description="存在的模态列表，如 ['SAR_C', 'OPTICAL_MULTI']",
    )
    modalities_missing: list[str] = Field(
        default_factory=list,
        description="缺失的模态列表（不能解释为正常）",
    )
    spatial_summary: dict | None = Field(None, description="空间汇总信息")
    temporal_summary: dict | None = Field(None, description="时间汇总信息")
    quality_summary: dict | None = Field(None, description="质量汇总（不压缩为单一 good/bad）")
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="创建时间 (RFC 3339)",
    )
    assembler_version: str = Field("1.0.0", description="Assembly 规则版本")
