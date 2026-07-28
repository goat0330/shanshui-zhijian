"""
RC-03: 事件治理桥接 + ML 下游适配 — 综合测试

测试覆盖:
  1. PerceptionToAlertBridge 基础摄入
  2. Bridge 幂等 (同一 PerceptionResult 再次摄入返回相同 Event)
  3. Bridge 观察值映射为证据条目
  4. Bridge 事件类型推导 (water_anomaly)
  5. Bridge 事件类型推导 (backscatter_change)
  6. Bridge 事件类型推导 (object_detected)
  7. Pipeline process 返回 IngestionResult
  8. Pipeline 幂等检测 (is_idempotent=True)
  9. Pipeline get_stats 返回聚合统计
  10. Pipeline get_stats 含最近事件列表
  11. POST /api/v2/ingest/perception 端点接收 PerceptionResult
  12. API 端点返回正确 event_id 和版本
  13. API 端点重复请求幂等
  14. API 端点无效输入返回 422
  15. GET /api/v2/governance/stats 返回统计数据
"""

import json
import pytest
from datetime import datetime

from core.event_governance.bridge import PerceptionToAlertBridge, _compute_event_id, _compute_candidate_id
from core.event_governance.pipeline import EventGovernancePipeline
from core.event_governance.persistence import create_session
from core.event_governance.models import GovernedEvent, EvidenceBundle, EvidenceItem
from core.schemas.contracts.perception import PerceptionResult, Observation
from core.schemas.contracts import (
    ExecutionStatus,
    TaskType,
    ObservationType,
    ScoreType,
)


def _make_observation(
    obs_id: str,
    obs_type: ObservationType = ObservationType.WATER_EXTENT,
    label: str = "water detected",
    score: float = 0.92,
) -> Observation:
    return Observation(
        observation_id=obs_id,
        perception_result_ref="pr_test",
        source_task_type=TaskType.WATER_EXTRACTION,
        observation_type=obs_type,
        label=label,
        score=score,
        score_type=ScoreType.MODEL_PROBABILITY,
        created_at=datetime.now().isoformat(),
    )


def _make_perception_result(
    pr_id: str = "pr_test_001",
    run_id: str = "run_test_001",
    n_obs: int = 2,
    obs_type: ObservationType = ObservationType.WATER_EXTENT,
) -> PerceptionResult:
    return PerceptionResult(
        perception_result_id=pr_id,
        inference_task_ref="task_water_001",
        task_spec_ref="spec_v1",
        run_id=run_id,
        status=ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
        observations=[
            _make_observation(f"obs_{i}", obs_type=obs_type, score=0.85 + i * 0.05)
            for i in range(n_obs)
        ],
        started_at=datetime.now().isoformat(),
        finished_at=datetime.now().isoformat(),
    )


# ── Fixtures ──

@pytest.fixture
def session():
    sess = create_session(":memory:")
    yield sess
    sess.close()


@pytest.fixture
def bridge(session):
    return PerceptionToAlertBridge(session)


@pytest.fixture
def pipeline(session):
    return EventGovernancePipeline(session)


@pytest.fixture
def sample_perception():
    return _make_perception_result()


# ═══════════════════════════════════════════════════════════════
#  1-6: PerceptionToAlertBridge
# ═══════════════════════════════════════════════════════════════

