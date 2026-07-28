"""
Correct governance chain:
DetectionCandidate → Candidate Intake → Evidence Bundle → Review → Event Version → Replay
Events are only created through Review, never from raw perception results.
"""

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from core.schemas.contracts.candidate import DetectionCandidate
from .models import (
    GovernanceCandidate,
    EvidenceItem,
    EvidenceBundle,
    ReviewDecision,
    GovernedEvent,
    EventGovernanceError,
    OptimisticLockError,
)
from .service import (
    intake_candidate,
    attach_evidence,
    review_bundle,
)
from .persistence import (
    GovernedEventRecord,
    EvidenceBundleRecord,
    ReviewRecord,
    ReplayRecordDB,
)


class CandidateIntakeBridge:
    """Intake a DetectionCandidate → GovernanceCandidate + EvidenceBundle.
    No Event is created — events only appear through Review."""

    def __init__(self, session: Session):
        self._session = session

    def intake(self, candidate: DetectionCandidate) -> dict:
        candidate_id = candidate.candidate_id

        existing = (
            self._session.query(EvidenceBundleRecord)
            .filter_by(candidate_id=candidate_id)
            .first()
        )
        if existing:
            return self._existing_result(candidate_id, existing)

        gov_candidate = GovernanceCandidate(
            candidate_id=candidate_id,
            source=candidate.candidate_type,
            payload={
                "candidate_type": candidate.candidate_type,
                "score": candidate.score,
                "observation_refs": candidate.observation_refs,
                "temporal_extent": candidate.temporal_extent,
                "geometry": candidate.geometry,
            },
        )
        intake_candidate(self._session, gov_candidate)

        evidence_items = []
        for i, ref in enumerate(candidate.evidence_refs):
            if isinstance(ref, str):
                evidence_items.append(EvidenceItem(
                    evidence_id=f"ev_{candidate_id}_{i}",
                    evidence_type=ref,
                    file_ref=ref,
                ))
            else:
                evidence_items.append(EvidenceItem(
                    evidence_id=f"ev_{candidate_id}_{i}",
                    evidence_type=getattr(ref, "evidence_type", str(ref)),
                    file_ref=getattr(ref, "source_asset_ref", str(ref)),
                    description=getattr(ref, "description", ""),
                ))

        bundle = EvidenceBundle(
            bundle_id=f"bundle_{candidate_id}",
            candidate_id=candidate_id,
            version=1,
            items=evidence_items,
            status="submitted",
        )
        attach_evidence(self._session, bundle)

        return {
            "candidate_id": candidate_id,
            "bundle_id": bundle.bundle_id,
            "n_evidence_items": len(evidence_items),
            "status": "intake_complete",
        }

    def _existing_result(self, candidate_id: str, bundle: EvidenceBundleRecord) -> dict:
        raw = bundle.items
        if isinstance(raw, str):
            try:
                items = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                items = []
        else:
            items = raw or []
        return {
            "candidate_id": candidate_id,
            "bundle_id": bundle.bundle_id,
            "n_evidence_items": len(items),
            "status": "already_ingested",
        }


class EvidenceBridge:
    def __init__(self, session: Session):
        self._session = session

    def list_bundles(self, candidate_id: str | None = None, limit: int = 20) -> list[dict]:
        q = self._session.query(EvidenceBundleRecord)
        if candidate_id:
            q = q.filter_by(candidate_id=candidate_id)
        rows = q.order_by(EvidenceBundleRecord.created_at.desc()).limit(limit).all()
        return [self._bundle_dict(r) for r in rows]

    def get_bundle(self, bundle_id: str) -> dict | None:
        r = self._session.query(EvidenceBundleRecord).filter_by(bundle_id=bundle_id).first()
        if not r:
            return None
        return self._bundle_dict(r)

    def _bundle_dict(self, r: EvidenceBundleRecord) -> dict:
        raw = r.items
        if isinstance(raw, str):
            try:
                items = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                items = []
        else:
            items = raw or []
        return {
            "bundle_id": r.bundle_id, "candidate_id": r.candidate_id,
            "version": r.version, "items": items, "item_count": len(items),
            "status": r.status, "created_at": r.created_at,
        }


