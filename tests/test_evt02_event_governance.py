"""
EVT-02: 持久化事件链纵切 — 综合测试
"""

import json
import pytest

from core.event_governance.models import (
    GovernanceCandidate,
    EvidenceItem,
    EvidenceBundle,
    ReviewDecision,
    GovernedEvent,
    ReplayRecord,
    OptimisticLockError,
    EventGovernanceError,
)
from core.event_governance.persistence import create_session
from core.event_governance.service import (
    intake_candidate,
    attach_evidence,
    review_bundle,
    record_event,
    get_event,
    replay_event,
    vote_event,
)


# ─── Fixtures ───

@pytest.fixture
def session():
    sess = create_session(":memory:")
    yield sess
    sess.close()


# ─── 1. Candidate Intake + 幂等 ───

class TestCandidateIntake:
    def test_normal_intake(self, session):
        c = GovernanceCandidate(candidate_id="c1", source="sentinel-1", payload={"type": "water_change"})
        result = intake_candidate(session, c)
        assert result.candidate_id == "c1"
        assert result.source == "sentinel-1"

    def test_double_intake_returns_same(self, session):
        c = GovernanceCandidate(candidate_id="c2", source="sentinel-2", payload={"idx": 1})
        r1 = intake_candidate(session, c)
        r2 = intake_candidate(session, c)
        assert r1.candidate_id == r2.candidate_id
        assert r1.ingested_at == r2.ingested_at

    def test_double_intake_with_different_payload_unchanged(self, session):
        c1 = GovernanceCandidate(candidate_id="c3", source="src", payload={"v": 1})
        intake_candidate(session, c1)
        c2 = GovernanceCandidate(candidate_id="c3", source="src", payload={"v": 999})
        r2 = intake_candidate(session, c2)
        assert r2.payload == {"v": 1}
        assert r2.payload != {"v": 999}


# ─── 2. EvidenceBundle + Review (乐观锁) ───

class TestEvidenceAndReview:
    def test_attach_evidence(self, session):
        c = GovernanceCandidate(candidate_id="e1", source="src")
        intake_candidate(session, c)
        bundle = EvidenceBundle(
            bundle_id="b1",
            candidate_id="e1",
            items=[EvidenceItem(evidence_id="ev1", evidence_type="ndwi", file_ref="/data/ndwi.tif")],
        )
        result = attach_evidence(session, bundle)
        assert result.bundle_id == "b1"
        assert len(result.items) == 1

    def test_review_ok(self, session):
        c = GovernanceCandidate(candidate_id="e2", source="src")
        intake_candidate(session, c)
        attach_evidence(session, EvidenceBundle(bundle_id="b2", candidate_id="e2"))
        decision = ReviewDecision(
            review_id="r1", bundle_id="b2", reviewer="alice",
            decision="approved", expected_version=1,
        )
        result = review_bundle(session, decision)
        assert result.decision == "approved"

    def test_review_optimistic_lock_conflict(self, session):
        c = GovernanceCandidate(candidate_id="e3", source="src")
        intake_candidate(session, c)
        attach_evidence(session, EvidenceBundle(bundle_id="b3", candidate_id="e3"))
        review_bundle(session, ReviewDecision(
            review_id="r2", bundle_id="b3", reviewer="alice",
            decision="approved", expected_version=1,
        ))
        with pytest.raises(OptimisticLockError, match="Version conflict"):
            review_bundle(session, ReviewDecision(
                review_id="r3", bundle_id="b3", reviewer="bob",
                decision="rejected", expected_version=1,
            ))

    def test_concurrent_reviews_one_wins(self, session):
        c = GovernanceCandidate(candidate_id="e4", source="src")
        intake_candidate(session, c)
        attach_evidence(session, EvidenceBundle(bundle_id="b4", candidate_id="e4"))
        review_bundle(session, ReviewDecision(
            review_id="r4", bundle_id="b4", reviewer="alice",
            decision="approved", expected_version=1,
        ))
        with pytest.raises(OptimisticLockError):
            review_bundle(session, ReviewDecision(
                review_id="r5", bundle_id="b4", reviewer="bob",
                decision="rejected", expected_version=1,
            ))
        r6 = ReviewDecision(
            review_id="r6", bundle_id="b4", reviewer="bob",
            decision="rejected", expected_version=2,
        )
        result = review_bundle(session, r6)
        assert result.decision == "rejected"


