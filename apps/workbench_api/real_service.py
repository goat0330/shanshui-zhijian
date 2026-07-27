"""
山水智鉴 V0 — Workbench API Real Service

接入 Agent C 的 event_governance 持久化层。
V0-MOCK 不可用数据回退到 mock_service（带警告日志，不静默）。

TODO (Agent B/RunManifest):
  - get_runs, get_run, get_artifact 接入 B 的 RunManifest
  - get_candidates, get_candidate 接入 A 的 Candidate 存储
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from core.event_governance.models import (
    GovernanceCandidate,
    EvidenceBundle,
    ReviewDecision as GovernanceReview,
    GovernedEvent,
    ReplayRecord,
    EventGovernanceError,
    OptimisticLockError,
)
from core.event_governance.service import (
    intake_candidate,
    attach_evidence,
    review_bundle,
    record_event,
    get_event as get_governed_event,
    replay_event,
    get_timeline,
    vote_event,
)
from core.event_governance.persistence import create_session, EvidenceBundleRecord, GovernedEventRecord

from .main import (
    CandidateListItem, CandidateDetail, QualitySummary,
    EvidenceItem, ReviewDecision, EventDetail, EventVersion,
    RunDetail, ArtifactRef, ArtifactDetail,
)
from . import mock_service

logger = logging.getLogger(__name__)

# ── Database lifecycle ──

_session: Session = None


def ensure_db():
    global _session
    if _session is None:
        _session = create_session()
    return _session


# ══════════════════════════════════════════════════════════
#  Candidate
# ══════════════════════════════════════════════════════════

def get_candidates(persistence_status=None, change_type=None,
                   include_transient=False, sort="score", limit=20):
    logger.warning(
        "get_candidates: falling back to mock — Agent A Candidate storage not yet wired"
    )
    return mock_service.get_candidates(
        persistence_status=persistence_status,
        change_type=change_type,
        include_transient=include_transient,
        sort=sort, limit=limit,
    )


def get_candidate(candidate_id: str):
    logger.warning(
        "get_candidate(%s): falling back to mock — Agent A Candidate storage not yet wired",
        candidate_id,
    )
    return mock_service.get_candidate(candidate_id)


def get_candidate_geojson():
    logger.warning(
        "get_candidate_geojson: falling back to mock — Agent A not yet wired"
    )
    return mock_service.get_candidate_geojson()


# ══════════════════════════════════════════════════════════
#  Evidence (V0 回退 mock — 待 C 扩展 Stance/Quality)
# ══════════════════════════════════════════════════════════

def get_evidence(candidate_id: str):
    logger.warning(
        "get_evidence(%s): falling back to mock — C EvidenceBundle not yet wired",
        candidate_id,
    )
    return mock_service.get_evidence(candidate_id)


# ══════════════════════════════════════════════════════════
#  Review — 接入 C 的 event_governance
# ══════════════════════════════════════════════════════════

# Action verb from ReviewRequest → C's ReviewDecision.decision
_ACTION_TO_DECISION = {
    "confirm": "confirm",
    "reject": "reject",
    "reclassify": "reclassify",
    "needs_more_evidence": "needs_more_evidence",
}


def _ensure_review_prerequisites(session: Session, candidate_id: str) -> tuple[str, str]:
    """
    Ensure candidate, evidence bundle, and event record exist before review.
    
    Returns (bundle_id, event_id).
    """
    # 1. Intake candidate
    candidate = GovernanceCandidate(
        candidate_id=candidate_id, source="workbench", payload={},
    )
    intake_candidate(session, candidate)

    # 2. Ensure evidence bundle exists
    bundle_id = f"BUNDLE-{candidate_id}"
    existing_bundle = session.query(EvidenceBundleRecord).filter_by(
        bundle_id=bundle_id
    ).first()
    if not existing_bundle:
        bundle = EvidenceBundle(
            bundle_id=bundle_id,
            candidate_id=candidate_id,
            version=1,
            items=[],
            status="submitted",
        )
        attach_evidence(session, bundle)

    # 3. Ensure event record exists (needed by _auto_create_event_version)
    existing_event = (
        session.query(GovernedEventRecord)
        .filter_by(candidate_id=candidate_id)
        .first()
    )
    if not existing_event:
        event_id = f"EVT-{candidate_id}"
        event = GovernedEvent(
            event_id=event_id,
            version=1,
            candidate_id=candidate_id,
            event_type="unknown",
            payload={},
            status="under_review",
        )
        record_event(session, event)
    else:
        event_id = existing_event.event_id

    return bundle_id, event_id


def submit_review(candidate_id: str, review_data: dict):
    session = ensure_db()

    decision_action = review_data["action"]
    if decision_action not in _ACTION_TO_DECISION:
        raise EventGovernanceError(f"Unknown review action: {decision_action}")

    # Create prerequisites so C's review_bundle has everything it needs
    bundle_id, _ = _ensure_review_prerequisites(session, candidate_id)

    # Build C's ReviewDecision with correct field names
    decision = GovernanceReview(
        review_id=(
            f"REV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            f"-{uuid.uuid4().hex[:6]}"
        ),
        bundle_id=bundle_id,
        reviewer=review_data.get("actor_ref", "unknown"),
        decision=_ACTION_TO_DECISION[decision_action],
        reason=review_data["comment"],
        expected_version=review_data.get("base_version", 1),
        reviewed_at=datetime.now().isoformat(),
        category=review_data.get("category"),
        comment=review_data["comment"],
        candidate_id=candidate_id,
    )

    try:
        result = review_bundle(session, decision)
    except OptimisticLockError as e:
        logger.warning(
            "submit_review OptimisticLockError for %s: %s", candidate_id, e
        )
        raise EventGovernanceError(str(e))
    except EventGovernanceError as e:
        logger.warning(
            "submit_review EventGovernanceError for %s: %s", candidate_id, e
        )
        raise

    # Map C's ReviewDecision back to workbench ReviewDecision DTO
    return ReviewDecision(
        review_id=result.review_id,
        candidate_id=candidate_id,
        action=result.decision,
        category=result.category,
        comment=result.comment or result.reason,
        evidence_refs=[],
        actor_ref=result.reviewer,
        base_version=result.expected_version,
        reviewed_at=result.reviewed_at,
    )


# ══════════════════════════════════════════════════════════
#  Events — 接入 C 的 event_governance
# ══════════════════════════════════════════════════════════

def _governed_to_detail(event: GovernedEvent) -> EventDetail:
    """Convert C's GovernedEvent model to workbench EventDetail DTO."""
    return EventDetail(
        event_id=event.event_id,
        candidate_id=event.candidate_id,
        event_type=event.event_type,
        status=event.status,
        title=f"Event {event.event_id[:12]}",
        created_at=event.created_at,
        updated_at=event.updated_at or event.created_at,
        versions=[
            EventVersion(
                version=event.version,
                status=event.status,
                changed_by="system",
                changed_at=event.created_at,
                summary=f"Version {event.version} — {event.status}",
            )
        ],
    )


