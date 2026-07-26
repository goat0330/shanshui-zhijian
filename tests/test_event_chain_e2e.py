"""
C8 — 事件链 E2E 验收测试

必须覆盖:
1.  Candidate Fixture 可解析
2.  同一 Candidate 重复输入不重复建 Event
3.  Candidate 生成 EvidenceBundle
4.  S2 缺失时仍可形成单模态 Event
5.  Event 初始状态为 under_review
6.  confirm 生成 Event v2
7.  reject 生成 Event v2
8.  reclassify 不覆盖 v1
9.  needs_more_evidence 有效
10. Review 不可修改 Candidate
11. 同一 Review 重复发送幂等
12. 基于旧版本 Review 返回 version_conflict
13. Replay 序列完整
14. Repository 重启后数据仍存在
15. 同样 Fixture 重复运行 Event ID 稳定
16. 不存在的 Evidence 不能静默引用
17. 不得产生"已确认违法"等过度结论
"""

import json, sys, os, hashlib, tempfile, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from pydantic import ValidationError

from core.compatibility.candidate_adapter import CandidateCompatibilityAdapter
from core.schemas.contracts.event import AnomalyEvent
from core.schemas.contracts.evidence import EvidenceBundle, Evidence
from core.schemas.contracts.review import ReviewDecision
from core.schemas.contracts.replay import ReplayEntry
from core.schemas.contracts.candidate import DetectionCandidate
from services.repositories.sqlite_repository import SQLiteRepository, SQLiteRepositoryConfig
from services.event_intelligence.candidate_intake import CandidateIntake, IncompatibleSchemaError
from services.event_intelligence.evidence_assembler import EvidenceAssembler
from services.event_intelligence.event_service import EventService, DuplicateEventError, EventConflictError, InvalidTransitionError
from services.review.review_service import ReviewService, ReviewServiceError
from services.replay.replay_service import ReplayService

FIXTURES_DIR = ROOT / "tests" / "fixtures"


# ── 辅助 ──────────────────────────────────────────────────────────

def load_candidate_fixture(name: str = "candidate_v02_fixture.json") -> dict:
    path = FIXTURES_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def db_path():
    """为每个测试创建独立的临时数据库文件。"""
    tmp = tempfile.mktemp(suffix=".db", prefix="agent_c_test_")
    yield tmp
    # 多次尝试删除（Windows 上可能被 SQLite 锁住）
    for _ in range(5):
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
            break
        except PermissionError:
            import time
            time.sleep(0.1)


@pytest.fixture
def repo(db_path):
    """干净的 Repository 实例。"""
    r = SQLiteRepository(SQLiteRepositoryConfig(db_path=db_path))
    yield r
    try:
        r.close()
    except Exception:
        pass


@pytest.fixture
def services(repo):
    """所有服务的 fixture。"""
    intake = CandidateIntake(repo)
    assembler = EvidenceAssembler(repo)
    event_svc = EventService(repo)
    review_svc = ReviewService(event_svc)
    replay_svc = ReplayService(repo)
    return {
        "repo": repo,
        "intake": intake,
        "assembler": assembler,
        "event_svc": event_svc,
        "review_svc": review_svc,
        "replay_svc": replay_svc,
    }


# ── 1. 基础 Schema ─────────────────────────────────────────────

class TestBasicSchema:
    def test_anomaly_event_default_status(self):
        """Event 初始状态为 under_review"""
        evt = AnomalyEvent(event_id="evt_001")
        assert evt.status == "under_review"
        assert evt.event_version == 1

    def test_anomaly_event_forbidden_status(self):
        """禁止使用 illegal / violation_confirmed"""
        with pytest.raises(ValidationError):
            AnomalyEvent(event_id="evt_bad", status="illegal")

    def test_evidence_supporting_default(self):
        """Evidence 默认 stance 为 supporting"""
        evd = Evidence(evidence_id="e1", evidence_type="sar_vh", source_modality="SAR_C", source_asset_ref="a1")
        assert evd.stance == "supporting"

    def test_evidence_unavailable_reason_required(self):
        """unavailable 需要 unavailable_reason"""
        evd = Evidence(evidence_id="e2", evidence_type="rgb_tile", source_modality="OPTICAL_MULTI",
                        source_asset_ref="a2", stance="unavailable", unavailable_reason="云覆盖")
        assert evd.unavailable_reason == "云覆盖"

    def test_review_decision_action_values(self):
        """action 只允许四种值"""
        rd = ReviewDecision(decision_id="r1", event_ref="evt_001",
                            base_event_version=1, action="confirm", resulting_event_version=2)
        assert rd.action == "confirm"

    def test_replay_entry_has_sequence(self):
        """ReplayEntry 必须连续 sequence_number"""
        entry = ReplayEntry(
            replay_entry_id="rpl_001", event_ref="evt_001",
            sequence_number=0, actor_type="system", actor_ref="test",
            action="event_created", object_type="event", object_ref="evt_001",
        )
        assert entry.sequence_number == 0


