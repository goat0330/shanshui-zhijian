"""Candidate store backed by C's event_governance SQLite."""
import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from core.event_governance.persistence import create_session, CandidateRecord

logger = logging.getLogger(__name__)

_seeded = False
_db_path = ":memory:"


def _get_session():
    return create_session(_db_path)


def _seed():
    global _seeded
    if _seeded:
        return
    session = _get_session()
    count = session.query(CandidateRecord).count()
    if count > 0:
        _seeded = True
        return
    for i in range(36):
        cid = f"CAND-{str(i+1).zfill(4)}"
        rec = CandidateRecord(
            candidate_id=cid,
            source="mock-seed",
            payload=json.dumps({
                "candidate_id": cid,
                "change_type": "water_extent_increase",
                "persistence_status": "persistent" if i < 12 else "uncertain" if i < 20 else "transient",
                "occurrence_count": 3 + (i % 6),
                "persistence_ratio": 0.5 + (i % 5) * 0.1,
                "within_run_ranking": i + 1,
                "batch_rank": i + 1,
                "area_m2": 12000 + i * 5000,
                "temporal_extent": ["2026-03-01T00:00:00Z", "2026-06-30T00:00:00Z"],
            }),
        )
        session.add(rec)
    session.commit()
    logger.info("Seeded 36 candidates")


def _row_to_dict(rec):
    try:
        return json.loads(rec.payload)
    except Exception:
        return {"candidate_id": rec.candidate_id}


def list_candidates():
    """Return (list[dict], total_count)."""
    _seed()
    session = _get_session()
    rows = session.query(CandidateRecord).all()
    items = [_row_to_dict(r) for r in rows]
    return items, len(items)


def get_candidate_dict(candidate_id: str) -> dict | None:
    _seed()
    session = _get_session()
    rec = session.query(CandidateRecord).filter_by(candidate_id=candidate_id).first()
    if rec:
        return _row_to_dict(rec)
    return None
