import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from core.schemas.contracts.perception import PerceptionResult
from .models import (
    GovernanceCandidate,
    EvidenceItem,
    EvidenceBundle,
    GovernedEvent,
)
from .service import (
    intake_candidate,
    attach_evidence,
    record_event,
    replay_event,
)
from .persistence import GovernedEventRecord


def _compute_event_id(perception_id: str) -> str:
    raw = f"evt_perception_{perception_id}"
    return "evt_" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def _compute_candidate_id(perception_id: str) -> str:
    return f"cand_{perception_id}"


def _map_observations_to_evidence(
    perception_result: PerceptionResult,
) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for obs in perception_result.observations:
        ev = EvidenceItem(
            evidence_id=f"ev_{obs.observation_id}",
            evidence_type=obs.observation_type.value
            if hasattr(obs.observation_type, "value")
            else str(obs.observation_type),
            file_ref=obs.perception_result_ref,
            description=obs.label,
            acquired_at=obs.created_at,
        )
        items.append(ev)
    return items


def _derive_event_type(perception_result: PerceptionResult) -> str:
    types = set()
    for obs in perception_result.observations:
        t = (
            obs.observation_type.value
            if hasattr(obs.observation_type, "value")
            else str(obs.observation_type)
        )
        types.add(t)
    if "water_extent" in types or "optical_water_index" in types:
        return "water_anomaly"
    if "sar_backscatter_change" in types:
        return "backscatter_change"
    if "object_detection" in types:
        return "object_detected"
    return "perception_alert"


class PerceptionToAlertBridge:
    def __init__(self, session: Session):
        self._session = session

    def ingest(self, perception_result: PerceptionResult) -> GovernedEvent:
        candidate_id = _compute_candidate_id(perception_result.perception_result_id)
        event_id = _compute_event_id(perception_result.perception_result_id)

        existing = (
            self._session.query(GovernedEventRecord)
            .filter_by(event_id=event_id)
            .first()
        )
        if existing:
            payload = {}
            if existing.payload:
                import json
                try:
                    payload = json.loads(existing.payload)
                except (json.JSONDecodeError, TypeError):
                    payload = {}
            return GovernedEvent(
                event_id=existing.event_id,
                version=existing.version,
                candidate_id=existing.candidate_id,
                event_type=existing.event_type,
                payload=payload,
                status=existing.status,
                created_at=existing.created_at,
                updated_at=existing.updated_at,
            )

        now = datetime.now().isoformat()
        source = (
            perception_result.inference_task_ref
            if perception_result.inference_task_ref
            else "perception"
        )

        candidate = GovernanceCandidate(
            candidate_id=candidate_id,
            source=source,
            payload={
                "perception_result_id": perception_result.perception_result_id,
                "run_id": perception_result.run_id,
                "task_spec_ref": perception_result.task_spec_ref,
                "status": (
                    perception_result.status.value
                    if hasattr(perception_result.status, "value")
                    else str(perception_result.status)
                ),
                "observations": [
                    o.observation_id for o in perception_result.observations
                ],
            },
            ingested_at=now,
        )
        intake_candidate(self._session, candidate)

        evidence_items = _map_observations_to_evidence(perception_result)
        bundle = EvidenceBundle(
            bundle_id=f"bundle_{candidate_id}",
            candidate_id=candidate_id,
            version=1,
            items=evidence_items,
            status="submitted",
            created_at=now,
        )
        attach_evidence(self._session, bundle)

        event_type = _derive_event_type(perception_result)
        event = GovernedEvent(
            event_id=event_id,
            version=1,
            candidate_id=candidate_id,
            event_type=event_type,
            payload={
                "perception_result_id": perception_result.perception_result_id,
                "run_id": perception_result.run_id,
                "inference_task_ref": perception_result.inference_task_ref,
                "n_observations": len(perception_result.observations),
                "artifact_refs": perception_result.artifact_refs,
                "started_at": perception_result.started_at or "",
                "finished_at": perception_result.finished_at or "",
            },
            status="under_review",
            created_at=now,
        )
        record_event(self._session, event)

        replay_event(
            self._session,
            event_id,
            actor="perception_bridge",
        )

        return event