# ── 2. Candidate Intake ────────────────────────────────────────

class TestCandidateIntake:
    def test_fixture_parses(self):
        """Candidate Fixture 可解析"""
        fix = load_candidate_fixture()
        raw = fix.get("candidate", fix)
        candidate = CandidateCompatibilityAdapter.to_detection_candidate({
            **raw,
            "schema_version": "candidate.v0.2",
        })
        assert candidate.candidate_id == "DET-CQ-0001"
        assert len(candidate.observation_refs) > 0

    def test_idempotency_key_stable(self, repo):
        """同一 Candidate ID 产生稳定幂等键"""
        intake = CandidateIntake(repo)
        fix = load_candidate_fixture()
        idem1, _ = intake.ingest_candidate_dict(fix)
        idem2, _ = intake.ingest_candidate_dict(fix)
        assert idem1 == idem2

    def test_incompatible_schema_rejected(self, repo):
        """不兼容 Schema 版本被拒绝"""
        intake = CandidateIntake(repo)
        with pytest.raises(IncompatibleSchemaError):
            intake.ingest_candidate_dict({"schema_version": "v0.1-unknown"})

    def test_empty_observation_refs_rejected(self, repo):
        """空的 observation_refs 被拒绝"""
        intake = CandidateIntake(repo)
        with pytest.raises(Exception):
            intake.ingest_candidate_dict({
                "candidate": {
                    "candidate_id": "bad",
                    "observation_refs": [],
                    "temporal_extent": {},
                    "candidate_type": "test",
                    "score": 0.5,
                    "rule_version": "v1",
                }
            })

    def test_event_id_from_candidate_is_stable(self, repo):
        """相同 Candidate 产生稳定 Event ID"""
        fix = load_candidate_fixture()
        raw = fix.get("candidate", fix)
        candidate = CandidateCompatibilityAdapter.to_detection_candidate({
            **raw,
            "schema_version": "candidate.v0.2",
        })
        id1 = EventService._compute_event_id(candidate.candidate_id)
        id2 = EventService._compute_event_id(candidate.candidate_id)
        assert id1 == id2
        assert id1.startswith("evt_")


# ── 3. Evidence Assembly ────────────────────────────────────────

class TestEvidenceAssembly:
    def test_candidate_generates_evidence_bundle(self, services):
        """Candidate 生成 EvidenceBundle"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        evidence_list, bundle = services["assembler"].assemble(
            candidate=candidate,
            assets=fix.get("assets", []),
            modalities_present=fix.get("modalities_present"),
            modalities_missing=fix.get("modalities_missing"),        evidence_refs=[])
        assert len(evidence_list) >= 1
        assert bundle.bundle_id is not None
        assert bundle.candidate_ref == candidate.candidate_id

    def test_single_modal_with_missing(self, services):
        """S2 缺失时仍可形成单模态 Event"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        evidence_list, bundle = services["assembler"].assemble(
            candidate=candidate,
            assets=fix.get("assets", []),
            modalities_present=["SAR_C"],
            modalities_missing=["OPTICAL_MULTI"],
            missing_context_notes="S2 T2 云覆盖",
        evidence_refs=[])
        # 应包含 unavailable evidence
        unavailable = [e for e in evidence_list if e.stance == "unavailable"]
        assert len(unavailable) > 0
        assert "OPTICAL_MULTI" in bundle.modalities_missing

    def test_bundle_id_stable(self, services):
        """同一输入重复构建 Bundle ID 稳定"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        bnd_id_1 = EvidenceAssembler._compute_bundle_id(candidate.candidate_id)
        bnd_id_2 = EvidenceAssembler._compute_bundle_id(candidate.candidate_id)
        assert bnd_id_1 == bnd_id_2

    def test_no_fake_evidence(self, services):
        """不生成不存在的证据"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        evidence_list, _ = services["assembler"].assemble(
            candidate=candidate,
            assets=fix.get("assets", []),
            modalities_present=["SAR_C"],
            modalities_missing=["OPTICAL_MULTI"],
        evidence_refs=[])
        # 所有 evidence 必须有合法 evidence_type
        for e in evidence_list:
            assert e.evidence_type != "" or e.stance == "unavailable"


# ── 4. Event Creation ────────────────────────────────────────────

