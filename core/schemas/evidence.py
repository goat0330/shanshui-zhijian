"""
EvidenceBundle — 同一异常的多源证据包
"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """单条证据"""
    type: str = Field(..., description="证据类型: rgb_tile / ndwi / mask / dem / sar")
    file_ref: str = Field(..., description="文件路径或引用")
    description: str = Field("", description="证据描述")
    acquired_at: str | None = Field(None, description="获取时间")


class EvidenceBundle(BaseModel):
    """证据包: 一个问题对应的所有证据"""
    bundle_id: str = Field(..., description="证据包 ID")
    detection_id: str = Field(..., description="关联的 DetectionResult ID")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    items: list[EvidenceItem] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict, description="汇总信息")
