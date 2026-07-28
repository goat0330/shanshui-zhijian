"""
治理链语义测试 — 正确链: DetectionCandidate → Intake → Review → Event → Replay

核心断言:
1. Intake 创建 candidate + bundle，不创建 event
2. Review 创建 event v1 (如无 event) 或 event v{n+1} (如已有 event)
3. 未经 Review 不得形成 confirmed/rejected Event
"""

import json
import pytest
from datetime import datetime

from core.event_governance.bridge import (
    CandidateIntakeBridge,
    EvidenceBridge,
    ReviewBridge,
    EventBridge,
    ReplayBridge,
)
from core.event_governance.pipeline import EventGovernancePipeline
from core.event_governance.persistence import create_session, GovernedEventRecord, CandidateRecord
from core.event_governance.models import GovernedEvent, OptimisticLockError
from core.schemas.contracts.candidate import DetectionCandidate


def _make_candidate(candidate_id: str = "cand_test_001",
                    n_evidence: int = 2) -> DetectionCandidate:
    return DetectionCandidate(
        candidate_id=candidate_id,
        observation_refs=[f"obs_{i}" for i in range(n_evidence)],
        temporal_extent={"start": "2026-01-01", "end": "2026-01-15"},
        candidate_type="water_extent_change",
        score=0.85,
        evidence_refs=[f"ev_ref_{i}" for i in range(n_evidence)],
        rule_version="1.0.0",
    )


@pytest.fixture
def session():
    sess = create_session(":memory:")
    yield sess
    sess.close()


@pytest.fixture
def pipeline(session):
    return EventGovernancePipeline(session)


@pytest.fixture
def sample_candidate():
    return _make_candidate()


# ═══════════════════════════════════════════════════════════
#  1. CandidateIntakeBridge — 只创建 candidate+bundle
# ═══════════════════════════════════════════════════════════

class TestCandidateIntakeBridge:
    def test_intake_creates_candidate(self, session, sample_candidate):
        bridge = CandidateIntakeBridge(session)
        result = bridge.intake(sample_candidate)
        assert result["candidate_id"] == "cand_test_001"
        assert result["bundle_id"].startswith("bundle_")
        assert result["n_evidence_items"] == 2
        assert result["status"] == "intake_complete"

    def test_intake_does_not_create_event(self, session, sample_candidate):
        bridge = CandidateIntakeBridge(session)
        bridge.intake(sample_candidate)
        events = session.query(GovernedEventRecord).count()
        assert events == 0, "Intake must NOT create events"

    def test_intake_idempotent(self, session, sample_candidate):
        bridge = CandidateIntakeBridge(session)
        r1 = bridge.intake(sample_candidate)
        r2 = bridge.intake(sample_candidate)
        assert r2["status"] == "already_ingested"
        assert r1["candidate_id"] == r2["candidate_id"]

    def test_intake_with_zero_evidence(self, session):
        c = DetectionCandidate(
            candidate_id="cand_no_ev",
            observation_refs=["obs_1"],
            temporal_extent={"start": "2026-01-01", "end": "2026-01-15"},
            candidate_type="water_extent_change",
            score=0.85,
            evidence_refs=[],
            rule_version="1.0.0",
        )
        bridge = CandidateIntakeBridge(session)
        result = bridge.intake(c)
        assert result["n_evidence_items"] == 0
        assert result["status"] == "intake_complete"

    def test_intake_stores_payload(self, session, sample_candidate):
        bridge = CandidateIntakeBridge(session)
        bridge.intake(sample_candidate)
        record = session.query(CandidateRecord).filter_by(candidate_id="cand_test_001").first()
        assert record is not None
        assert record.source == "water_extent_change"


# ═══════════════════════════════════════════════════════════
#  2. ReviewBridge — 在 event 不存在时创建 event v1
# ═══════════════════════════════════════════════════════════

