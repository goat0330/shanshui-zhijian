from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from core.schemas.contracts.candidate import DetectionCandidate
from core.event_governance.persistence import (
    GovernedEventRecord,
    CandidateRecord,
    EvidenceBundleRecord,
    ReviewRecord,
    ReplayRecordDB,
)
from .bridge import CandidateIntakeBridge


class IntakeResult:
    def __init__(self, candidate_id: str, bundle_id: str,
                 n_evidence_items: int, is_idempotent: bool = False):
        self.candidate_id = candidate_id
        self.bundle_id = bundle_id
        self.n_evidence_items = n_evidence_items
        self.is_idempotent = is_idempotent


class EventGovernancePipeline:
    """Orchestrates the governance chain:
    DetectionCandidate → Intake (candidate+bundle) → Review → Event → Replay"""

    def __init__(self, session: Session):
        self._session = session
        self._bridge = CandidateIntakeBridge(session)

    def intake(self, candidate: DetectionCandidate) -> IntakeResult:
        candidate_id = candidate.candidate_id
        existing = (
            self._session.query(CandidateRecord)
            .filter_by(candidate_id=candidate_id)
            .first()
        )
        is_idempotent = existing is not None
        result = self._bridge.intake(candidate)
        return IntakeResult(
            candidate_id=result["candidate_id"],
            bundle_id=result["bundle_id"],
            n_evidence_items=result["n_evidence_items"],
            is_idempotent=is_idempotent,
        )

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_candidates": self._session.query(CandidateRecord).count(),
            "total_events": self._session.query(GovernedEventRecord).count(),
            "total_bundles": self._session.query(EvidenceBundleRecord).count(),
            "total_reviews": self._session.query(ReviewRecord).count(),
            "total_replay_entries": self._session.query(ReplayRecordDB).count(),
            "recent_events": [],
        }

    def get_snapshot(self) -> dict[str, Any]:
        candidates = self._session.query(CandidateRecord).count()
        events_distinct = self._session.query(GovernedEventRecord.event_id).distinct().count()
        events_total = self._session.query(GovernedEventRecord).count()
        bundles = self._session.query(EvidenceBundleRecord).count()
        reviews = self._session.query(ReviewRecord).count()
        replays = self._session.query(ReplayRecordDB).count()

        status_rows = (self._session.query(GovernedEventRecord.status, func.count(GovernedEventRecord.id.distinct()))
                       .group_by(GovernedEventRecord.status).all())
        events_by_status = dict(status_rows)

        recent_rows = (self._session.query(GovernedEventRecord)
                       .order_by(GovernedEventRecord.created_at.desc()).limit(10).all())
        seen = set()
        recent_events = []
        for r in recent_rows:
            if r.event_id not in seen:
                seen.add(r.event_id)
                recent_events.append(dict(
                    event_id=r.event_id, version=r.version,
                    candidate_id=r.candidate_id, event_type=r.event_type,
                    status=r.status, created_at=r.created_at,
                ))

        recent_reviews = (self._session.query(ReviewRecord)
                          .order_by(ReviewRecord.reviewed_at.desc()).limit(10).all())

        return {
            "totals": {
                "candidates": candidates,
                "events_distinct": events_distinct,
                "events_total_versions": events_total,
                "evidence_bundles": bundles,
                "reviews": reviews,
                "replay_entries": replays,
            },
            "events_by_status": events_by_status,
            "funnel": {
                "candidates_ingested": candidates,
                "candidates_with_bundle": bundles,
                "candidates_reviewed": reviews,
                "events_created": events_distinct,
            },
            "recent_events": recent_events,
            "recent_reviews": [dict(
                review_id=r.review_id, bundle_id=r.bundle_id,
                reviewer=r.reviewer, decision=r.decision,
                reason=r.reason, category=r.category,
                comment=r.comment, reviewed_at=r.reviewed_at,
            ) for r in recent_reviews],
            "source": "event_governance",
        }
