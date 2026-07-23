"""
GovernanceEvent — 人工确认后进入正式治理流程的事件
"""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class GovernanceEvent(BaseModel):
    """正式治理事件"""
    event_id: str = Field(..., description="事件 ID")
    alert_id: str = Field(..., description="来源告警 ID")
    title: str = Field("", description="事件标题")
    status: Literal["open", "processing", "completed", "closed"] = Field("open")
    location_desc: str = Field("", description="位置描述")
    responsibility: str | None = Field(None, description="责任辖区/主体")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    closed_at: str | None = Field(None)
    notes: str = Field("", description="备注")
