"""
C0 — AnomalyEvent 版本化异常事件

V0 状态只允许:
  under_review, confirmed, rejected, needs_more_evidence

禁止使用: illegal, violation_confirmed, closed, dispatched

除非已有人工或业务规则证据支持。
Event 的状态迁移必须通过 ReviewDecision。
"""

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, model_validator

_FORBIDDEN = {"illegal", "violation_confirmed", "closed", "dispatched"}

class AnomalyEvent(BaseModel, frozen=True):
    schema_version: str = "event.v0.1-internal"
    event_id: str = Field(..., min_length=1)
    event_version: int = Field(1, ge=1)
    status: str = "under_review"
    category: str = "unknown"
    severity: str = "unassessed"
    geometry: dict | None = None
    temporal_extent: dict | None = None
    candidate_refs: list[str] = Field(default_factory=list)
    evidence_bundle_refs: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)
    previous_version_ref: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    @model_validator(mode="after")
    def _check_forbidden(self):
        if self.status in _FORBIDDEN:
            raise ValueError(f"禁止使用状态: {self.status}")
        return self

    def new_version(self, **updates) -> "AnomalyEvent":
        d = self.model_dump()
        d.update(updates)
        d["event_version"] = self.event_version + 1
        d["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if not updates.get("previous_version_ref"):
            d["previous_version_ref"] = f"{self.event_id}@v{self.event_version}"
        return AnomalyEvent(**d)
