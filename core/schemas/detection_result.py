"""
DetectionResult — 唯一跨链接口 Schema

兼容三种几何类型:
  - Polygon / MultiPolygon (NDWI 变化候选)
  - BoundingBox (目标检测框)
  - mask_ref (语义分割引用)

score 必须包含 score_type 字段说明来源
"""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class ModelMeta(BaseModel):
    """模型元信息"""
    name: str = "ndwi_otsu_change_baseline"
    version: str = "0.1.0"


class Geometry(BaseModel):
    """GeoJSON 几何对象"""
    type: Literal["Point", "MultiPoint", "LineString", "MultiLineString",
                  "Polygon", "MultiPolygon"] = "Polygon"
    coordinates: list[list[list[float]]]


class DetectionResult(BaseModel):
    """标准检测结果"""
    detection_id: str = Field(..., description="唯一标识，如 DET-CQ-0001")
    source_type: str = Field("sentinel_2", description="数据源类型")
    source_assets: list[str] = Field(default_factory=list, description="源文件列表")
    task_type: str = Field("water_extent_change",
                           description="任务类型: water_extent_change / object_detection / segmentation")
    category: str = Field("candidate", description="类别")

    # 几何 (三种形式至少提供一种)
    geometry: Geometry | None = Field(None, description="多边形几何 (变化候选/分割)")
    bbox: list[float] | None = Field(None, description="边界框 [xmin, ymin, xmax, ymax] (检测)")
    mask_ref: str | None = Field(None, description="掩膜文件路径引用 (分割)")

    observed_at: str = Field(..., description="观测时间")
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="置信度/规则分数")
    score_type: str = Field("rule_based", description="分数类型: rule_based / model_probability / ensemble")

    model: ModelMeta = Field(default_factory=ModelMeta)
    evidence_refs: list[str] = Field(default_factory=list, description="证据文件列表")
    properties: dict[str, Any] = Field(default_factory=dict, description="扩展属性")
