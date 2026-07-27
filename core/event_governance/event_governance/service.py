import json
from datetime import datetime
from typing import Sequence

from sqlalchemy.orm import Session

from .models import (
    GovernanceCandidate,
    EvidenceBundle,
    ReviewDecision,
    GovernedEvent,
    ReplayRecord,
    OptimisticLockError,
    EventGovernanceError,
    REVIEW_DECISION_ACTIONS,
    EVENT_STATUS_VALUES,
    EVENT_STATUS_FORBIDDEN,
)
from .persistence import (
    CandidateRecord,
    EvidenceBundleRecord,
    ReviewRecord,
    GovernedEventRecord,
    ReplayRecordDB,
)

# Decision → status mapping
_DECISION_TO_STATUS = {
    "confirm": "confirmed",
    "reject": "rejected",
    "reclassify": "reclassified",
    "needs_more_evidence": "needs_more_evidence",
}


def intake_candidate(session: Session, candidate: GovernanceCandidate) -> GovernanceCandidate:
    existing = session.query(CandidateRecord).filter_by(candidate_id=candidate.candidate_id).first()
    if existing:
        return GovernanceCandidate(
            candidate_id=existing.candidate_id,
            source=existing.source,
            payload=json.loads(existing.payload),
            ingested_at=existing.ingested_at,
        )
    record = CandidateRecord(
        candidate_id=candidate.candidate_id,
        source=candidate.source,
        payload=json.dumps(candidate.payload),
        ingested_at=candidate.ingested_at,
    )
    session.add(record)
    session.flush()
    return candidate


def attach_evidence(session: Session, bundle: EvidenceBundle) -> EvidenceBundle:
    existing = session.query(EvidenceBundleRecord).filter_by(bundle_id=bundle.bundle_id).first()
    if existing:
        return EvidenceBundle(
            bundle_id=existing.bundle_id,
            candidate_id=existing.candidate_id,
            version=existing.version,
            items=json.loads(existing.items),
            status=existing.status,
            created_at=existing.created_at,
        )
    record = EvidenceBundleRecord(
        bundle_id=bundle.bundle_id,
        candidate_id=bundle.candidate_id,
        version=bundle.version,
        items=json.dumps([m.model_dump() for m in bundle.items]),
        status=bundle.status,
        created_at=bundle.created_at,
    )
    session.add(record)
    session.flush()
    return bundle


def _validate_status(status: str) -> None:
    """Validate that a status value is allowed and not forbidden."""
    if status in EVENT_STATUS_FORBIDDEN:
        raise EventGovernanceError(
            f"Status '{status}' is reserved for external systems and cannot be used"
        )
    if status not in EVENT_STATUS_VALUES:
        raise EventGovernanceError(
            f"Invalid status '{status}'. Allowed: {EVENT_STATUS_VALUES}"
        )


def review_bundle(session: Session, decision: ReviewDecision) -> ReviewDecision:
    # Validate decision action
    allowed_actions = {"confirm", "reject", "reclassify", "needs_more_evidence"}
    if decision.decision not in allowed_actions:
        raise EventGovernanceError(
            f"Invalid decision '{decision.decision}'. "
            f"Allowed: {allowed_actions}"
        )

    # Read EvidenceBundleRecord
    bundle = session.query(EvidenceBundleRecord).filter_by(bundle_id=decision.bundle_id).first()
    if not bundle:
        raise EventGovernanceError(f"EvidenceBundle {decision.bundle_id} not found")

    # Optimistic lock: version check
    if decision.expected_version != bundle.version:
        raise OptimisticLockError(
            f"Version conflict: expected {decision.expected_version}, current {bundle.version}"
        )

    # For reclassify, category is required
    if decision.decision == "reclassify" and not decision.category:
        raise EventGovernanceError("reclassify requires a non-empty category")

    # Determine target status
    target_status = _DECISION_TO_STATUS[decision.decision]
    _validate_status(target_status)

    # Write ReviewRecord
    review = ReviewRecord(
        review_id=decision.review_id,
        bundle_id=decision.bundle_id,
        reviewer=decision.reviewer,
        decision=decision.decision,
        reason=decision.reason,
        version_at_review=bundle.version,
        reviewed_at=decision.reviewed_at,
        category=decision.category,
        comment=decision.comment,
        candidate_id=decision.candidate_id,
    )
    session.add(review)

    # Increment bundle version
    bundle.version += 1
    bundle.status = "reviewed"

    # Auto-create new GovernedEventRecord version
    _auto_create_event_version(session, decision, target_status)

    # Write ReplayReplay timeline entry
    _append_replay_timeline(session, decision, target_status)

    session.flush()
    return decision


def _auto_create_event_version(
    session: Session, decision: ReviewDecision, target_status: str
) -> GovernedEventRecord:
    """Auto-create a new event version after a review decision."""
    # Find the candidate_id from decision or from evidence bundle
    candidate_id = decision.candidate_id
    if not candidate_id:
        bundle = session.query(EvidenceBundleRecord).filter_by(bundle_id=decision.bundle_id).first()
        if bundle:
            candidate_id = bundle.candidate_id

    if not candidate_id:
        raise EventGovernanceError("Cannot determine candidate_id for auto-creating event version")

    # Find the latest GovernedEventRecord by candidate_id
    latest = (
        session.query(GovernedEventRecord)
        .filter_by(candidate_id=candidate_id)
        .order_by(GovernedEventRecord.version.desc())
        .first()
    )
    if not latest:
        raise EventGovernanceError(
            f"No existing GovernedEventRecord found for candidate {candidate_id}. "
            f"Create one via record_event first."
        )

    # Determine new event_type
    new_event_type = latest.event_type
    if decision.decision == "reclassify" and decision.category:
        new_event_type = decision.category

    now = datetime.now().isoformat()
    new_record = GovernedEventRecord(
        event_id=latest.event_id,
        version=latest.version + 1,
        candidate_id=candidate_id,
        event_type=new_event_type,
        payload=latest.payload,
        status=target_status,
        created_at=latest.created_at,
        updated_at=now,
    )
    session.add(new_record)
    return new_record