class EvidenceBridge:
    def __init__(self, session):
        self._session = session

    def list_bundles(self, candidate_id=None, limit=20):
        from .persistence import EvidenceBundleRecord
        q = self._session.query(EvidenceBundleRecord)
        if candidate_id:
            q = q.filter_by(candidate_id=candidate_id)
        rows = q.order_by(EvidenceBundleRecord.created_at.desc()).limit(limit).all()
        result = []
        for r in rows:
            raw = r.items
            if isinstance(raw, str):
                try: items = json.loads(raw)
                except: items = []
            else: items = raw or []
            result.append(dict(bundle_id=r.bundle_id, candidate_id=r.candidate_id,
                version=r.version, items=items, item_count=len(items),
                status=r.status, created_at=r.created_at))
        return result

    def get_bundle(self, bundle_id):
        from .persistence import EvidenceBundleRecord
        r = self._session.query(EvidenceBundleRecord).filter_by(bundle_id=bundle_id).first()
        if not r: return None
        raw = r.items
        if isinstance(raw, str):
            try: items = json.loads(raw)
            except: items = []
        else: items = raw or []
        return dict(bundle_id=r.bundle_id, candidate_id=r.candidate_id,
            version=r.version, items=items, item_count=len(items),
            status=r.status, created_at=r.created_at)


class ReviewBridge:
    def __init__(self, session):
        self._session = session

    def list_reviews(self, bundle_id=None, limit=20):
        from .persistence import ReviewRecord
        q = self._session.query(ReviewRecord)
        if bundle_id:
            q = q.filter_by(bundle_id=bundle_id)
        rows = q.order_by(ReviewRecord.reviewed_at.desc()).limit(limit).all()
        return [dict(review_id=r.review_id, bundle_id=r.bundle_id,
            reviewer=r.reviewer, decision=r.decision, reason=r.reason,
            version_at_review=r.version_at_review, category=r.category,
            comment=r.comment, candidate_id=r.candidate_id,
            reviewed_at=r.reviewed_at) for r in rows]

    def submit(self, bundle_id, reviewer, decision, reason="", expected_version=1,
            category=None, comment="", candidate_id=None):
        from .models import ReviewDecision
        from .service import review_bundle
        review = ReviewDecision(
            review_id="REV-" + datetime.now().strftime("%Y%m%d%H%M%S") + "-" + hashlib.md5(bundle_id.encode()).hexdigest()[:6],
            bundle_id=bundle_id, reviewer=reviewer, decision=decision,
            reason=reason, expected_version=expected_version,
            category=category, comment=comment, candidate_id=candidate_id)
        return review_bundle(self._session, review)


class EventBridge:
    def __init__(self, session):
        self._session = session

    def list_events(self, status=None, limit=20):
        from .persistence import GovernedEventRecord
        q = self._session.query(GovernedEventRecord).order_by(GovernedEventRecord.created_at.desc())
        if status:
            q = q.filter_by(status=status)
        rows = q.limit(limit).all()
        seen = set()
        result = []
        for r in rows:
            if r.event_id not in seen:
                seen.add(r.event_id)
                result.append(self._ed(r))
        return result

    def get_event(self, event_id):
        from .persistence import GovernedEventRecord
        r = self._session.query(GovernedEventRecord).filter_by(event_id=event_id).order_by(GovernedEventRecord.version.desc()).first()
        if not r: return None
        return self._ed(r)

    def get_event_versions(self, event_id):
        from .persistence import GovernedEventRecord
        rows = self._session.query(GovernedEventRecord).filter_by(event_id=event_id).order_by(GovernedEventRecord.version).all()
        return [self._ed(r) for r in rows]

    def get_events_by_status(self):
        from sqlalchemy import func
        from .persistence import GovernedEventRecord
        q = self._session.query(GovernedEventRecord.status, func.count(GovernedEventRecord.id.distinct())).group_by(GovernedEventRecord.status).all()
        return dict(q)

    def _ed(self, r):
        return dict(event_id=r.event_id, version=r.version, candidate_id=r.candidate_id,
            event_type=r.event_type, status=r.status, created_at=r.created_at, updated_at=r.updated_at)


class ReplayBridge:
    def __init__(self, session):
        self._session = session

    def get_timeline(self, event_id, limit=50):
        from .persistence import ReplayRecordDB
        rows = self._session.query(ReplayRecordDB).filter_by(event_id=event_id).order_by(ReplayRecordDB.sequence_number.desc()).limit(limit).all()
        return [self._rd(r) for r in reversed(rows)]

    def get_recent_entries(self, limit=20):
        from .persistence import ReplayRecordDB
        rows = self._session.query(ReplayRecordDB).order_by(ReplayRecordDB.replayed_at.desc()).limit(limit).all()
        return [self._rd(r) for r in rows]

    def _rd(self, r):
        return dict(replay_id=r.replay_id, event_id=r.event_id,
            sequence_number=r.sequence_number, actor_type=r.actor_type,
            actor_ref=r.actor_ref, action=r.action, object_type=r.object_type,
            object_ref=r.object_ref, details=r.details, replayed_at=r.replayed_at)
