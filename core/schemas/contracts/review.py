"""
C0 — ReviewDecision

ReviewDecision 只允许追加，不允许 update 和 delete。
action 只允许: confirm, reject, reclassify, needs_more_evidence
使用 base_event_version 实现乐观并发控制。
"""

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class ReviewDecision(BaseModel, frozen=True):
    decision_id: str = Field(..., min_length=1)
    event_ref: str = Field(..., min_length=1)
    base_event_version: int = Field(..., ge=1)
    action: Literal["confirm","reject","reclassify","needs_more_evidence"] = Field(...)
    reason_code: str | None = None
    comment: str | None = None
    reviewer_ref: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    resulting_event_version: int = Field(..., ge=1)

    @model_validator(mode="after")
    def _check_version(self):
        if self.resulting_event_version != self.base_event_version + 1:
            raise ValueError(f"resulting({self.resulting_event_version}) != base+1({self.base_event_version+1})")
        return self


class Decision(BaseModel):
    decision_id: str = Field(..., min_length=1)
    event_ref: str = Field(..., min_length=1)
    decision_type: str = Field(...)
    input_refs: list[str] = Field(default_factory=list)
    rule_version: str = ""
    output: dict = Field(default_factory=dict)
    reason_codes: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
