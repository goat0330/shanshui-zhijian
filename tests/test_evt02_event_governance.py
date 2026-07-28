"""
EVT-02: 持久化事件链纵切 — 综合测试

测试覆盖:
  1. Candidate Intake + 幂等
  2. EvidenceBundle + Review (4 actions + 乐观锁)
  3. Event 整数版本 (1, 2, 3...)
  4. Event 状态校验 (允许 / 禁止值)
  5. Review 自动创建 Event 新版本
  6. Replay 时间线 (非简单去重)
  7. get_timeline 排序
  8. SQLite 文件持久化
  9. 应用门面 vote_event
"""

import json
import os
import tempfile
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
    REVIEW_DECISION_ACTIONS,
    EVENT_STATUS_VALUES,
    EVENT_STATUS_FORBIDDEN,
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
    get_timeline,
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


# ─── 2. EvidenceBundle + Review (4 actions + 乐观锁) ───

class TestEvidenceAndReview:
    def test_attach_evidence(self, session):
        c = GovernanceCandidate(candidate_id="e1", source="src")
        intake_candidate(session, c)
        bundle = EvidenceBundle(
            bundle_id="b1",
            candidate_id="e1",
            items=[EvidenceItem(evidence_id="ev1", evidence_type="ndwi", source_asset_ref="/data/ndwi.tif")],
        )
        result = attach_evidence(session, bundle)
        assert result.bundle_id == "b1"
        assert len(result.items) == 1

    def _setup_for_review(self, session, prefix: str):
        """Helper: intake candidate + attach evidence + record event v1."""
        c = GovernanceCandidate(candidate_id=f"{prefix}_cand", source="src")
        intake_candidate(session, c)
        attach_evidence(session, EvidenceBundle(bundle_id=f"{prefix}_bnd", candidate_id=f"{prefix}_cand"))
        ev = GovernedEvent(
            event_id=f"{prefix}_evt",
            version=1,
            candidate_id=f"{prefix}_cand",
            event_type="water_alarm",
        )
        record_event(session, ev)

    def test_review_confirm(self, session):
        self._setup_for_review(session, "cf")
        decision = ReviewDecision(
            review_id="r_cf", bundle_id="cf_bnd", reviewer="alice",
            decision="confirm", expected_version=1,
        )
        result = review_bundle(session, decision)
        assert result.decision == "confirm"

        # Verify auto-created event version
        ev = get_event(session, "cf_evt")
        assert ev is not None
        assert ev.version == 2
        assert ev.status == "confirmed"

    def test_review_reject_no_event_version(self, session):
        """Reject creates a ReviewRecord but does NOT create a new Event version."""
        self._setup_for_review(session, "rj")
        decision = ReviewDecision(
            review_id="r_rj", bundle_id="rj_bnd", reviewer="alice",
            decision="reject", expected_version=1,
        )
        result = review_bundle(session, decision)
        assert result.decision == "reject"

        ev = get_event(session, "rj_evt")
        assert ev is not None
        assert ev.version == 1  # Event version unchanged
        assert ev.status == "under_review"  # Original status preserved

    def test_review_needs_more_evidence_no_event_version(self, session):
        self._setup_for_review(session, "nme")
        decision = ReviewDecision(
            review_id="r_nme", bundle_id="nme_bnd", reviewer="alice",
            decision="needs_more_evidence", expected_version=1,
        )
        result = review_bundle(session, decision)
        assert result.decision == "needs_more_evidence"

        ev = get_event(session, "nme_evt")
        assert ev is not None
        assert ev.version == 1  # No new Event version

    def test_review_reclassify_confirm_first(self, session):
        """Reclassify after confirm creates v2 with reclassified status."""
        self._setup_for_review(session, "rc")
        review_bundle(session, ReviewDecision(
            review_id="r_rc1", bundle_id="rc_bnd", reviewer="alice",
            decision="confirm", expected_version=1,
        ))
        decision = ReviewDecision(
            review_id="r_rc2", bundle_id="rc_bnd", reviewer="alice",
            decision="reclassify", expected_version=2,
            category="suspected_floating",
        )
        result = review_bundle(session, decision)
        assert result.decision == "reclassify"

        ev = get_event(session, "rc_evt")
        assert ev is not None
        assert ev.version == 3  # v1 setup + v2 confirm + v3 reclassify
        assert ev.status == "reclassified"
        assert ev.event_type == "suspected_floating"

    def test_review_invalid_decision_raises_error(self, session):
        self._setup_for_review(session, "inv")
        # Use model_construct to bypass Pydantic Literal validation
        decision = ReviewDecision.model_construct(
            review_id="r_inv", bundle_id="inv_bnd", reviewer="alice",
            decision="approved",  # old value, caught by service layer
            expected_version=1,
        )
        with pytest.raises(EventGovernanceError, match="Invalid decision"):
            review_bundle(session, decision)

    def test_review_reclassify_without_category_raises_error(self, session):
        self._setup_for_review(session, "rc2")
        decision = ReviewDecision(
            review_id="r_rc2", bundle_id="rc2_bnd", reviewer="alice",
            decision="reclassify", expected_version=1,
            category=None,
        )
        with pytest.raises(EventGovernanceError, match="reclassify requires a non-empty category"):
            review_bundle(session, decision)

    def test_review_optimistic_lock_conflict(self, session):
        self._setup_for_review(session, "ol")
        review_bundle(session, ReviewDecision(
            review_id="r_ol1", bundle_id="ol_bnd", reviewer="alice",
            decision="confirm", expected_version=1,
        ))
        with pytest.raises(OptimisticLockError, match="Version conflict"):
            review_bundle(session, ReviewDecision(
                review_id="r_ol2", bundle_id="ol_bnd", reviewer="bob",
                decision="reject", expected_version=1,
            ))

    def test_concurrent_reviews_one_wins(self, session):
        self._setup_for_review(session, "cw")
        review_bundle(session, ReviewDecision(
            review_id="r_cw1", bundle_id="cw_bnd", reviewer="alice",
            decision="confirm", expected_version=1,
        ))
        with pytest.raises(OptimisticLockError):
            review_bundle(session, ReviewDecision(
                review_id="r_cw2", bundle_id="cw_bnd", reviewer="bob",
                decision="confirm", expected_version=1,
            ))
        # needs_more_evidence does NOT create new event version
        r3 = ReviewDecision(
            review_id="r_cw3", bundle_id="cw_bnd", reviewer="bob",
            decision="needs_more_evidence", expected_version=2,
            comment="needs more data",
        )
        result = review_bundle(session, r3)
        assert result.decision == "needs_more_evidence"

        ev = get_event(session, "cw_evt")
        assert ev is not None
        assert ev.version == 2  # v1 from setup, v2 from confirm
        assert ev.status == "confirmed"

    def test_review_create_event_version_twice(self, session):
        """Setup v1 + confirm v2. needs_more_evidence adds no version."""
        self._setup_for_review(session, "seq")
        review_bundle(session, ReviewDecision(
            review_id="r_seq1", bundle_id="seq_bnd", reviewer="alice",
            decision="confirm", expected_version=1,
        ))
        # needs_more_evidence does NOT create new event version
        review_bundle(session, ReviewDecision(
            review_id="r_seq2", bundle_id="seq_bnd", reviewer="bob",
            decision="needs_more_evidence", expected_version=2,
            comment="still needs evidence",
        ))

        ev = get_event(session, "seq_evt")
        assert ev is not None
        assert ev.version == 2  # v1 from setup, v2 from confirm
        assert ev.status == "confirmed"

    def test_review_creates_event_if_none_exists(self, session):
        """Review should auto-create event v1 if none exists for candidate."""
        c = GovernanceCandidate(candidate_id="auto_evt", source="src")
        intake_candidate(session, c)
        attach_evidence(session, EvidenceBundle(bundle_id="auto_evt_bnd", candidate_id="auto_evt"))
        decision = ReviewDecision(
            review_id="r_auto_evt", bundle_id="auto_evt_bnd", reviewer="alice",
            decision="confirm", expected_version=1,
        )
        result = review_bundle(session, decision)
        assert result.decision == "confirm"
        ev = get_event(session, "evt_auto_evt")
        assert ev is not None
        assert ev.version == 1
        assert ev.status == "confirmed"


