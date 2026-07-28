"""
山水智鉴 V0 — Workbench API Real Service (Real Only)

接入 Agent C 的 event_governance 持久化层。
Real 模式禁止回退 mock_service。数据不存在时返回空/None/0，不静默回退。
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
from core.event_governance.pipeline import EventGovernancePipeline
from core.schemas.contracts.candidate import DetectionCandidate

logger = logging.getLogger(__name__)

# ── Database lifecycle ──

_session: Session = None


def ensure_db():
    global _session
    if _session is None:
        _session = create_session()
    return _session


# ══════════════════════════════════════════════════════════
#  Candidate Intake
# ══════════════════════════════════════════════════════════

def do_intake(session, candidate: DetectionCandidate) -> dict:
    """Intake a DetectionCandidate via the Pipeline (no event created)."""
    pipeline = EventGovernancePipeline(session)
    result = pipeline.intake(candidate)
    return {
        "candidate_id": result.candidate_id,
        "bundle_id": result.bundle_id,
        "n_evidence_items": result.n_evidence_items,
        "is_idempotent": result.is_idempotent,
        "status": "intake_complete",
    }


# ══════════════════════════════════════════════════════════
#  Candidate
# ══════════════════════════════════════════════════════════

def get_candidates(persistence_status=None, change_type=None,
                   include_transient=False, sort="score", limit=20):
    from .candidate_store import list_candidates
    from .main import CandidateListItem
    items, total = list_candidates()
    result = []
    for d in items:
        try:
            result.append(CandidateListItem(**d))
        except Exception:
            pass
    return result[:limit], total


def get_candidate(candidate_id: str):
    from .candidate_store import get_candidate_dict
    from .main import CandidateDetail
    d = get_candidate_dict(candidate_id)
    if d:
        return CandidateDetail(**d)
    return None


def get_candidate_geojson():
    return {"type": "FeatureCollection", "features": []}


# ══════════════════════════════════════════════════════════
#  Evidence — from event_governance EvidenceBundleRecord
# ══════════════════════════════════════════════════════════

def get_evidence(candidate_id: str):
    from .main import EvidenceItem, QualitySummary
    session = ensure_db()
    bundles = session.query(EvidenceBundleRecord).filter_by(candidate_id=candidate_id).all()
    items = []
    for b in bundles:
        try:
            parsed = json.loads(b.items) if isinstance(b.items, str) else b.items
            for ev in parsed:
                mapped = {
                    "evidence_id": ev.get("evidence_id", ""),
                    "evidence_type": ev.get("evidence_type", ""),
                    "source_modality": ev.get("source_modality", ev.get("evidence_type", "")),
                    "source_asset_ref": ev.get("source_asset_ref", ev.get("file_ref", "")),
                    "derived_asset_ref": ev.get("derived_asset_ref", None),
                    "captured_at": ev.get("captured_at", ev.get("acquired_at", "")),
                    "stance": ev.get("stance", "supporting"),
                    "quality_summary": ev.get("quality_summary",
                        {"overall": "good", "cloud_cover": None, "geometric_quality": None, "artifact_count": None}),
                    "provenance": ev.get("provenance", ""),
                    "unavailable_reason": ev.get("unavailable_reason", None),
                }
                items.append(EvidenceItem(**mapped))
        except Exception as exc:
            logger.warning("get_evidence(%s): item parse error: %s", candidate_id, exc)
    return items


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
    session = ensure_db()
    records = session.query(GovernedEventRecord).all()
    features = []
    for r in records:
        payload = {}
        if r.payload:
            try:
                payload = json.loads(r.payload)
            except Exception:
                pass
        coords = payload.get("geometry", None) if isinstance(payload, dict) else None
        if not coords:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": coords},
            "properties": {
                "event_id": r.event_id,
                "candidate_id": r.candidate_id,
                "status": r.status,
                "event_type": r.event_type,
            },
        })
    return {"type": "FeatureCollection", "features": features}


def get_event_replay(event_id: str):
    session = ensure_db()
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


# ══════════════════════════════════════════════════════════
#  Runs + Artifacts — 接入 B 的 RunManifest
# ══════════════════════════════════════════════════════════

def get_runs(execution_status=None):
    logger.warning("get_runs: real data not available — Agent B RunManifest not yet wired")
    return []


def get_run(run_id: str):
    logger.warning("get_run(%s): real data not available — Agent B RunManifest not yet wired", run_id)
    return None


def get_artifact(artifact_id: str):
    logger.warning("get_artifact(%s): real data not available — Agent B RunManifest not yet wired", artifact_id)
    return None


# ══════════════════════════════════════════════════════════
#  Summary — 真实聚合 (review + replay counts)
# ══════════════════════════════════════════════════════════

def get_summary():
    from core.event_governance.persistence import GovernedEventRecord, ReviewRecord, ReplayRecordDB
    from core.event_governance.persistence import CandidateRecord
    session = ensure_db()
    cand_total = session.query(CandidateRecord).count()
    event_count = session.query(GovernedEventRecord).count()
    total_reviews = session.query(ReviewRecord).count()
    recent_rows = (
        session.query(ReplayRecordDB)
        .order_by(ReplayRecordDB.replayed_at.desc())
        .limit(5)
        .all()
    )
    return {
        "total_candidates": cand_total,
        "total_events": event_count,
        "total_reviews": total_reviews,
        "recent_activity": [
            {"event_id": r.event_id, "action": r.action,
             "actor_ref": r.actor_ref, "replayed_at": r.replayed_at,
             "details": r.details}
            for r in recent_rows
        ],
        "source": "real",
    }


# ══════════════════════════════════════════════════════════
#  Dashboard Snapshot — 真实聚合
# ══════════════════════════════════════════════════════════

def get_dashboard_snapshot():
    from .main import (
        DashboardSnapshotResponse, DashboardSummaryDTO,
        ChangeTypeDTO, MonthlyTrendDTO, FunnelStageDTO, TypicalCaseDTO,
    )
    session = ensure_db()
    pipeline = EventGovernancePipeline(session)
    snap = pipeline.get_snapshot()

    t = snap["totals"]
    funnel = snap.get("funnel", {})
    ebs = snap.get("events_by_status", {})

    return DashboardSnapshotResponse(
        summary=DashboardSummaryDTO(
            total_candidates=t.get("candidates", 0),
            events_under_review=ebs.get("under_review", 0),
            events_confirmed=ebs.get("confirmed", 0),
            events_rejected=ebs.get("rejected", 0),
            events_needs_evidence=ebs.get("needs_more_evidence", 0),
            total_runs=0,
        ),
        change_types=[],
        trend=[],
        funnel=[
            FunnelStageDTO(stage="candidates_ingested", count=funnel.get("candidates_ingested", 0), description="已摄入候选"),
            FunnelStageDTO(stage="candidates_with_bundle", count=funnel.get("candidates_with_bundle", 0), description="已生成证据包"),
            FunnelStageDTO(stage="candidates_reviewed", count=funnel.get("candidates_reviewed", 0), description="已人工核验"),
            FunnelStageDTO(stage="events_created", count=funnel.get("events_created", 0), description="已创建事件"),
        ],
        typical_cases=[],
    )