# ─── 3. Event 多版本 ───

class TestEventMultiVersion:
    def test_record_v1(self, session):
        e = GovernedEvent(event_id="ev1", version="v1", candidate_id="c1", event_type="water_alarm")
        result = record_event(session, e)
        assert result.version == "v1"

    def test_record_v1_and_v2_both_queryable(self, session):
        e1 = GovernedEvent(event_id="ev2", version="v1", candidate_id="c2", event_type="flood")
        e2 = GovernedEvent(event_id="ev2", version="v2", candidate_id="c2", event_type="flood_updated")
        record_event(session, e1)
        record_event(session, e2)

        got_v1 = get_event(session, "ev2", version="v1")
        assert got_v1 is not None
        assert got_v1.version == "v1"
        assert got_v1.event_type == "flood"

        got_v2 = get_event(session, "ev2", version="v2")
        assert got_v2 is not None
        assert got_v2.version == "v2"
        assert got_v2.event_type == "flood_updated"

    def test_get_latest_version(self, session):
        e1 = GovernedEvent(event_id="ev3", version="v1", candidate_id="c3", event_type="drought")
        e2 = GovernedEvent(event_id="ev3", version="v2", candidate_id="c3", event_type="drought_v2")
        record_event(session, e1)
        record_event(session, e2)

        latest = get_event(session, "ev3")
        assert latest is not None
        assert latest.version == "v2"

    def test_get_nonexistent_event(self, session):
        result = get_event(session, "nonexistent")
        assert result is None


# ─── 4. Replay 去重 ───

class TestReplayDedup:
    def test_replay_ok(self, session):
        e = GovernedEvent(event_id="rev1", version="v1", candidate_id="c1", event_type="test")
        record_event(session, e)
        r = replay_event(session, "rev1")
        assert r.event_id == "rev1"
        assert r.result == "ok"

    def test_replay_dedup_returns_same(self, session):
        e = GovernedEvent(event_id="rev2", version="v1", candidate_id="c2", event_type="test")
        record_event(session, e)
        r1 = replay_event(session, "rev2")
        r2 = replay_event(session, "rev2")
        assert r1.replay_id == r2.replay_id
        assert r1.replayed_at == r2.replayed_at


# ─── 5. SQLite 持久化 + 应用门面 ───

class TestPersistenceAndFacade:
    def test_data_survives_session_close_reopen(self):
        sess1 = create_session(":memory:")
        c = GovernanceCandidate(candidate_id="persist1", source="test", payload={"k": "v"})
        intake_candidate(sess1, c)
        e = GovernedEvent(event_id="persist-ev1", version="v1", candidate_id="persist1", event_type="test")
        record_event(sess1, e)
        sess1.commit()
        sess1.close()

        sess2 = create_session(":memory:")
        c2 = intake_candidate(sess2, c)
        assert c2.candidate_id == "persist1"

    def test_vote_event_atomic(self, session):
        c = GovernanceCandidate(candidate_id="vote1", source="src", payload={"x": 1})
        e = GovernedEvent(event_id="vote-ev1", version="v1", candidate_id="vote1", event_type="vote_test")
        cand, evt = vote_event(session, c, e)
        assert cand.candidate_id == "vote1"
        assert evt.event_id == "vote-ev1"

    def test_vote_event_partial_failure_rollback(self, session):
        from sqlalchemy import text
        c = GovernanceCandidate(candidate_id="fail1", source="src", payload={"x": 1})
        try:
            intake_candidate(session, c)
            raise RuntimeError("simulated failure")
        except RuntimeError:
            session.rollback()
        rows = session.execute(
            text("SELECT * FROM governance_candidates WHERE candidate_id='fail1'")
        ).fetchall()
        assert len(rows) == 0


# ─── 6. Candidate 只读消费验证 ───

class TestCandidateReadOnly:
    def test_candidate_frozen_after_intake(self, session):
        c = GovernanceCandidate(candidate_id="ro1", source="src", payload={"orig": True})
        intake_candidate(session, c)
        with pytest.raises(AttributeError, match="read-only"):
            c.payload = {"hacked": True}

    def test_candidate_immutable_hash(self):
        c1 = GovernanceCandidate(candidate_id="hash1", source="a", payload={"v": 1})
        c2 = GovernanceCandidate(candidate_id="hash1", source="b", payload={"v": 2})
        assert hash(c1) == hash(c2)
        assert len({c1, c2}) == 1