class TestReviewBridge:
    @pytest.fixture
    def rv_bridge(self, session, sample_candidate):
        CandidateIntakeBridge(session).intake(sample_candidate)
        return ReviewBridge(session)

    def test_review_creates_event_v1(self, rv_bridge, session):
        rv_bridge.submit(
            bundle_id="bundle_cand_test_001", reviewer="alice",
            decision="confirm", expected_version=1,
        )
        events = session.query(GovernedEventRecord).all()
        assert len(events) == 1
        assert events[0].version == 1
        assert events[0].status == "confirmed"

    def test_review_event_id_stable(self, rv_bridge, session):
        rv_bridge.submit(
            bundle_id="bundle_cand_test_001", reviewer="alice",
            decision="confirm", expected_version=1,
        )
        e = session.query(GovernedEventRecord).first()
        assert e.event_id.startswith("evt_")

    def test_review_reject_does_not_create_event(self, rv_bridge, session):
        rv_bridge.submit(
            bundle_id="bundle_cand_test_001", reviewer="bob",
            decision="reject", expected_version=1,
        )
        events = session.query(GovernedEventRecord).count()
        assert events == 0, "Reject must NOT create an Event"

    def test_review_needs_more_evidence_no_event(self, rv_bridge, session):
        rv_bridge.submit(
            bundle_id="bundle_cand_test_001", reviewer="carol",
            decision="needs_more_evidence", expected_version=1,
        )
        events = session.query(GovernedEventRecord).count()
        assert events == 0, "needs_more_evidence must NOT create an Event"

    def test_second_review_confirm_increments_version(self, rv_bridge, session):
        rv_bridge.submit(bundle_id="bundle_cand_test_001", reviewer="a",
                         decision="confirm", expected_version=1)
        rv_bridge.submit(bundle_id="bundle_cand_test_001", reviewer="b",
                         decision="confirm", expected_version=2,
                         comment="second opinion")
        events = session.query(GovernedEventRecord).order_by(GovernedEventRecord.version).all()
        assert len(events) == 2
        assert events[0].version == 1 and events[0].status == "confirmed"
        assert events[1].version == 2 and events[1].status == "confirmed"

    def test_review_version_conflict(self, rv_bridge, session):
        rv_bridge.submit(bundle_id="bundle_cand_test_001", reviewer="a",
                         decision="confirm", expected_version=1)
        with pytest.raises(OptimisticLockError):
            rv_bridge.submit(bundle_id="bundle_cand_test_001", reviewer="b",
                             decision="confirm", expected_version=1)

    def test_review_list(self, rv_bridge, session):
        rv_bridge.submit(bundle_id="bundle_cand_test_001", reviewer="a",
                         decision="confirm", expected_version=1)
        reviews = rv_bridge.list_reviews()
        assert len(reviews) == 1
        assert reviews[0]["decision"] == "confirm"


# ═══════════════════════════════════════════════════════════
#  3. EventBridge — 只查已有 event
# ═══════════════════════════════════════════════════════════

class TestEventBridge:
    @pytest.fixture
    def evt_setup(self, session):
        ci = CandidateIntakeBridge(session)
        ci.intake(_make_candidate("cand_ev_1"))
        ci.intake(_make_candidate("cand_ev_2"))
        ci.intake(_make_candidate("cand_ev_3"))
        rb = ReviewBridge(session)
        rb.submit(bundle_id="bundle_cand_ev_1", reviewer="a",
                  decision="confirm", expected_version=1)
        rb.submit(bundle_id="bundle_cand_ev_2", reviewer="b",
                  decision="confirm", expected_version=1)
        # cand_ev_3 is rejected — no Event created
        rb.submit(bundle_id="bundle_cand_ev_3", reviewer="c",
                  decision="reject", expected_version=1)
        return EventBridge(session)

    def test_list_events(self, evt_setup):
        events = evt_setup.list_events()
        assert len(events) == 2  # only confirmed events

    def test_list_by_status(self, evt_setup):
        confirmed = evt_setup.list_events(status="confirmed")
        assert len(confirmed) == 2

    def test_get_event(self, evt_setup):
        events = evt_setup.list_events()
        e = evt_setup.get_event(events[0]["event_id"])
        assert e is not None

    def test_get_event_nonexistent(self, evt_setup):
        assert evt_setup.get_event("nonexistent") is None

    def test_events_by_status(self, evt_setup):
        counts = evt_setup.get_events_by_status()
        assert counts.get("confirmed", 0) >= 2

    def test_no_events_before_review(self, session):
        ci = CandidateIntakeBridge(session)
        ci.intake(_make_candidate("cand_no_evt"))
        eb = EventBridge(session)
        assert eb.list_events() == []


# ═══════════════════════════════════════════════════════════
#  4. ReplayBridge
# ═══════════════════════════════════════════════════════════

