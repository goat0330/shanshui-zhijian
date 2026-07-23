"""
AnomalyAlert — 经规则过滤后进入人工核验队列的告警
"""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

from .evidence import EvidenceBundle


class AnomalyAlert(BaseModel):
    """待核验告警"""
    alert_id: str = Field(..., description="告警 ID")
    bundle: EvidenceBundle = Field(..., description="关联证据包")
    status: Literal["pending", "confirmed", "rejected"] = Field("pending")
    rule_summary: str = Field("", description="触发规则说明")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    reviewed_at: str | None = Field(None)
    reviewed_by: str | None = Field(None)
    reject_reason: str | None = Field(None, description="驳回原因")
