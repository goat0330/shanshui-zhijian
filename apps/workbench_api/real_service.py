"""
山水智鉴 V0 — Workbench API Real Service

接入 Agent C 的 event_governance 持久化层。
V0-MOCK 不可用数据回退到 mock_service。

TODO (Agent B/RunManifest):
  - get_runs, get_run, get_artifact 接入 B 的 RunManifest
"""

import json
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
    vote_event,
)
from core.event_governance.persistence import create_session

from .main import (
    CandidateListItem, CandidateDetail, QualitySummary,
    EvidenceItem, ReviewDecision, EventDetail, EventVersion,
    RunDetail, ArtifactRef, ArtifactDetail,
)
from . import mock_service

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
    # V0: 回退到 mock — TODO: 接入 A 的 Candidate 存储
    return mock_service.get_candidates(
        persistence_status=persistence_status,
        change_type=change_type,
        include_transient=include_transient,
        sort=sort, limit=limit,
    )


def get_candidate(candidate_id: str):
    return mock_service.get_candidate(candidate_id)


def get_candidate_geojson():
    return mock_service.get_candidate_geojson()


# ══════════════════════════════════════════════════════════
#  Evidence (V0 回退 mock — 待 C 扩展 Stance/Quality)
# ══════════════════════════════════════════════════════════

def get_evidence(candidate_id: str):
    return mock_service.get_evidence(candidate_id)


# ══════════════════════════════════════════════════════════
#  Review — 接入 C 的 event_governance
# ══════════════════════════════════════════════════════════

def submit_review(candidate_id: str, review_data: dict):
    session = ensure_db()

    decision = GovernanceReview(
        review_id=f"REV-{datetime.now().strftime('%Y%m%d%H%M%S')}-{candidate_id[-4:]}",
        candidate_id=candidate_id,
        action=review_data["action"],
        category=review_data.get("category"),
        comment=review_data["comment"],
        evidence_refs=review_data.get("evidence_refs", []),
        actor_ref=review_data.get("actor_ref", "unknown"),
        base_version=review_data.get("base_version", 1),
        reviewed_at=datetime.now().isoformat(),
    )

    try:
        result = review_bundle(session, candidate_id, decision)
    except OptimisticLockError as e:
        raise EventGovernanceError(str(e))
    except EventGovernanceError:
        # Fall back to mock for non-governance candidates
        return mock_service.submit_review(candidate_id, review_data)

    return ReviewDecision(
        review_id=result.review_id,
        candidate_id=result.candidate_id,
        action=result.action,
        category=result.category,
        comment=result.comment,
        evidence_refs=result.evidence_refs,
        actor_ref=result.actor_ref,
        base_version=result.base_version,
        reviewed_at=result.reviewed_at,
    )


# ══════════════════════════════════════════════════════════
#  Events — 接入 C 的 event_governance
# ══════════════════════════════════════════════════════════

def _governed_to_detail(event: GovernedEvent) -> EventDetail:
    return EventDetail(
        event_id=event.event_id,
        candidate_id=event.candidate_id,
        event_type=getattr(event, 'event_type', 'unknown'),
        status=event.status,
        title=f"Event {event.event_id[:12]}",
        created_at=event.created_at,
        updated_at=getattr(event, 'updated_at', event.created_at),
        versions=[
            EventVersion(version=1, status=event.status,
                         changed_by="system",
                         changed_at=event.created_at,
                         summary=f"Version 1 — {event.status}")
        ],
    )


def get_events(status=None):
    session = ensure_db()
    try:
        # V0: 从 C 的 event_governance 读取所有事件
        from core.event_governance.persistence import GovernedEventRecord
        query = session.query(GovernedEventRecord)
        if status:
            query = query.filter_by(status=status)
        records = query.all()
        if records:
            return [
                EventDetail(
                    event_id=r.event_id,
                    candidate_id=r.candidate_id,
                    event_type=r.payload.get("event_type", "unknown")
                    if isinstance(r.payload, dict) else "unknown",
                    status=r.status,
                    title=f"Event {r.event_id[:12]}",
                    created_at=r.created_at,
                    updated_at=r.updated_at or r.created_at,
                    versions=[
                        EventVersion(
                            version=r.version, status=r.status,
                            changed_by="system", changed_at=r.created_at,
                            summary=f"v{r.version} — {r.status}",
                        )
                    ],
                )
                for r in records
            ]
    except Exception:
        pass
    # Fallback to mock
    return mock_service.get_events(status=status)


def get_event(event_id: str):
    session = ensure_db()
    try:
        event = get_governed_event(session, event_id)
        if event:
            return _governed_to_detail(event)
    except Exception:
        pass
    return mock_service.get_event(event_id)


def get_event_geojson():
    return mock_service.get_event_geojson()


def get_event_replay(event_id: str):
    return mock_service.get_event_replay(event_id)


# ══════════════════════════════════════════════════════════
#  Runs + Artifacts — 回退 mock (待 B 接入)
# ══════════════════════════════════════════════════════════

def get_runs(execution_status=None):
    return mock_service.get_runs(execution_status=execution_status)


def get_run(run_id: str):
    return mock_service.get_run(run_id)


def get_artifact(artifact_id: str):
    return mock_service.get_artifact(artifact_id)


# ══════════════════════════════════════════════════════════
#  Summary — mock (待 A/B/C 全部接入后可做真实聚合)
# ══════════════════════════════════════════════════════════

def get_summary():
    return mock_service.get_summary()