class TestPerceptionToAlertBridge:

    def test_bridge_ingest_creates_event(self, bridge, sample_perception):
        event = bridge.ingest(sample_perception)
        assert event is not None
        assert event.event_id.startswith("evt_")
        assert event.version == 1
        assert event.status == "under_review"
        assert event.candidate_id.startswith("cand_")
        assert event.event_type == "water_anomaly"

    def test_bridge_idempotent_returns_same_event(self, bridge, sample_perception):
        event1 = bridge.ingest(sample_perception)
        event2 = bridge.ingest(sample_perception)
        assert event1.event_id == event2.event_id
        assert event1.version == event2.version
        assert event1.candidate_id == event2.candidate_id

    def test_bridge_maps_observations_to_evidence(self, bridge, sample_perception):
        bridge.ingest(sample_perception)
        from core.event_governance.persistence import EvidenceBundleRecord
        bundles = bridge._session.query(EvidenceBundleRecord).all()
        assert len(bundles) >= 1
        items = json.loads(bundles[0].items)
        assert len(items) == 2
        assert items[0]["evidence_type"] == "water_extent"

    def test_bridge_event_type_water_anomaly(self, bridge, session):
        pr = _make_perception_result(
            pr_id="pr_water", n_obs=1,
            obs_type=ObservationType.OPTICAL_WATER_INDEX,
        )
        event = bridge.ingest(pr)
        assert event.event_type == "water_anomaly"

    def test_bridge_event_type_backscatter_change(self, bridge, session):
        pr = _make_perception_result(
            pr_id="pr_sar", n_obs=1,
            obs_type=ObservationType.SAR_BACKSCATTER_CHANGE,
        )
        event = bridge.ingest(pr)
        assert event.event_type == "backscatter_change"

    def test_bridge_event_type_object_detected(self, bridge, session):
        pr = _make_perception_result(
            pr_id="pr_obj", n_obs=1,
            obs_type=ObservationType.OBJECT_DETECTION,
        )
        event = bridge.ingest(pr)
        assert event.event_type == "object_detected"

    def test_bridge_creates_replay_entry(self, bridge, sample_perception):
        bridge.ingest(sample_perception)
        from core.event_governance.persistence import ReplayRecordDB
        entries = bridge._session.query(ReplayRecordDB).all()
        assert len(entries) >= 1
        assert entries[0].action == "replayed"
        assert entries[0].actor_ref == "perception_bridge"


# ═══════════════════════════════════════════════════════════════
#  7-10: EventGovernancePipeline
# ═══════════════════════════════════════════════════════════════

class TestEventGovernancePipeline:

    def test_pipeline_process_returns_ingestion_result(self, pipeline, sample_perception):
        result = pipeline.process(sample_perception)
        assert result.event is not None
        assert result.candidate_id.startswith("cand_")
        assert result.bundle_id.startswith("bundle_")
        assert result.n_observations == 2
        assert result.is_idempotent is False

    def test_pipeline_idempotent_detection(self, pipeline, sample_perception):
        result1 = pipeline.process(sample_perception)
        assert result1.is_idempotent is False
        result2 = pipeline.process(sample_perception)
        assert result2.is_idempotent is True
        assert result1.event.event_id == result2.event.event_id

    def test_pipeline_get_stats_returns_aggregates(self, pipeline, sample_perception):
        pipeline.process(sample_perception)
        stats = pipeline.get_stats()
        assert stats["total_candidates"] >= 1
        assert stats["total_events"] >= 1
        assert stats["total_bundles"] >= 1
        assert stats["total_replay_entries"] >= 1

    def test_pipeline_get_stats_includes_recent_events(self, pipeline, sample_perception):
        pipeline.process(sample_perception)
        stats = pipeline.get_stats()
        assert len(stats["recent_events"]) >= 1
        latest = stats["recent_events"][0]
        assert "event_id" in latest
        assert "status" in latest
        assert "event_type" in latest

    def test_pipeline_process_multiple_perceptions(self, pipeline, session):
        pr1 = _make_perception_result(pr_id="pr_multi_1", run_id="run_m1")
        pr2 = _make_perception_result(pr_id="pr_multi_2", run_id="run_m2")
        r1 = pipeline.process(pr1)
        r2 = pipeline.process(pr2)
        assert r1.event.event_id != r2.event.event_id
        stats = pipeline.get_stats()
        assert stats["total_events"] >= 2

    def test_pipeline_empty_observations(self, pipeline, session):
        pr = PerceptionResult(
            perception_result_id="pr_empty",
            inference_task_ref="task_empty",
            task_spec_ref="spec_v1",
            run_id="run_empty",
            status=ExecutionStatus.SUCCEEDED_EMPTY,
            observations=[],
        )
        result = pipeline.process(pr)
        assert result.n_observations == 0
        assert result.event is not None