class TestReplayBridge:
    @pytest.fixture
    def rp_setup(self, session):
        ci = CandidateIntakeBridge(session)
        ci.intake(_make_candidate("cand_rp"))
        rb = ReviewBridge(session)
        rb.submit(bundle_id="bundle_cand_rp", reviewer="a",
                  decision="confirm", expected_version=1)
        return ReplayBridge(session)

    def test_timeline_not_empty(self, rp_setup):
        from core.event_governance.bridge import EventBridge
        eb = EventBridge(rp_setup._session)
        events = eb.list_events()
        assert len(events) >= 1
        timeline = rp_setup.get_timeline(events[0]["event_id"])
        assert len(timeline) >= 1

    def test_timeline_unknown_event(self, rp_setup):
        assert rp_setup.get_timeline("nonexistent") == []

    def test_recent_entries(self, rp_setup):
        entries = rp_setup.get_recent_entries()
        assert len(entries) >= 1


# ═══════════════════════════════════════════════════════════
#  5. Pipeline 集成
# ═══════════════════════════════════════════════════════════

class TestPipeline:
    def test_pipeline_intake_only(self, pipeline, sample_candidate):
        result = pipeline.intake(sample_candidate)
        assert result.candidate_id == "cand_test_001"
        assert result.is_idempotent is False
        assert not hasattr(result, "event")

    def test_pipeline_intake_idempotent(self, pipeline, sample_candidate):
        r1 = pipeline.intake(sample_candidate)
        r2 = pipeline.intake(sample_candidate)
        assert r1.candidate_id == r2.candidate_id
        assert r2.is_idempotent is True

    def test_pipeline_get_stats(self, pipeline, sample_candidate):
        pipeline.intake(sample_candidate)
        stats = pipeline.get_stats()
        assert stats["total_candidates"] >= 1

    def test_pipeline_snapshot_empty(self, pipeline):
        snap = pipeline.get_snapshot()
        assert snap["totals"]["candidates"] == 0
        assert snap["totals"]["events_distinct"] == 0

    def test_pipeline_snapshot_after_intake(self, pipeline, session, sample_candidate):
        pipeline.intake(sample_candidate)
        snap = pipeline.get_snapshot()
        assert snap["totals"]["candidates"] >= 1
        assert snap["totals"]["events_distinct"] == 0
        assert snap["funnel"]["candidates_ingested"] >= 1

    def test_pipeline_snapshot_funnel(self, pipeline, session, sample_candidate):
        pipeline.intake(sample_candidate)
        rb = ReviewBridge(session)
        rb.submit(bundle_id="bundle_cand_test_001", reviewer="a",
                  decision="confirm", expected_version=1)
        snap = pipeline.get_snapshot()
        assert snap["funnel"]["candidates_ingested"] >= 1
        assert snap["funnel"]["candidates_reviewed"] >= 1
        assert snap["funnel"]["events_created"] >= 1

    def test_pipeline_snapshot_with_reviews(self, pipeline, session, sample_candidate):
        pipeline.intake(sample_candidate)
        rb = ReviewBridge(session)
        rb.submit(bundle_id="bundle_cand_test_001", reviewer="alice",
                  decision="confirm", expected_version=1)
        snap = pipeline.get_snapshot()
        assert snap["totals"]["reviews"] >= 1
        assert len(snap["recent_reviews"]) >= 1
        assert snap["events_by_status"].get("confirmed", 0) >= 1


# ═══════════════════════════════════════════════════════════
#  6. 语义约束验证
# ═══════════════════════════════════════════════════════════

class TestSemanticGuarantees:
    def test_no_candidate_no_event(self, session):
        assert session.query(GovernedEventRecord).count() == 0

    def test_no_event_without_review(self, session):
        """No event exists until a review decision is submitted."""
        CandidateIntakeBridge(session).intake(_make_candidate("cand_sem"))
        assert session.query(GovernedEventRecord).count() == 0
        ReviewBridge(session).submit(
            bundle_id="bundle_cand_sem", reviewer="a",
            decision="confirm", expected_version=1,
        )
        assert session.query(GovernedEventRecord).count() == 1

    def test_review_without_candidate_raises(self, session):
        rb = ReviewBridge(session)
        with pytest.raises(Exception):
            rb.submit(bundle_id="bundle_nonexistent", reviewer="a",
                      decision="confirm", expected_version=1)

    def test_event_only_after_review(self, session, sample_candidate):
        ci = CandidateIntakeBridge(session)
        ci.intake(sample_candidate)
        assert session.query(GovernedEventRecord).count() == 0
        rb = ReviewBridge(session)
        rb.submit(bundle_id="bundle_cand_test_001", reviewer="a",
                  decision="confirm", expected_version=1)
        assert session.query(GovernedEventRecord).count() == 1
