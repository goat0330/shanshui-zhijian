import hashlib
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