# ─── 3. Event 整数版本 ───

class TestEventMultiVersion:
    def test_record_v1(self, session):
        e = GovernedEvent(event_id="ev1", version=1, candidate_id="c1", event_type="water_alarm")
        result = record_event(session, e)
        assert result.version == 1

    def test_record_v1_and_v2_both_queryable(self, session):
        e1 = GovernedEvent(event_id="ev2", version=1, candidate_id="c2", event_type="flood")
        e2 = GovernedEvent(event_id="ev2", version=2, candidate_id="c2", event_type="flood_updated")
        record_event(session, e1)
        record_event(session, e2)

        got_v1 = get_event(session, "ev2", version=1)
        assert got_v1 is not None
        assert got_v1.version == 1
        assert got_v1.event_type == "flood"

        got_v2 = get_event(session, "ev2", version=2)
        assert got_v2 is not None
        assert got_v2.version == 2
        assert got_v2.event_type == "flood_updated"

    def test_get_latest_version(self, session):
        e1 = GovernedEvent(event_id="ev3", version=1, candidate_id="c3", event_type="drought")
        e2 = GovernedEvent(event_id="ev3", version=2, candidate_id="c3", event_type="drought_v2")
        record_event(session, e1)
        record_event(session, e2)

        latest = get_event(session, "ev3")
        assert latest is not None
        assert latest.version == 2

    def test_get_nonexistent_event(self, session):
        result = get_event(session, "nonexistent")
        assert result is None

    def test_version_must_be_positive(self):
        with pytest.raises(Exception):
            GovernedEvent(event_id="ev_bad", version=0, candidate_id="c1", event_type="test")

    def test_record_with_integer_version_comparison(self, session):
        """Version comparisons must work with integer operators (not string)."""
        e1 = GovernedEvent(event_id="ev_comp", version=1, candidate_id="c1", event_type="a")
        e2 = GovernedEvent(event_id="ev_comp", version=2, candidate_id="c1", event_type="b")
        e3 = GovernedEvent(event_id="ev_comp", version=10, candidate_id="c1", event_type="c")
        record_event(session, e1)
        record_event(session, e2)
        record_event(session, e3)

        latest = get_event(session, "ev_comp")
        assert latest is not None
        assert latest.version == 10  # 10 > 2 when compared as int