class ReviewBridge:
    def __init__(self, session: Session):
        self._session = session

    def list_reviews(self, bundle_id: str | None = None, limit: int = 20) -> list[dict]:
        q = self._session.query(ReviewRecord)
        if bundle_id:
            q = q.filter_by(bundle_id=bundle_id)
        rows = q.order_by(ReviewRecord.reviewed_at.desc()).limit(limit).all()
        return [self._review_dict(r) for r in rows]

    def submit(self, bundle_id: str, reviewer: str, decision: str, *,
               reason: str = "", expected_version: int = 1,
               category: str | None = None, comment: str = "",
               candidate_id: str | None = None) -> ReviewDecision:
        import uuid
        ts = datetime.now().strftime('%Y%m%d%H%M%S')
        unique = uuid.uuid4().hex[:8]
        review = ReviewDecision(
            review_id=f"REV-{ts}-{unique}",
            bundle_id=bundle_id, reviewer=reviewer, decision=decision,
            reason=reason, expected_version=expected_version,
            category=category, comment=comment, candidate_id=candidate_id,
        )
        return review_bundle(self._session, review)

    def _review_dict(self, r: ReviewRecord) -> dict:
        return {
            "review_id": r.review_id, "bundle_id": r.bundle_id,
            "reviewer": r.reviewer, "decision": r.decision,
            "reason": r.reason, "version_at_review": r.version_at_review,
            "category": r.category, "comment": r.comment,
            "candidate_id": r.candidate_id, "reviewed_at": r.reviewed_at,
        }


class EventBridge:
    def __init__(self, session: Session):
        self._session = session

    def list_events(self, status: str | None = None, limit: int = 20) -> list[dict]:
        q = self._session.query(GovernedEventRecord).order_by(GovernedEventRecord.created_at.desc())
        if status:
            q = q.filter_by(status=status)
        rows = q.limit(limit).all()
        seen: set[str] = set()
        result = []
        for r in rows:
            if r.event_id not in seen:
                seen.add(r.event_id)
                result.append(self._event_dict(r))
        return result

    def get_event(self, event_id: str) -> dict | None:
        r = (self._session.query(GovernedEventRecord).filter_by(event_id=event_id)
             .order_by(GovernedEventRecord.version.desc()).first())
        if not r:
            return None
        return self._event_dict(r)

    def get_event_versions(self, event_id: str) -> list[dict]:
        rows = (self._session.query(GovernedEventRecord).filter_by(event_id=event_id)
                .order_by(GovernedEventRecord.version).all())
        return [self._event_dict(r) for r in rows]

    def get_events_by_status(self) -> dict[str, int]:
        from sqlalchemy import func
        q = (self._session.query(GovernedEventRecord.status, func.count(GovernedEventRecord.id.distinct()))
             .group_by(GovernedEventRecord.status).all())
        return {s: c for s, c in q}

    def _event_dict(self, r: GovernedEventRecord) -> dict:
        return {
            "event_id": r.event_id, "version": r.version,
            "candidate_id": r.candidate_id, "event_type": r.event_type,
            "status": r.status, "created_at": r.created_at, "updated_at": r.updated_at,
        }


class ReplayBridge:
    def __init__(self, session: Session):
        self._session = session

    def get_timeline(self, event_id: str, limit: int = 50) -> list[dict]:
        rows = (self._session.query(ReplayRecordDB).filter_by(event_id=event_id)
                .order_by(ReplayRecordDB.sequence_number.desc()).limit(limit).all())
        return [self._replay_dict(r) for r in reversed(rows)]

    def get_recent_entries(self, limit: int = 20) -> list[dict]:
        rows = (self._session.query(ReplayRecordDB)
                .order_by(ReplayRecordDB.replayed_at.desc()).limit(limit).all())
        return [self._replay_dict(r) for r in rows]

    def _replay_dict(self, r: ReplayRecordDB) -> dict:
        return {
            "replay_id": r.replay_id, "event_id": r.event_id,
            "sequence_number": r.sequence_number, "actor_type": r.actor_type,
            "actor_ref": r.actor_ref, "action": r.action,
            "object_type": r.object_type, "object_ref": r.object_ref,
            "details": r.details, "replayed_at": r.replayed_at,
        }
