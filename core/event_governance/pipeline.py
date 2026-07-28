import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from core.schemas.contracts.perception import PerceptionResult
from core.event_governance.persistence import (
    GovernedEventRecord,
    CandidateRecord,
    EvidenceBundleRecord,
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