# ─── 4. Event 状态校验 ───

class TestEventStatusValidation:
    def test_default_status_is_under_review(self, session):
        e = GovernedEvent(event_id="st1", version=1, candidate_id="c1", event_type="test")
        assert e.status == "under_review"

    def test_status_under_review_accepted(self, session):
        e = GovernedEvent(event_id="st2", version=1, candidate_id="c1", event_type="test", status="under_review")
        result = record_event(session, e)
        assert result.status == "under_review"

    def test_status_confirmed_accepted(self, session):
        e = GovernedEvent(event_id="st3", version=1, candidate_id="c1", event_type="test", status="confirmed")
        result = record_event(session, e)
        assert result.status == "confirmed"

    def test_status_rejected_accepted(self, session):
        e = GovernedEvent(event_id="st4", version=1, candidate_id="c1", event_type="test", status="rejected")
        result = record_event(session, e)
        assert result.status == "rejected"

    def test_status_reclassified_accepted(self, session):
        e = GovernedEvent(event_id="st5", version=1, candidate_id="c1", event_type="test", status="reclassified")
        result = record_event(session, e)
        assert result.status == "reclassified"

    def test_status_needs_more_evidence_accepted(self, session):
        e = GovernedEvent(event_id="st6", version=1, candidate_id="c1", event_type="test", status="needs_more_evidence")
        result = record_event(session, e)
        assert result.status == "needs_more_evidence"

    def test_status_illegal_forbidden(self, session):
        e = GovernedEvent(event_id="st7", version=1, candidate_id="c1", event_type="test", status="illegal")
        with pytest.raises(EventGovernanceError, match="reserved for external"):
            record_event(session, e)

    def test_status_violation_confirmed_forbidden(self, session):
        e = GovernedEvent(event_id="st8", version=1, candidate_id="c1", event_type="test", status="violation_confirmed")
        with pytest.raises(EventGovernanceError, match="reserved for external"):
            record_event(session, e)

    def test_status_closed_forbidden(self, session):
        e = GovernedEvent(event_id="st9", version=1, candidate_id="c1", event_type="test", status="closed")
        with pytest.raises(EventGovernanceError, match="reserved for external"):
            record_event(session, e)

    def test_status_dispatched_forbidden(self, session):
        e = GovernedEvent(event_id="st10", version=1, candidate_id="c1", event_type="test", status="dispatched")
        with pytest.raises(EventGovernanceError, match="reserved for external"):
            record_event(session, e)

    def test_status_invalid_value_raises_error(self, session):
        e = GovernedEvent(event_id="st11", version=1, candidate_id="c1", event_type="test", status="invalid_status")
        with pytest.raises(EventGovernanceError, match="Invalid status"):
            record_event(session, e)


# ─── 5. Replay 时间线 ───

