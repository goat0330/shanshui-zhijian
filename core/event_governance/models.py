from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class GovernanceCandidate(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    source: str = Field(..., description="source system identifier")
    payload: dict[str, Any] = Field(default_factory=dict)
    ingested_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def __hash__(self) -> int:
        return hash(self.candidate_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GovernanceCandidate):
            return NotImplemented
        return self.candidate_id == other.candidate_id

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False):
            raise AttributeError(f"Candidate is read-only after intake")
        super().__setattr__(name, value)


class EvidenceItem(BaseModel):
    evidence_id: str = Field(..., min_length=1)
    evidence_type: str = Field(..., description="rgb_tile / ndwi / mask / dem / sar")
    file_ref: str = Field(..., description="file path or URI")
    description: str = ""
    acquired_at: str | None = None


class EvidenceBundle(BaseModel):
    bundle_id: str = Field(..., min_length=1)
    candidate_id: str = Field(..., min_length=1)
    version: int = Field(default=1, ge=1)
    items: list[EvidenceItem] = Field(default_factory=list)
    status: Literal["draft", "submitted", "reviewed"] = "draft"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ReviewDecision(BaseModel):
    review_id: str = Field(..., min_length=1)
    bundle_id: str = Field(..., min_length=1)
    reviewer: str = Field(..., min_length=1)
    decision: Literal["approved", "rejected"]
    reason: str = ""
    expected_version: int = Field(default=1, ge=1)
    reviewed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class GovernedEvent(BaseModel):
    event_id: str = Field(..., min_length=1)
    version: Literal["v1", "v2"] = "v1"
    candidate_id: str = Field(..., min_length=1)
    event_type: str = Field(..., description="event classification")
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ReplayRecord(BaseModel):
    replay_id: str = Field(..., min_length=1)
    event_id: str = Field(..., min_length=1)
    replayed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    result: str = Field(default="ok")


class EventGovernanceError(Exception):
    pass


class OptimisticLockError(EventGovernanceError):
    pass


class IdempotentIntakeError(EventGovernanceError):
    pass


class ReplayDedupError(EventGovernanceError):
    pass
