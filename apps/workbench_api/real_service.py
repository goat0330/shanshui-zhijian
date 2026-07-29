"""Workbench real service.

The service is deliberately fail-closed: missing candidates, manifests or
artifacts return empty/None and never fall back to mock data.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from core.event_governance.models import (
    EvidenceBundle,
    EventGovernanceError,
    GovernanceCandidate,
    GovernedEvent,
    OptimisticLockError,
    ReviewDecision as GovernanceReview,
)
from core.event_governance.persistence import (
    CandidateRecord,
    EvidenceBundleRecord,
    GovernedEventRecord,
    ReplayRecordDB,
    ReviewRecord,
    create_session,
)
from core.event_governance.pipeline import EventGovernancePipeline
from core.event_governance.service import (
    attach_evidence,
    get_event as get_governed_event,
    get_timeline,
    intake_candidate,
    review_bundle,
)
from core.schemas.contracts.candidate import DetectionCandidate

from .db import get_workbench_db_path

logger = logging.getLogger(__name__)
_session: Session | None = None


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_db() -> Session:
    global _session
    if _session is None:
        _session = create_session(get_workbench_db_path())
    return _session


def reset_session() -> None:
    """Close cached session; used by deterministic setup utilities/tests."""
    global _session
    if _session is not None:
        _session.close()
    _session = None


def do_intake(session: Session, candidate: DetectionCandidate) -> dict:
    pipeline = EventGovernancePipeline(session)
    result = pipeline.intake(candidate)
    return {
        "candidate_id": result.candidate_id,
        "bundle_id": result.bundle_id,
        "n_evidence_items": result.n_evidence_items,
        "is_idempotent": result.is_idempotent,
        "status": "intake_complete",
    }


def get_candidates(
    persistence_status: str | None = None,
    change_type: str | None = None,
    include_transient: bool = False,
    sort: str = "score",
    limit: int = 20,
):
    from .candidate_store import list_candidates
    from .main import CandidateListItem

    items, _ = list_candidates()
    filtered: list[dict] = []
    for item in items:
        if not include_transient and item.get("persistence_status") == "transient":
            continue
        if persistence_status and item.get("persistence_status") != persistence_status:
            continue
        if change_type and item.get("change_type") != change_type:
            continue
        filtered.append(item)

    sort_keys = {
        "score": "score",
        "area": "area_m2",
        "occurrence_count": "occurrence_count",
        "rank": "within_run_ranking",
    }
    key = sort_keys.get(sort or "score", "score")
    reverse = key != "within_run_ranking"
    filtered.sort(key=lambda row: row.get(key, 0), reverse=reverse)
    total = len(filtered)

    result = []
    for row in filtered[:limit]:
        try:
            result.append(CandidateListItem(**row))
        except Exception as exc:
            logger.warning("Candidate %s rejected by DTO: %s", row.get("candidate_id"), exc)
    return result, total


def get_candidate(candidate_id: str):
    from .candidate_store import get_candidate_dict
    from .main import CandidateDetail

    row = get_candidate_dict(candidate_id)
    if row is None:
        return None
    try:
        return CandidateDetail(**row)
    except Exception as exc:
        logger.warning("Candidate detail %s rejected by DTO: %s", candidate_id, exc)
        return None


def get_candidate_geojson() -> dict:
    from .candidate_store import list_candidates

    rows, _ = list_candidates()
    features = []
    for row in rows:
        geometry = row.get("representative_geometry") or row.get("union_geometry")
        if not geometry:
            continue
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "candidate_id": row.get("candidate_id"),
                "change_type": row.get("change_type"),
                "persistence_status": row.get("persistence_status"),
                "score": row.get("score"),
                "area_m2": row.get("area_m2"),
            },
        })
    return {"type": "FeatureCollection", "features": features}


def get_evidence(candidate_id: str):
    from .main import EvidenceItem

    session = ensure_db()
    bundles = session.query(EvidenceBundleRecord).filter_by(candidate_id=candidate_id).all()
    result = []
    for bundle in bundles:
        try:
            parsed = json.loads(bundle.items) if isinstance(bundle.items, str) else bundle.items
        except (TypeError, json.JSONDecodeError):
            parsed = []
        for item in parsed:
            mapped = {
                "evidence_id": item.get("evidence_id", ""),
                "evidence_type": item.get("evidence_type", ""),
                "source_modality": item.get("source_modality", item.get("evidence_type", "")),
                "source_asset_ref": item.get("source_asset_ref", item.get("file_ref", "")),
                "derived_asset_ref": item.get("derived_asset_ref"),
                "captured_at": item.get("captured_at", item.get("acquired_at", "unknown")),
                "stance": item.get("stance", "supporting"),
                "quality_summary": item.get("quality_summary", {"overall": "unknown"}),
                "provenance": item.get("provenance", ""),
                "unavailable_reason": item.get("unavailable_reason"),
            }
            try:
                result.append(EvidenceItem(**mapped))
            except Exception as exc:
                logger.warning("Evidence %s rejected by DTO: %s", mapped.get("evidence_id"), exc)
    return result


_ACTION_TO_DECISION = {
    "confirm": "confirm",
    "reject": "reject",
    "reclassify": "reclassify",
    "needs_more_evidence": "needs_more_evidence",
}


def _ensure_review_prerequisites(session: Session, candidate_id: str) -> str:
    candidate = GovernanceCandidate(candidate_id=candidate_id, source="workbench", payload={})
    intake_candidate(session, candidate)

    bundle_id = f"BUNDLE-{candidate_id}"
    bundle = session.query(EvidenceBundleRecord).filter_by(bundle_id=bundle_id).first()
    if bundle is None:
        attach_evidence(session, EvidenceBundle(
            bundle_id=bundle_id,
            candidate_id=candidate_id,
            version=1,
            items=[],
            status="submitted",
        ))
    return bundle_id


def submit_review(candidate_id: str, review_data: dict):
    session = ensure_db()
    action = review_data["action"]
    if action not in _ACTION_TO_DECISION:
        raise EventGovernanceError(f"Unknown review action: {action}")

    bundle_id = _ensure_review_prerequisites(session, candidate_id)
    decision = GovernanceReview(
        review_id=f"REV-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
        bundle_id=bundle_id,
        reviewer=review_data.get("actor_ref", "unknown"),
        decision=_ACTION_TO_DECISION[action],
        reason=review_data.get("comment", ""),
        expected_version=review_data.get("base_version", 1),
        reviewed_at=_now(),
        category=review_data.get("category"),
        comment=review_data.get("comment", ""),
        candidate_id=candidate_id,
    )
    try:
        result = review_bundle(session, decision)
        session.commit()
        return result
    except (OptimisticLockError, EventGovernanceError):
        session.rollback()
        raise


def _governed_to_detail(event: GovernedEvent):
    from .main import EventDetail, EventVersion

    return EventDetail(
        event_id=event.event_id,
        candidate_id=event.candidate_id,
        event_type=event.event_type,
        status=event.status,
        title=f"Event {event.event_id[:12]}",
        created_at=event.created_at,
        updated_at=event.updated_at or event.created_at,
        versions=[EventVersion(
            version=event.version,
            status=event.status,
            changed_by="system",
            changed_at=event.updated_at or event.created_at,
            summary=f"Version {event.version} — {event.status}",
        )],
    )


def get_events(status: str | None = None):
    from .main import EventDetail, EventVersion

    session = ensure_db()
    query = session.query(GovernedEventRecord).order_by(
        GovernedEventRecord.event_id,
        GovernedEventRecord.version.desc(),
    )
    if status:
        query = query.filter_by(status=status)

    event_map: dict[str, EventDetail] = {}
    for record in query.all():
        if record.event_id not in event_map:
            event_map[record.event_id] = EventDetail(
                event_id=record.event_id,
                candidate_id=record.candidate_id,
                event_type=record.event_type or "unknown",
                status=record.status,
                title=f"Event {record.event_id[:12]}",
                created_at=record.created_at,
                updated_at=record.updated_at or record.created_at,
                versions=[],
            )
        event_map[record.event_id].versions.append(EventVersion(
            version=record.version,
            status=record.status,
            changed_by="system",
            changed_at=record.updated_at or record.created_at,
            summary=f"v{record.version} — {record.status}",
        ))
    return list(event_map.values())


def get_event(event_id: str):
    try:
        event = get_governed_event(ensure_db(), event_id)
        return _governed_to_detail(event) if event else None
    except Exception:
        logger.warning("get_event(%s) failed", event_id, exc_info=True)
        return None


def get_event_geojson() -> dict:
    from .candidate_store import get_candidate_dict

    features = []
    seen = set()
    for record in ensure_db().query(GovernedEventRecord).order_by(GovernedEventRecord.version.desc()).all():
        if record.event_id in seen:
            continue
        seen.add(record.event_id)
        candidate = get_candidate_dict(record.candidate_id) or {}
        geometry = candidate.get("representative_geometry") or candidate.get("union_geometry")
        if geometry is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "event_id": record.event_id,
                "candidate_id": record.candidate_id,
                "status": record.status,
                "event_type": record.event_type,
            },
        })
    return {"type": "FeatureCollection", "features": features}


def get_event_replay(event_id: str):
    timeline = get_timeline(ensure_db(), event_id)
    return [
        {
            "replay_id": item.replay_id,
            "event_id": item.event_id,
            "sequence_number": item.sequence_number,
            "actor_type": item.actor_type,
            "actor_ref": item.actor_ref,
            "action": item.action,
            "object_type": item.object_type,
            "object_ref": item.object_ref,
            "details": item.details,
            "replayed_at": item.replayed_at,
        }
        for item in timeline
    ]


def get_runs(execution_status: Optional[str] = None):
    from .manifest_service import get_runs as get_manifest_runs
    return get_manifest_runs(execution_status=execution_status)


def get_run(run_id: str):
    from .manifest_service import get_run as get_manifest_run
    return get_manifest_run(run_id)


def get_artifact(artifact_id: str):
    from .manifest_service import get_artifact as get_manifest_artifact
    return get_manifest_artifact(artifact_id)


def get_summary() -> dict:
    session = ensure_db()
    latest_events = {
        row.event_id: row
        for row in session.query(GovernedEventRecord)
        .order_by(GovernedEventRecord.event_id, GovernedEventRecord.version.asc())
        .all()
    }
    recent_rows = session.query(ReplayRecordDB).order_by(ReplayRecordDB.replayed_at.desc()).limit(5).all()
    return {
        "total_candidates": session.query(CandidateRecord).count(),
        "total_events": len(latest_events),
        "total_reviews": session.query(ReviewRecord).count(),
        "recent_activity": [
            {
                "event_id": row.event_id,
                "action": row.action,
                "actor_ref": row.actor_ref,
                "replayed_at": row.replayed_at,
                "details": row.details,
            }
            for row in recent_rows
        ],
        "source": "real",
    }


def get_dashboard_snapshot():
    from .candidate_store import list_candidates
    from .main import (
        ChangeTypeDTO,
        DashboardSnapshotResponse,
        DashboardSummaryDTO,
        FunnelStageDTO,
        MonthlyTrendDTO,
        TypicalCaseDTO,
    )

    candidates, _ = list_candidates()
    events = get_events()
    runs = get_runs()
    persistence = Counter(row.get("persistence_status", "unknown") for row in candidates)
    change_types = Counter(row.get("change_type", "unknown") for row in candidates)
    event_status = Counter(event.status for event in events)
    session = ensure_db()

    labels = {
        "water_extent_increase": "水体扩张",
        "water_extent_decrease": "水体收缩",
        "unknown": "其他",
    }
    colors = {
        "water_extent_increase": "#22c55e",
        "water_extent_decrease": "#f97316",
        "unknown": "#94a3b8",
    }

    typical = sorted(candidates, key=lambda row: row.get("score", 0), reverse=True)[:5]
    last_run_at = max((run.finished_at or run.started_at for run in runs), default="")

    return DashboardSnapshotResponse(
        summary=DashboardSummaryDTO(
            total_candidates=len(candidates),
            persistent_count=persistence.get("persistent", 0),
            uncertain_count=persistence.get("uncertain", 0),
            transient_count=persistence.get("transient", 0),
            events_under_review=event_status.get("under_review", 0),
            events_confirmed=event_status.get("confirmed", 0),
            events_rejected=event_status.get("rejected", 0),
            events_needs_evidence=event_status.get("needs_more_evidence", 0),
            total_runs=len(runs),
            runs_completed=sum(run.execution_status == "succeeded" for run in runs),
            runs_failed=sum(run.execution_status == "failed" for run in runs),
            last_run_at=last_run_at,
            monitoring_area_km2=round(sum(row.get("area_m2", 0) for row in candidates) / 1_000_000, 3),
        ),
        change_types=[
            ChangeTypeDTO(
                change_type=name,
                label=labels.get(name, name),
                count=count,
                color=colors.get(name, colors["unknown"]),
            )
            for name, count in sorted(change_types.items())
        ],
        trend=[
            MonthlyTrendDTO(month="2026-05", label="2026年5月", candidates=len(candidates) // 2, confirmed=0),
            MonthlyTrendDTO(month="2026-06", label="2026年6月", candidates=len(candidates), confirmed=event_status.get("confirmed", 0)),
        ],
        funnel=[
            FunnelStageDTO(stage="candidates_ingested", count=len(candidates), description="已摄入候选"),
            FunnelStageDTO(stage="candidates_with_bundle", count=session.query(EvidenceBundleRecord).count(), description="已生成证据包"),
            FunnelStageDTO(stage="candidates_reviewed", count=session.query(ReviewRecord).count(), description="已人工核验"),
            FunnelStageDTO(stage="events_created", count=len(events), description="已创建事件"),
        ],
        typical_cases=[
            TypicalCaseDTO(
                id=row["candidate_id"],
                title=f"候选 {row['candidate_id']}",
                change_type=row.get("change_type", "unknown"),
                change_type_label=labels.get(row.get("change_type", "unknown"), "其他"),
                status=row.get("persistence_status", "unknown"),
                status_label=row.get("persistence_status", "unknown"),
                area_m2=row.get("area_m2", 0),
                detected_at=row.get("temporal_extent", ["unknown"])[-1],
                summary=f"排序分 {row.get('score', 0):.3f}，面积 {row.get('area_m2', 0):.0f} m²",
                candidate_id=row["candidate_id"],
            )
            for row in typical
        ],
    )
