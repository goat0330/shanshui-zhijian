"""Candidate store backed by the shared event-governance SQLite database.

There is no implicit mock fallback. Demo data is written only when the explicit
``seed_demo_candidates`` utility is called (for local demo or CI E2E setup).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from core.event_governance.persistence import (
    CandidateRecord,
    EvidenceBundleRecord,
    create_session,
)

from .db import get_workbench_db_path


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_session():
    return create_session(get_workbench_db_path())


def _geometry(index: int) -> dict:
    col = index % 6
    row = index // 6
    x = 106.50 + col * 0.012
    y = 29.53 + row * 0.010
    dx = 0.003
    dy = 0.002
    return {
        "type": "Polygon",
        "coordinates": [[
            [x, y], [x + dx, y], [x + dx, y + dy], [x, y + dy], [x, y]
        ]],
    }


def _candidate_payload(index: int) -> dict:
    candidate_id = f"CAND-{index + 1:04d}"
    persistence = "persistent" if index < 12 else "uncertain" if index < 20 else "transient"
    change_type = "water_extent_increase" if index % 2 == 0 else "water_extent_decrease"
    geom = _geometry(index)
    score = round(max(0.25, 0.96 - index * 0.015), 4)
    return {
        "candidate_id": candidate_id,
        "candidate_track_id": f"TRACK-{index + 1:04d}",
        "schema_version": "0.3.0",
        "change_type": change_type,
        "persistence_status": persistence,
        "temporal_extent": ["2026-05-01T00:00:00Z", "2026-06-30T23:59:59Z"],
        "occurrence_count": 3 + (index % 6),
        "persistence_ratio": round(0.50 + (index % 5) * 0.10, 2),
        "representative_geometry": geom,
        "union_geometry": geom,
        "score": score,
        "score_type": "within_run_ranking_score",
        "score_components": {
            "spectral_change": round(score * 0.55, 4),
            "temporal_persistence": round(score * 0.30, 4),
            "quality": round(score * 0.15, 4),
        },
        "quality_summary": {
            "overall": "good",
            "cloud_cover": 8.0 + index % 12,
            "geometric_quality": "aligned",
            "artifact_count": 0,
        },
        "observation_refs": [f"OBS-{index + 1:04d}-T1", f"OBS-{index + 1:04d}-T2"],
        "source_asset_refs": ["S2-T1-E2E", "S2-T2-E2E"],
        "rule_version": "ml-b2-v1",
        "run_manifest_ref": "run-e2e-001",
        "within_run_ranking": index + 1,
        "batch_rank": index + 1,
        "area_m2": float(12000 + index * 5000),
        "review_state": None,
    }


def seed_demo_candidates(count: int = 36, replace: bool = False) -> int:
    """Write deterministic E2E/demo candidates and evidence into real SQLite."""
    session = _get_session()
    try:
        if replace:
            session.query(EvidenceBundleRecord).delete()
            session.query(CandidateRecord).delete()
            session.commit()

        inserted = 0
        for index in range(count):
            payload = _candidate_payload(index)
            candidate_id = payload["candidate_id"]
            existing = session.query(CandidateRecord).filter_by(candidate_id=candidate_id).first()
            if existing is None:
                session.add(CandidateRecord(
                    candidate_id=candidate_id,
                    source="e2e-seed",
                    payload=json.dumps(payload, ensure_ascii=False),
                    ingested_at=_now(),
                ))
                inserted += 1

            bundle_id = f"BUNDLE-{candidate_id}"
            bundle = session.query(EvidenceBundleRecord).filter_by(bundle_id=bundle_id).first()
            if bundle is None:
                evidence = [{
                    "evidence_id": f"EVD-{candidate_id}-S2",
                    "evidence_type": "optical_image",
                    "source_modality": "光学",
                    "source_asset_ref": "S2-T2-E2E",
                    "derived_asset_ref": f"ART-{candidate_id}-MNDWI",
                    "captured_at": "2026-06-15T02:30:00Z",
                    "stance": "supporting",
                    "quality_summary": {
                        "overall": "good",
                        "cloud_cover": 8.0,
                        "geometric_quality": "aligned",
                        "artifact_count": 0,
                    },
                    "provenance": "cycle311-e2e-seed",
                    "unavailable_reason": None,
                }]
                session.add(EvidenceBundleRecord(
                    bundle_id=bundle_id,
                    candidate_id=candidate_id,
                    version=1,
                    items=json.dumps(evidence, ensure_ascii=False),
                    status="submitted",
                    created_at=_now(),
                ))
        session.commit()
        return inserted
    finally:
        session.close()


def _row_to_dict(record: CandidateRecord) -> dict:
    try:
        data = json.loads(record.payload)
    except (TypeError, json.JSONDecodeError):
        data = {"candidate_id": record.candidate_id}
    data.setdefault("candidate_id", record.candidate_id)
    return data


def list_candidates() -> tuple[list[dict], int]:
    session = _get_session()
    try:
        rows = session.query(CandidateRecord).order_by(CandidateRecord.candidate_id).all()
        items = [_row_to_dict(row) for row in rows]
        return items, len(items)
    finally:
        session.close()


def get_candidate_dict(candidate_id: str) -> dict | None:
    session = _get_session()
    try:
        record = session.query(CandidateRecord).filter_by(candidate_id=candidate_id).first()
        return _row_to_dict(record) if record else None
    finally:
        session.close()
