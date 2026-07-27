"""RC-02.1: FastAPI TestClient E2E — Candidate→Review→Event→Replay"""
import pytest
from fastapi.testclient import TestClient
from apps.workbench_api.main import app

client = TestClient(app)


class TestRealApiE2E:
    def test_get_candidates(self):
        resp = client.get("/api/v2/candidates")
        assert resp.status_code == 200

    def test_get_events(self):
        resp = client.get("/api/v2/events")
        assert resp.status_code == 200

    def test_submit_review_validation(self):
        """Invalid action rejected"""
        resp = client.post("/api/v2/candidates/test/reviews",
            json={"action": "invalid", "comment": "test"})
        assert resp.status_code == 422

    def test_get_summary(self):
        resp = client.get("/api/v2/workbench/summary")
        assert resp.status_code == 200