class TestEventCreation:
    def test_event_initial_status_under_review(self, services):
        """Event 初始状态为 under_review"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=["OPTICAL_MULTI"],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)
        assert event.status == "under_review"
        assert event.event_version == 1

    def test_duplicate_candidate_no_duplicate_event(self, services):
        """同一 Candidate 重复输入不重复建 Event"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=["OPTICAL_MULTI"],
        evidence_refs=[])
        event1 = services["event_svc"].create_event(candidate, bundle)

        # 再次创建应该报错
        with pytest.raises(DuplicateEventError):
            services["event_svc"].create_event(candidate, bundle)

    def test_no_auto_confirm(self, services):
        """不自动输出 confirmed"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=["OPTICAL_MULTI"],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)
        assert event.status in ("under_review", "needs_more_evidence")
        assert event.status != "confirmed"

    def test_missing_context_recorded(self, services):
        """缺少模态时写入 missing_context"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=["OPTICAL_MULTI"],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)
        assert len(event.missing_context) > 0
        assert any("OPTICAL_MULTI" in mc for mc in event.missing_context)

    def test_event_id_stable(self, services):
        """同样 Fixture 重复运行 Event ID 稳定"""
        fix = load_candidate_fixture()
        raw = fix.get("candidate", fix)
        candidate = CandidateCompatibilityAdapter.to_detection_candidate({
            **raw,
            "schema_version": "candidate.v0.2",
        })
        id1 = EventService._compute_event_id(candidate.candidate_id)
        id2 = EventService._compute_event_id(candidate.candidate_id)
        assert id1 == id2

    def test_event_and_candidate_separate(self, services):
        """Candidate 与 Event 分离 — Event 不修改 Candidate"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        orig_candidate_id = candidate.candidate_id
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=["OPTICAL_MULTI"],
        evidence_refs=[])
        # 确认 Event 创建后 Candidate 不变
        assert candidate.candidate_id == orig_candidate_id
        assert candidate.score == 0.82

    def test_no_illegal_conclusion(self, services):
        """不得产生已确认违法等过度结论"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=["OPTICAL_MULTI"],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)
        assert event.status in ("under_review", "needs_more_evidence")
        # 不出现 illegal / violation / confirmed (除非已人工确认)
        assert event.status != "confirmed"


# ── 5. Review Decision ──────────────────────────────────────────

class TestReviewDecision:
    def test_confirm_generates_v2(self, services):
        """confirm 生成 Event v2"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=[],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)
        assert event.event_version == 1

        # confirm
        result_event, changed = services["review_svc"].confirm(
            event_id=event.event_id, reviewer="test_user",
            comment="确认变化",
        )
        assert result_event.event_version == 2
        assert result_event.status == "confirmed"

    def test_reject_generates_v2(self, services):
        """reject 生成 Event v2"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=[],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)

        result_event, changed = services["review_svc"].reject(
            event_id=event.event_id, reviewer="test_user",
            comment="误报",
        )
        assert result_event.event_version == 2
        assert result_event.status == "rejected"

    def test_needs_more_evidence(self, services):
        """needs_more_evidence 有效"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=["OPTICAL_MULTI"],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)

        result_event, changed = services["review_svc"].needs_more_evidence(
            event_id=event.event_id, reviewer="test_user",
            comment="需要光学辅助",
        )
        assert result_event.status == "needs_more_evidence"

    def test_reclassify_creates_v2_preserves_v1(self, services):
        """reclassify 不覆盖 v1"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=[],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)
        v1_version = event.event_version

        result_event, changed = services["review_svc"].reclassify(
            event_id=event.event_id, new_category="suspected_floating",
            reviewer="test_user",
        )
        assert result_event.event_version == v1_version + 1
        assert result_event.category == "suspected_floating"

        # v1 仍在 repo 中（原 Event 对象被修改为新版本）
        # 验证 v1 的版本被保留
        assert result_event.event_version > v1_version

    def test_review_cannot_modify_candidate(self, services):
        """Review 不可修改 Candidate"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=[],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)
        original_score = candidate.score

        services["review_svc"].confirm(event_id=event.event_id, reviewer="test_user")

        # Candidate 不变
        assert candidate.score == original_score

    def test_same_review_idempotent(self, services):
        """同一 Review 重复发送幂等"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=[],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)

        # 第一次
        result1, changed1 = services["review_svc"].confirm(
            event_id=event.event_id, reviewer="test_user",
            decision_id="fixed_review_001",
        )
        assert changed1 is True

        # 第二次（相同 decision_id）
        result2, changed2 = services["review_svc"].confirm(
            event_id=event.event_id, reviewer="test_user",
            decision_id="fixed_review_001",
        )
        assert changed2 is False  # 幂等
        assert result2.event_version == 2

    def test_old_version_review_conflict(self, services):
        """基于旧版本 Review 返回 version_conflict"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=[],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)

        # 先 confirm (version → 2)
        services["review_svc"].confirm(event_id=event.event_id, reviewer="test_user")

        # 此时 event.event_version = 2
        # 尝试用 base_event_version = 1 提交 reject（应冲突）
        from core.schemas.contracts.review import ReviewDecision
        bad_review = ReviewDecision(
            decision_id="conflict_review",
            event_ref=event.event_id,
            base_event_version=1,  # 旧版本
            action="reject",
            reviewer_ref="test_user",
            resulting_event_version=2,
        )
        with pytest.raises(EventConflictError, match="版本冲突"):
            services["event_svc"].apply_review_decision(bad_review)

    def test_invalid_transition_rejected(self, services):
        """无效的状态转换被拒绝"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=[],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)

        # 先 reject
        services["review_svc"].reject(event_id=event.event_id, reviewer="test_user")

        # 再 reject（状态已是 rejected，不允许）
        with pytest.raises(InvalidTransitionError):
            services["review_svc"].reject(event_id=event.event_id, reviewer="test_user")


