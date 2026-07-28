"""
Real HTTP E2E — full Evidence → Review → Event → Replay chain via TestClient.

This test exercises the apps/workbench_api/main.py endpoints with real HTTP
calls (no in-process mock). All services use the same SQLite database.
"""

import json
import os
import sys
import tempfile
import pytest

from fastapi.testclient import TestClient


def _setup_app():
    """Single setup: creates DB, injects session, returns (client, cleanup)."""
    from core.event_governance.persistence import Base as GovBase
    from sqlalchemy import create_engine, orm
    from pathlib import Path

    svc = str(Path(__file__).resolve().parent.parent / "services")
    if svc not in sys.path:
        sys.path.insert(0, svc)

    db_path = os.path.join(tempfile.gettempdir(), f"test_e2e_{os.urandom(4).hex()}.db")
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    GovBase.metadata.create_all(engine)
    session = orm.sessionmaker(bind=engine)()

    # Inject session into real_service BEFORE any imports
    import apps.workbench_api.real_service as rs
    rs._session = session

    from apps.workbench_api.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    def cleanup():
        try:
            session.close()
            engine.dispose()
        except Exception:
            pass
        try:
            for _ in range(5):
                try:
                    os.remove(db_path)
                    break
                except PermissionError:
                    import time
                    time.sleep(0.1)
        except Exception:
            pass

    return client, cleanup


@pytest.fixture
def client():
    cl, cleanup_fn = _setup_app()
    yield cl
    cleanup_fn()


@pytest.fixture
def sample_candidate():
    return {
        "candidate_id": "e2e_cand_001",
        "observation_refs": ["obs_1", "obs_2"],
        "temporal_extent": {"start": "2026-06-01", "end": "2026-06-15"},
        "candidate_type": "water_extent_change",
        "score": 0.87,
        "evidence_refs": ["sar_vh", "optical_ndwi"],
        "rule_version": "1.0.0",
    }


class TestRealHTTPE2E:
    """Full Evidence → Review → Event → Replay chain via HTTP."""

    def test_intake_creates_candidate_only(self, client, sample_candidate):
        """POST /api/v2/candidates/intake creates candidate+bundle, no event."""
        resp = client.post("/api/v2/candidates/intake", json=sample_candidate)
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidate_id"] == "e2e_cand_001"
        assert data["bundle_id"].startswith("bundle_")
        assert data["n_evidence_items"] == 2
        assert data["is_idempotent"] is False

        resp2 = client.post("/api/v2/candidates/intake", json=sample_candidate)
        assert resp2.json()["is_idempotent"] is True

    def test_intake_no_event(self, client, sample_candidate):
        """No events exist before review."""
        client.post("/api/v2/candidates/intake", json=sample_candidate)
        resp = client.get("/api/v2/events")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 0

    def test_full_review_confirm_chain(self, client, sample_candidate):
        """Intake → Review(confirm) → Event → Versions → Replay."""
        # 1. Intake
        client.post("/api/v2/candidates/intake", json=sample_candidate)

        # 2. Review with confirm
        review_resp = client.post(
            "/api/v2/candidates/e2e_cand_001/reviews",
            json={"action": "confirm", "comment": "confirmed via E2E"},
        )
        assert review_resp.status_code == 200
        review_data = review_resp.json()
        assert review_data["action"] == "confirm"

        # 3. Verify event was created
        events_resp = client.get("/api/v2/events")
        assert events_resp.status_code == 200
        events = events_resp.json()["data"]
        assert len(events) >= 1
        event = events[0]
        assert event["status"] == "confirmed"
        event_id = event["event_id"]

        # 4. Get event detail
        detail_resp = client.get(f"/api/v2/events/{event_id}")
        assert detail_resp.status_code == 200

        # 5. Verify event versions
        versions_resp = client.get(f"/api/v2/events/{event_id}/versions")
        assert versions_resp.status_code == 200

        # 6. Replay timeline
        replay_resp = client.get(f"/api/v2/events/{event_id}/replay")
        assert replay_resp.status_code == 200
        assert len(replay_resp.json()) >= 1

        # 7. Dashboard snapshot
        snap_resp = client.get("/api/v2/dashboard/snapshot")
        assert snap_resp.status_code == 200
        snap = snap_resp.json()
        assert snap["summary"]["total_candidates"] >= 1
        assert snap["summary"]["events_confirmed"] >= 1

    def test_review_reject_no_event(self, client):
        """Reject creates review but no event."""
        cand = {
            "candidate_id": "e2e_cand_reject",
            "observation_refs": ["o1"],
            "temporal_extent": {"start": "2026-06-01", "end": "2026-06-15"},
            "candidate_type": "water_extent_change",
            "score": 0.5,
            "evidence_refs": ["sar_vh"],
            "rule_version": "1.0.0",
        }
        client.post("/api/v2/candidates/intake", json=cand)

        resp = client.post(
            "/api/v2/candidates/e2e_cand_reject/reviews",
            json={"action": "reject", "comment": "false positive"},
        )
        assert resp.status_code == 200

        events = client.get("/api/v2/events").json()["data"]
        for e in events:
            assert e["candidate_id"] != "e2e_cand_reject", "Reject must not create event"

    def test_replay_timeline_after_review(self, client, sample_candidate):
        """Review creates replay timeline entries."""
        client.post("/api/v2/candidates/intake", json=sample_candidate)
        client.post(
            "/api/v2/candidates/e2e_cand_001/reviews",
            json={"action": "confirm", "comment": "confirmed"},
        )
        events = client.get("/api/v2/events").json()["data"]
        event_id = events[0]["event_id"]

        replay = client.get(f"/api/v2/events/{event_id}/replay").json()
        assert len(replay) >= 1
        assert replay[0]["action"] == "review_confirm"

    def test_dashboard_snapshot_aggregates(self, client, sample_candidate):
        """Dashboard snapshot reflects real data."""
        client.post("/api/v2/candidates/intake", json=sample_candidate)
        client.post(
            "/api/v2/candidates/e2e_cand_001/reviews",
            json={"action": "confirm", "comment": "confirmed"},
        )
        snap = client.get("/api/v2/dashboard/snapshot").json()
        assert snap["summary"]["total_candidates"] >= 1
        assert snap["summary"]["events_confirmed"] >= 1
        assert len(snap["funnel"]) == 4