def get_events(status=None):
    session = ensure_db()
    try:
        query = session.query(GovernedEventRecord).order_by(
            GovernedEventRecord.event_id, GovernedEventRecord.version.desc()
        )
        if status:
            query = query.filter_by(status=status)
        records = query.all()

        if not records:
            return []

        # Group multiple versions under one EventDetail
        event_map: dict[str, EventDetail] = {}
        for r in records:
            if r.event_id not in event_map:
                payload = {}
                if r.payload:
                    try:
                        payload = json.loads(r.payload)
                    except (json.JSONDecodeError, TypeError):
                        payload = {}

                event_map[r.event_id] = EventDetail(
                    event_id=r.event_id,
                    candidate_id=r.candidate_id,
                    event_type=(
                        payload.get("event_type", "unknown")
                        if isinstance(payload, dict) else "unknown"
                    ),
                    status=r.status,
                    title=f"Event {r.event_id[:12]}",
                    created_at=r.created_at,
                    updated_at=r.updated_at or r.created_at,
                    versions=[EventVersion(
                        version=r.version,
                        status=r.status,
                        changed_by="system",
                        changed_at=r.created_at,
                        summary=f"v{r.version} — {r.status}",
                    )],
                )
            else:
                # Append version to existing event
                event_map[r.event_id].versions.append(EventVersion(
                    version=r.version,
                    status=r.status,
                    changed_by="system",
                    changed_at=r.created_at,
                    summary=f"v{r.version} — {r.status}",
                ))

        return list(event_map.values())

    except Exception:
        logger.warning("get_events: real query failed, falling back to mock", exc_info=True)

    return mock_service.get_events(status=status)


def get_event(event_id: str):
    session = ensure_db()
    try:
        event = get_governed_event(session, event_id)
        if event:
            return _governed_to_detail(event)
    except Exception:
        logger.warning("get_event(%s): real query failed, falling back to mock", event_id, exc_info=True)
    return mock_service.get_event(event_id)


def get_event_geojson():
    logger.warning(
        "get_event_geojson: falling back to mock — Agent A/C not yet wired"
    )
    return mock_service.get_event_geojson()


def get_event_replay(event_id: str):
    session = ensure_db()
    try:
        # Try looking up timeline by the event's associated bundle
        event = get_governed_event(session, event_id)
        if event:
            bundle_id = f"BUNDLE-{event.candidate_id}"
            timeline = get_timeline(session, bundle_id)
        else:
            timeline = get_timeline(session, event_id)

        return [
            {
                "replay_id": t.replay_id,
                "event_id": t.event_id,
                "sequence_number": t.sequence_number,
                "actor_type": t.actor_type,
                "actor_ref": t.actor_ref,
                "action": t.action,
                "object_type": t.object_type,
                "object_ref": t.object_ref,
                "details": t.details,
                "replayed_at": t.replayed_at,
            }
            for t in timeline
        ]
    except Exception:
        logger.warning(
            "get_event_replay(%s): real query failed, falling back to mock",
            event_id, exc_info=True,
        )
    return mock_service.get_event_replay(event_id)


# ══════════════════════════════════════════════════════════
#  Runs + Artifacts — 回退 mock (待 B 接入)
# ══════════════════════════════════════════════════════════

def get_runs(execution_status=None):
    logger.warning(
        "get_runs: falling back to mock — Agent B RunManifest not yet wired"
    )
    return mock_service.get_runs(execution_status=execution_status)


def get_run(run_id: str):
    logger.warning(
        "get_run(%s): falling back to mock — Agent B RunManifest not yet wired", run_id
    )
    return mock_service.get_run(run_id)


def get_artifact(artifact_id: str):
    logger.warning(
        "get_artifact(%s): falling back to mock — Agent B RunManifest not yet wired",
        artifact_id,
    )
    return mock_service.get_artifact(artifact_id)


# ══════════════════════════════════════════════════════════
#  Summary — mock (待 A/B/C 全部接入后可做真实聚合)
# ══════════════════════════════════════════════════════════

def get_summary():
    logger.warning(
        "get_summary: falling back to mock — aggregate from A/B/C not yet wired"
    )
    return mock_service.get_summary()
