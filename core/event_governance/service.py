import json
from datetime import datetime

from sqlalchemy.orm import Session

from .models import (
    GovernanceCandidate,
    EvidenceBundle,
    ReviewDecision,
    GovernedEvent,
    ReplayRecord,
    OptimisticLockError,
    EventGovernanceError,
)
from .persistence import (
    CandidateRecord,
    EvidenceBundleRecord,
    ReviewRecord,
    GovernedEventRecord,
    ReplayRecordDB,
)


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


def review_bundle(session: Session, decision: ReviewDecision) -> ReviewDecision:
    bundle = session.query(EvidenceBundleRecord).filter_by(bundle_id=decision.bundle_id).first()
    if not bundle:
        raise EventGovernanceError(f"EvidenceBundle {decision.bundle_id} not found")
    if decision.expected_version != bundle.version:
        raise OptimisticLockError(
            f"Version conflict: expected {decision.expected_version}, current {bundle.version}"
        )
    review = ReviewRecord(
        review_id=decision.review_id,
        bundle_id=decision.bundle_id,
        reviewer=decision.reviewer,
        decision=decision.decision,
        reason=decision.reason,
        version_at_review=bundle.version,
        reviewed_at=decision.reviewed_at,
    )
    bundle.version += 1
    bundle.status = "reviewed"
    session.add(review)
    session.flush()
    return decision


def record_event(session: Session, event: GovernedEvent) -> GovernedEvent:
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
            created_at=existing.created_at,
        )
    record = GovernedEventRecord(
        event_id=event.event_id,
        version=event.version,
        candidate_id=event.candidate_id,
        event_type=event.event_type,
        payload=json.dumps(event.payload),
        created_at=event.created_at,
    )
    session.add(record)
    session.flush()
    return event


def get_event(session: Session, event_id: str, version: str | None = None) -> GovernedEvent | None:
    if version:
        row = session.query(GovernedEventRecord).filter_by(event_id=event_id, version=version).first()
    else:
        row = (
            session.query(GovernedEventRecord)
            .filter_by(event_id=event_id)
            .order_by(GovernedEventRecord.id.desc())
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
        created_at=row.created_at,
    )


def replay_event(session: Session, event_id: str) -> ReplayRecord:
    existing = session.query(ReplayRecordDB).filter_by(event_id=event_id).first()
    if existing:
        return ReplayRecord(
            replay_id=existing.replay_id,
            event_id=existing.event_id,
            replayed_at=existing.replayed_at,
            result=existing.result,
        )
    replay = ReplayRecord(
        replay_id=f"replay-{event_id}-{datetime.now().isoformat()}",
        event_id=event_id,
        result="ok",
    )
    record = ReplayRecordDB(
        event_id=replay.event_id,
        replay_id=replay.replay_id,
        replayed_at=replay.replayed_at,
        result=replay.result,
    )
    session.add(record)
    session.flush()
    return replay


def vote_event(session: Session, candidate: GovernanceCandidate, event: GovernedEvent) -> tuple[GovernanceCandidate, GovernedEvent]:
    c = intake_candidate(session, candidate)
    e = record_event(session, event)
    return (c, e)