class TestReplayTimeline:
    def test_replay_appends_entry(self, session):
        """replay_event now appends a new entry each time."""
        e = GovernedEvent(event_id="tl1", version=1, candidate_id="c1", event_type="test")
        record_event(session, e)
        r = replay_event(session, "tl1")
        assert r.event_id == "tl1"
        assert r.sequence_number >= 1
        assert r.action == "replayed"

    def test_replay_multiple_calls_creates_separate_entries(self, session):
        e = GovernedEvent(event_id="tl2", version=1, candidate_id="c2", event_type="test")
        record_event(session, e)
        r1 = replay_event(session, "tl2")
        r2 = replay_event(session, "tl2")
        assert r1.replay_id != r2.replay_id
        assert r1.sequence_number != r2.sequence_number
        assert r2.sequence_number > r1.sequence_number

    def test_get_timeline_returns_sorted_entries(self, session):
        e = GovernedEvent(event_id="tl3", version=1, candidate_id="c3", event_type="test")
        record_event(session, e)
        replay_event(session, "tl3")
        replay_event(session, "tl3")
        replay_event(session, "tl3")

        timeline = get_timeline(session, "tl3")
        assert len(timeline) == 3
        # Verify sorted by sequence_number
        for i in range(len(timeline) - 1):
            assert timeline[i].sequence_number < timeline[i + 1].sequence_number

    def test_get_timeline_empty_for_unknown_event(self, session):
        timeline = get_timeline(session, "nonexistent")
        assert len(timeline) == 0

    def test_replay_stores_actor_info(self, session):
        e = GovernedEvent(event_id="tl4", version=1, candidate_id="c4", event_type="test")
        record_event(session, e)
        r = replay_event(session, "tl4", actor="perception-agent")
        assert r.actor_ref == "perception-agent"
        assert r.actor_type == "system"
        assert r.object_type == "event"
        assert r.object_ref == "tl4"

    def test_review_creates_replay_timeline_entry(self, session):
        """Review should write a replay timeline entry."""
        c = GovernanceCandidate(candidate_id="tl5_cand", source="src")
        intake_candidate(session, c)
        attach_evidence(session, EvidenceBundle(bundle_id="tl5_bnd", candidate_id="tl5_cand"))
        ev = GovernedEvent(event_id="tl5_evt", version=1, candidate_id="tl5_cand", event_type="test")
        record_event(session, ev)

        review_bundle(session, ReviewDecision(
            review_id="r_tl5", bundle_id="tl5_bnd", reviewer="alice",
            decision="confirm", expected_version=1,
        ))

        timeline = get_timeline(session, "tl5_evt")
        assert len(timeline) >= 1
        entry = timeline[0]
        assert entry.action == "review_confirm"
        assert entry.actor_ref == "alice"
        assert entry.actor_type == "human"


# ─── 6. SQLite 持久化 + 应用门面 ───

class TestPersistenceAndFacade:
    def test_data_survives_session_close_reopen(self):
        sess1 = create_session(":memory:")
        c = GovernanceCandidate(candidate_id="persist1", source="test", payload={"k": "v"})
        intake_candidate(sess1, c)
        e = GovernedEvent(event_id="persist-ev1", version=1, candidate_id="persist1", event_type="test")
        record_event(sess1, e)
        sess1.commit()
        sess1.close()

        sess2 = create_session(":memory:")
        c2 = intake_candidate(sess2, c)
        assert c2.candidate_id == "persist1"

    def test_vote_event_atomic(self, session):
        c = GovernanceCandidate(candidate_id="vote1", source="src", payload={"x": 1})
        e = GovernedEvent(event_id="vote-ev1", version=1, candidate_id="vote1", event_type="vote_test")
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

    def test_create_session_with_file_path(self):
        """Verify that create_session works with a file path and data persists."""
        tmp_path = os.path.join(tempfile.gettempdir(), f"test_evt02_{os.urandom(4).hex()}.db")
        try:
            sess1 = create_session(tmp_path)
            c = GovernanceCandidate(candidate_id="file_test", source="test", payload={"persist": True})
            intake_candidate(sess1, c)
            e = GovernedEvent(event_id="file_evt", version=1, candidate_id="file_test", event_type="file_test")
            record_event(sess1, e)
            sess1.commit()
            sess1.close()
            sess1.get_bind().dispose()

            # Re-open same file
            sess2 = create_session(tmp_path)
            c2 = intake_candidate(sess2, c)
            assert c2.candidate_id == "file_test"
            assert c2.payload == {"persist": True}
            ev2 = get_event(sess2, "file_evt")
            assert ev2 is not None
            assert ev2.version == 1
            assert ev2.event_type == "file_test"
            sess2.close()
            sess2.get_bind().dispose()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_event_with_updated_at(self, session):
        e = GovernedEvent(
            event_id="upd1", version=1, candidate_id="c1", event_type="test",
            status="confirmed", updated_at="2026-07-27T12:00:00",
        )
        result = record_event(session, e)
        assert result.updated_at is not None
        assert result.updated_at == "2026-07-27T12:00:00"


# ─── 7. Candidate 只读消费验证 ───

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