# ═══════════════════════════════════════════════════════════════
#  11-15: API Endpoints
# ═══════════════════════════════════════════════════════════════

class TestIngestAPI:

    @pytest.fixture
    def client(self):
        import sys
        import tempfile
        import os
        from pathlib import Path
        svc_path = str(Path(__file__).resolve().parent.parent / "services")
        if svc_path not in sys.path:
            sys.path.insert(0, svc_path)

        from core.event_governance.persistence import create_session as make_gov_session, Base as GovBase
        from sqlalchemy import create_engine

        gov_db = os.path.join(tempfile.gettempdir(), f"test_gov_{os.urandom(4).hex()}.db")
        gov_engine = create_engine(
            f"sqlite:///{gov_db}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
        GovBase.metadata.create_all(gov_engine)

        from sqlalchemy.orm import sessionmaker
        GovSession = sessionmaker(bind=gov_engine)
        gov_session = GovSession()

        import services.main
        services.main._gov_session = gov_session

        from fastapi.testclient import TestClient
        client = TestClient(services.main.app)
        yield client

        try:
            gov_session.close()
            gov_engine.dispose()
        except Exception:
            pass
        try:
            for _ in range(5):
                try:
                    os.remove(gov_db)
                    break
                except PermissionError:
                    import time
                    time.sleep(0.1)
        except Exception:
            pass

    def test_api_ingest_perception(self, client):
        payload = _make_perception_result().model_dump()
        resp = client.post("/api/v2/ingest/perception", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ingested"
        assert data["event_id"].startswith("evt_")
        assert data["n_observations"] == 2
        assert data["event_version"] == 1

    def test_api_ingest_returns_correct_ids(self, client):
        pr = _make_perception_result(pr_id="pr_api_002")
        payload = pr.model_dump()
        resp = client.post("/api/v2/ingest/perception", json=payload)
        data = resp.json()
        expected_event_id = _compute_event_id("pr_api_002")
        expected_candidate_id = _compute_candidate_id("pr_api_002")
        assert data["event_id"] == expected_event_id
        assert data["candidate_id"] == expected_candidate_id

    def test_api_ingest_idempotent(self, client):
        payload = _make_perception_result(pr_id="pr_idem").model_dump()
        resp1 = client.post("/api/v2/ingest/perception", json=payload)
        resp2 = client.post("/api/v2/ingest/perception", json=payload)
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["event_id"] == resp2.json()["event_id"]
        assert resp2.json()["is_idempotent"] is True

    def test_api_ingest_invalid_input(self, client):
        resp = client.post(
            "/api/v2/ingest/perception",
            json={"bad_field": "no perception result"},
        )
        assert resp.status_code == 422

    def test_api_governance_stats(self, client):
        pr = _make_perception_result(pr_id="pr_stats").model_dump()
        client.post("/api/v2/ingest/perception", json=pr)
        resp = client.get("/api/v2/governance/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_candidates"] >= 1
        assert data["total_events"] >= 1
        assert "recent_events" in data


# ═══════════════════════════════════════════════════════════════
#  额外: 辅助函数测试
# ═══════════════════════════════════════════════════════════════

class TestBridgeHelpers:

    def test_compute_event_id_stable(self):
        id1 = _compute_event_id("test_input")
        id2 = _compute_event_id("test_input")
        assert id1 == id2
        assert id1.startswith("evt_")

    def test_compute_event_id_different_inputs_differ(self):
        id1 = _compute_event_id("input_a")
        id2 = _compute_event_id("input_b")
        assert id1 != id2
