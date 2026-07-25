"""
C0 — ReplayEntry

Replay 时间线的不可变条目。
sequence_number 连续递增，时间线不可覆盖。
每个节点有 object_ref 和 version。
"""

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


class ReplayEntry(BaseModel, frozen=True):
    replay_entry_id: str = Field(..., min_length=1)
    event_ref: str = Field(..., min_length=1)
    sequence_number: int = Field(..., ge=0)
    actor_type: Literal["system","model","human"] = Field(...)
    actor_ref: str = Field(...)
    action: str = Field(...)
    object_type: str = Field(...)
    object_ref: str = Field(...)
    object_version: int | None = Field(None, ge=1)
    reason: str | None = None
    metadata: dict = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