def _next_sequence_number(session: Session, event_id: str) -> int:
    """Get the next sequence number for replay timeline entries for a given event."""
    max_seq = (
        session.query(ReplayRecordDB.sequence_number)
        .filter_by(event_id=event_id)
        .order_by(ReplayRecordDB.sequence_number.desc())
        .first()
    )
    if max_seq is None:
        return 1
    return max_seq[0] + 1


def _append_replay_timeline(
    session: Session, decision: ReviewDecision, target_status: str
) -> ReplayRecordDB:
    """Write a replay timeline entry for a review decision."""
    seq = _next_sequence_number(session, decision.bundle_id)
    now = datetime.now().isoformat()
    replay_id = f"replay-{decision.bundle_id}-{seq}-{now}"

    details = f"decision={decision.decision}"
    if decision.comment:
        details += f", comment={decision.comment}"
    if decision.category:
        details += f", new_category={decision.category}"

    record = ReplayRecordDB(
        event_id=decision.bundle_id,
        replay_id=replay_id,
        sequence_number=seq,
        actor_type="human",
        actor_ref=decision.reviewer,
        action=f"review_{decision.decision}",
        object_type="event",
        object_ref=decision.bundle_id,
        details=details,
        replayed_at=now,
    )
    session.add(record)
    return record


def record_event(session: Session, event: GovernedEvent) -> GovernedEvent:
    _validate_status(event.status)

    existing = (
        session.query(GovernedEventRecord)
        .filter_by(event_id=event.event_id, version=event.version)
        .first()
    )
    if existing:
        return GovernedEvent(
            event_id=existing.event_id,
            version=existing.version,
            candidate_id=existing.candidate_id,
            event_type=existing.event_type,
            payload=json.loads(existing.payload),
            status=existing.status,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )
    now = datetime.now().isoformat()
    record = GovernedEventRecord(
        event_id=event.event_id,
        version=event.version,
        candidate_id=event.candidate_id,
        event_type=event.event_type,
        payload=json.dumps(event.payload),
        status=event.status,
        created_at=event.created_at,
        updated_at=now,
    )
    session.add(record)
    session.flush()
    return event


def get_event(session: Session, event_id: str, version: int | None = None) -> GovernedEvent | None:
    if version is not None:
        row = session.query(GovernedEventRecord).filter_by(event_id=event_id, version=version).first()
    else:
        row = (
            session.query(GovernedEventRecord)
            .filter_by(event_id=event_id)
            .order_by(GovernedEventRecord.version.desc())
            .first()
        )
    if not row:
        return None
    return GovernedEvent(
        event_id=row.event_id,
        version=row.version,
        candidate_id=row.candidate_id,
        event_type=row.event_type,
        payload=json.loads(row.payload),
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def replay_event(session: Session, event_id: str, actor: str = "system") -> ReplayRecord:
    """Write a replay timeline entry. No longer simple dedup — each call appends a new entry.

    Returns the most recent ReplayRecord for the event (the one just written).
    """
    seq = _next_sequence_number(session, event_id)
    now = datetime.now().isoformat()
    replay_id = f"replay-{event_id}-{seq}-{now}"

    replay = ReplayRecord(
        replay_id=replay_id,
        event_id=event_id,
        sequence_number=seq,
        actor_type="system",
        actor_ref=actor,
        action="replayed",
        object_type="event",
        object_ref=event_id,
        details="event replayed via replay_event",
        replayed_at=now,
    )
    record = ReplayRecordDB(
        event_id=replay.event_id,
        replay_id=replay.replay_id,
        sequence_number=replay.sequence_number,
        actor_type=replay.actor_type,
        actor_ref=replay.actor_ref,
        action=replay.action,
        object_type=replay.object_type,
        object_ref=replay.object_ref,
        details=replay.details,
        replayed_at=replay.replayed_at,
    )
    session.add(record)
    session.flush()
    return replay


def get_timeline(session: Session, event_id: str) -> Sequence[ReplayRecord]:
    """Return all replay timeline entries for an event, ordered by sequence_number."""
    rows = (
        session.query(ReplayRecordDB)
        .filter_by(event_id=event_id)
        .order_by(ReplayRecordDB.sequence_number)
        .all()
    )
    return [
        ReplayRecord(
            replay_id=row.replay_id,
            event_id=row.event_id,
            sequence_number=row.sequence_number,
            actor_type=row.actor_type,
            actor_ref=row.actor_ref,
            action=row.action,
            object_type=row.object_type,
            object_ref=row.object_ref,
            details=row.details,
            replayed_at=row.replayed_at,
        )
        for row in rows
    ]


def vote_event(session: Session, candidate: GovernanceCandidate, event: GovernedEvent) -> tuple[GovernanceCandidate, GovernedEvent]:
    c = intake_candidate(session, candidate)
    e = record_event(session, event)
    return (c, e)
