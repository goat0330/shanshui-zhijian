"""
RS-00 契约 — PerceptionResult + RunContext + Observation

PerceptionResult 是感知工具的唯一返回对象。
Observation 是单次结构化观测。
"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from . import ExecutionStatus, TaskType, ObservationType, ScoreType
from .asset import SpatialMetadata


class Observation(BaseModel):
    """单次结构化观测。产品链从这里开始。"""
    schema_version: str = Field("rs-contract.v0.2", pattern=r"^rs-contract\.v[\d.]+$")
    observation_id: str = Field(..., min_length=1)
    perception_result_ref: str = Field(..., min_length=1)
    source_asset_refs: list[str] = Field(default_factory=list)
    source_task_type: TaskType
    observation_type: ObservationType
    label: str = Field(..., min_length=1)
    score: float = Field(..., ge=0.0, le=1.0)
    score_type: ScoreType
    geometry: dict | None = None
    geometry_crs: str | None = Field(None, description="geometry 的 CRS，如 EPSG:4326")
    bbox: list[float] | None = Field(None, min_length=4, max_length=4)
    temporal: dict | None = None
    quality: dict | None = None
    model_run_ref: str | None = None
    coordinate_space: str | None = Field(None, pattern=r"^(geographic|pixel|unknown)$")
    created_at: str | None = None


class QualityReport(BaseModel):
    """RS-01B-1 扩展质量报告。

    包含:
    - 输入质量指标
    - 轨道/极化/分辨率兼容性
    - 拒绝原因和警告
    """
    # 输入质量
    valid_pixel_ratio: float = Field(0.0, ge=0.0, le=1.0)
    nodata_ratio: float = Field(0.0, ge=0.0, le=1.0)
    finite_pixel_ratio: float = Field(0.0, ge=0.0, le=1.0)
    spatial_overlap_ratio: float = Field(0.0, ge=0.0, le=1.0)
    constant_pixel_ratio: float = Field(0.0, ge=0.0, le=1.0, description="常量像素比 (可能是无数据或饱和)")

    # 配准
    registration_quality: float | None = Field(None, ge=0.0, le=1.0)

    # 传感器
    sensor_comparability: bool | None = None
    cloud_ratio: float | None = Field(None, ge=0.0, le=1.0)

    # 动态范围
    vv_dynamic_range: tuple[float, float] | None = None
    vh_dynamic_range: tuple[float, float] | None = None

    # RS-01B-1 兼容性
    orbit_match: bool | None = Field(None, description="是否同轨")
    polarization_compatible: bool | None = Field(None, description="极化是否兼容")
    resolution_compatible: bool | None = Field(None, description="分辨率是否兼容")

    # RS-01B-2.2A: 多时相场景质量汇总
    accepted_scenes: int | None = Field(None, description="通过质量门禁的场景数")
    rejected_scenes: int | None = Field(None, description="被拒绝的场景数")
    warned_count: int | None = Field(None, description="有警告的场景数")

    # 拒绝与警告
    rejection_reason: str | None = Field(None, description="拒绝原因 (strict 模式)")
    recommendations: list[str] = Field(default_factory=list, description="建议/警告")

    # 原因列表 (向后兼容)
    reasons: list[str] = Field(default_factory=list)


class PerceptionResult(BaseModel):
    """感知工具的唯一返回对象。产品链和比赛链都从这里分叉。"""
    schema_version: str = Field("rs-contract.v0.2", pattern=r"^rs-contract\.v[\d.]+$")
    perception_result_id: str = Field(..., min_length=1)
    inference_task_ref: str = Field(..., min_length=1)
    task_spec_ref: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    status: ExecutionStatus
    observations: list[Observation] = Field(default_factory=list)
    artifact_refs: list[str] = Field(
        default_factory=list,
        description="派生 Asset ID（掩膜/栅格/GeoJSON），非 EvidenceRef",
    )
    quality_report: QualityReport | None = None
    diagnostics: dict | None = None
    started_at: str | None = None
    finished_at: str | None = None
