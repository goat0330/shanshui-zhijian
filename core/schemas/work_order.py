"""
WorkOrder — 事件拆分的处置任务
"""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class WorkOrder(BaseModel):
    """处置工单"""
    order_id: str = Field(..., description="工单 ID")
    event_id: str = Field(..., description="关联事件 ID")
    title: str = Field("", description="工单标题")
    assignee: str = Field("", description="处置人")
    status: Literal["pending", "in_progress", "completed", "rejected"] = Field("pending")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = Field(None)
    feedback: str = Field("", description="处置反馈")
    photos: list[str] = Field(default_factory=list, description="现场照片路径")
