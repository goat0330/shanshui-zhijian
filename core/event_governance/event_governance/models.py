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


# Allowed review decision actions
REVIEW_DECISION_ACTIONS = Literal["confirm", "reject", "reclassify", "needs_more_evidence"]


class ReviewDecision(BaseModel):
    review_id: str = Field(..., min_length=1)
    bundle_id: str = Field(..., min_length=1)
    reviewer: str = Field(..., min_length=1)
    decision: REVIEW_DECISION_ACTIONS
    reason: str = ""
    expected_version: int = Field(default=1, ge=1)
    reviewed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    # reclassify support: new category when reclassifying
    category: str | None = None
    # human-readable comment
    comment: str = ""
    # optional candidate reference
    candidate_id: str | None = None


# Allowed GovernedEvent status values
EVENT_STATUS_VALUES = {"under_review", "confirmed", "rejected", "reclassified", "needs_more_evidence"}
# Forbidden status values (dedicated to other systems)
EVENT_STATUS_FORBIDDEN = {"illegal", "violation_confirmed", "closed", "dispatched"}


class GovernedEvent(BaseModel):
    event_id: str = Field(..., min_length=1)
    version: int = Field(default=1, ge=1)
    candidate_id: str = Field(..., min_length=1)
    event_type: str = Field(..., description="event classification")
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str = "under_review"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str | None = None


class ReplayRecord(BaseModel):
    replay_id: str = Field(..., min_length=1)
    event_id: str = Field(..., min_length=1)
    sequence_number: int = Field(default=0, ge=0)
    actor_type: str = Field(default="system", description="system / human")
    actor_ref: str = Field(default="", description="identifier of the actor")
    action: str = Field(default="", description="what was done")
    object_type: str = Field(default="event", description="type of object acted upon")
    object_ref: str = Field(default="", description="identifier of the object")
    details: str = ""
    replayed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class EventGovernanceError(Exception):
    pass


class OptimisticLockError(EventGovernanceError):
    pass


class IdempotentIntakeError(EventGovernanceError):
    pass


class ReplayDedupError(EventGovernanceError):
    pass
