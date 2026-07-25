"""
C0 — ReplayEntry

Replay 时间线的不可变条目。
sequence_number 连续递增，时间线不可覆盖。
每个节点有 object_ref 和 version。
"""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class ReplayEntry(BaseModel):
    """Replay 时间线条目。

    记录 Actor 在某个时间点对 Object 执行 Action 的审计日志。
    时间线不可覆盖，sequence_number 连续递增。
    Repository 重启后仍可重建同样时间线。
    """
    replay_entry_id: str = Field(..., min_length=1, description="Replay 条目 ID")
    event_ref: str = Field(..., min_length=1, description="关联 Event ID")

    sequence_number: int = Field(..., ge=0, description="连续序列号")
    actor_type: Literal["system", "model", "human"] = Field(
        ..., description="执行者类型"
    )
    actor_ref: str = Field(..., description="执行者引用（系统组件名/模型名/用户名）")
    action: str = Field(
        ..., description="动作: candidate_received / evidence_assembled / event_created / "
        "review_submitted / status_changed / event_version_created"
    )

    object_type: str = Field(..., description="操作对象类型: candidate / evidence / event / review")
    object_ref: str = Field(..., description="操作对象引用 ID")
    object_version: int | None = Field(None, ge=1, description="操作对象版本号（若有）")

    reason: str | None = Field(None, description="操作原因说明")
    metadata: dict = Field(default_factory=dict, description="扩展元数据")

    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="操作时间 (RFC 3339)",
    )
