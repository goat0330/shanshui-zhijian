import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from core.schemas.contracts.perception import PerceptionResult
from core.event_governance.persistence import (
    GovernedEventRecord,
    CandidateRecord,
    EvidenceBundleRecord,
    ReviewRecord,
    ReplayRecordDB,
)
from .bridge import PerceptionToAlertBridge
from .models import GovernedEvent


class IngestionResult:
    def __init__(
        self,
        event: GovernedEvent,
        candidate_id: str,
        bundle_id: str,
        n_observations: int,
        is_idempotent: bool = False,
    ):
        self.event = event
        self.candidate_id = candidate_id
        self.bundle_id = bundle_id
        self.n_observations = n_observations
        self.is_idempotent = is_idempotent


class EventGovernancePipeline:
    def __init__(self, session: Session):
        self._session = session
        self._bridge = PerceptionToAlertBridge(session)

    def process(self, perception_result: PerceptionResult) -> IngestionResult:
        from .bridge import _compute_candidate_id
        candidate_id = _compute_candidate_id(perception_result.perception_result_id)
        bundle_id = f"bundle_{candidate_id}"

        existing_candidate = (
            self._session.query(CandidateRecord)
            .filter_by(candidate_id=candidate_id)
            .first()
        )
        is_idempotent = existing_candidate is not None

        event = self._bridge.ingest(perception_result)

        n_observations = len(perception_result.observations)

        return IngestionResult(
            event=event,
            candidate_id=candidate_id,
            bundle_id=bundle_id,
            n_observations=n_observations,
            is_idempotent=is_idempotent,
        )

    def get_stats(self) -> dict[str, Any]:
        candidates = self._session.query(CandidateRecord).count()
        events = self._session.query(GovernedEventRecord).count()
        bundles = self._session.query(EvidenceBundleRecord).count()
        replays = self._session.query(ReplayRecordDB).count()

        recent_events = (
            self._session.query(GovernedEventRecord)
            .order_by(GovernedEventRecord.created_at.desc())
            .limit(10)
            .all()
        )

        return {
            "total_candidates": candidates,
            "total_events": events,
            "total_bundles": bundles,
            "total_replay_entries": replays,
            "recent_events": [
                {
                    "event_id": r.event_id,
                    "version": r.version,
                    "candidate_id": r.candidate_id,
                    "event_type": r.event_type,
                    "status": r.status,
                    "created_at": r.created_at,
                }
                for r in recent_events
            ],
        }

    def get_snapshot(self) -> dict:
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
            "recent_events": recent_events,
            "recent_reviews": [dict(
                review_id=r.review_id, bundle_id=r.bundle_id,
                reviewer=r.reviewer, decision=r.decision,
                reason=r.reason, category=r.category,
                comment=r.comment, reviewed_at=r.reviewed_at,
            ) for r in recent_reviews],
            "source": "event_governance",
        }