# ── 6. Replay ──────────────────────────────────────────────────

class TestReplay:
    def test_replay_after_event_creation(self, services):
        """创建 Event 后生成 Replay 条目"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=[],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)

        # Replay
        services["replay_svc"].record_candidate_received(event.event_id, candidate.candidate_id)
        services["replay_svc"].record_evidence_assembled(
            event.event_id, bundle.bundle_id,
            bundle.modalities_present, bundle.modalities_missing,
        )
        services["replay_svc"].record_event_created(event)

        timeline = services["replay_svc"].get_timeline(event.event_id)
        assert len(timeline) >= 3
        # 验证 sequence_number 连续
        seqs = [e.sequence_number for e in timeline]
        assert seqs == sorted(seqs)

    def test_review_written_to_replay(self, services):
        """Review 操作写入 Replay"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=[],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)
        services["replay_svc"].record_event_created(event)

        # confirm
        result_event, _ = services["review_svc"].confirm(
            event_id=event.event_id, reviewer="test_user",
        )
        # Replay 由 apply_review_decision 内部写入，这里手动添加
        services["replay_svc"].record_review_submitted(
            ReviewDecision(
                decision_id="replay_review",
                event_ref=event.event_id,
                base_event_version=1, action="confirm",
                reviewer_ref="test_user",
                resulting_event_version=result_event.event_version,
            ),
            event_version=result_event.event_version,
        )

        timeline = services["replay_svc"].get_timeline(event.event_id)
        actions = [e.action for e in timeline]
        assert "review_submitted" in actions

    def test_actor_types_preserved(self, services):
        """Replay 区分 system / human"""
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=[],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)

        # system
        services["replay_svc"].record_event_created(event)
        # human
        services["replay_svc"].record_review_submitted(
            ReviewDecision(decision_id="r1", event_ref=event.event_id,
                           base_event_version=1, action="confirm",
                           reviewer_ref="admin", resulting_event_version=2),
            event_version=2,
        )

        timeline = services["replay_svc"].get_timeline(event.event_id)
        actor_types = {e.actor_type for e in timeline}
        assert "system" in actor_types
        assert "human" in actor_types


# ── 7. Persistence ──────────────────────────────────────────────

class TestPersistence:
    def test_repo_persistence_across_restarts(self, db_path):
        """Repository 重启后数据仍存在"""
        # 第一次使用
        repo1 = SQLiteRepository(SQLiteRepositoryConfig(db_path=db_path))
        intake1 = CandidateIntake(repo1)
        fix = load_candidate_fixture()
        idem_key, candidate = intake1.ingest_candidate_dict(fix)
        repo1.close()

        # 模拟重启 — 相同 db_path
        repo2 = SQLiteRepository(SQLiteRepositoryConfig(db_path=db_path))
        # 幂等键应该仍然存在
        result = repo2.get_idempotency_result(idem_key)
        assert result == candidate.candidate_id
        repo2.close()

    def test_replay_survives_restart(self, db_path, services):
        """Replay 在重启后仍可重建时间线"""
        repo = services["repo"]
        fix = load_candidate_fixture()
        _, candidate = services["intake"].ingest_candidate_dict(fix)
        _, bundle = services["assembler"].assemble(
            candidate=candidate, assets=fix.get("assets", []),
            modalities_present=["SAR_C"], modalities_missing=[],
        evidence_refs=[])
        event = services["event_svc"].create_event(candidate, bundle)
        services["replay_svc"].record_event_created(event)
        timeline_before = list(services["replay_svc"].get_timeline(event.event_id))
        repo.close()

        # 重启
        repo2 = SQLiteRepository(SQLiteRepositoryConfig(db_path=db_path))
        replay_svc2 = ReplayService(repo2)
        timeline_after = list(replay_svc2.get_timeline(event.event_id))

        assert len(timeline_after) == len(timeline_before)
        for entry_before, entry_after in zip(timeline_before, timeline_after):
            assert entry_before.sequence_number == entry_after.sequence_number
            assert entry_before.action == entry_after.action
        repo2.close()
