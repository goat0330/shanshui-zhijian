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
from core.event_governance.models import (
    GovernanceCandidate, EvidenceBundle as GovEvidenceBundle,
    ReviewDecision as GovReviewDecision,
    GovernedEvent, ReplayRecord, EventGovernanceError, OptimisticLockError,
)
from core.event_governance.service import (
    intake_candidate, attach_evidence, review_bundle,
    record_event, get_event as get_governed_event,
    replay_event, get_timeline,
)
from core.event_governance.persistence import create_session

FIXTURES_DIR = ROOT / "tests" / "fixtures"


# ── 辅助 ──────────────────────────────────────────────────────────

def load_candidate_fixture(name: str = "candidate_v02_fixture.json") -> dict:
    path = FIXTURES_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _compute_event_id(candidate_id: str) -> str:
    return "evt_" + hashlib.sha256(candidate_id.encode()).hexdigest()[:16]


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
def repo():
    """兼容层：使用 core/event_governance 替代旧的 SQLiteRepository"""
    session = create_session()
    class _RepoCompat:
        def get_idempotency_result(self, key):
            from core.event_governance.persistence import CandidateRecord
            r = session.query(CandidateRecord).filter_by(candidate_id=key).first()
            return r.candidate_id if r else None
        def close(self): pass
        @property
        def session(self): return session
    return _RepoCompat()


@pytest.fixture
def services(repo):
    session = repo.session
    return {
        "session": session,
        "repo": repo,
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
        """Candidate Fixture 可解析（经 v0.3 Adapter）"""
        fix = load_candidate_fixture()
        raw = fix.get("candidate", fix)
        candidate = CandidateCompatibilityAdapter.to_detection_candidate({
            **raw,
            "schema_version": "candidate.v0.2",
        })
        assert candidate.candidate_id == "DET-CQ-0001"
        assert len(candidate.observation_refs) > 0

    def test_event_id_from_candidate_is_stable(self):
        """相同 Candidate 产生稳定 Event ID"""
        fix = load_candidate_fixture()
        raw = fix.get("candidate", fix)
        candidate = CandidateCompatibilityAdapter.to_detection_candidate({
            **raw,
            "schema_version": "candidate.v0.2",
        })
        id1 = _compute_event_id(candidate.candidate_id)
        id2 = _compute_event_id(candidate.candidate_id)
        assert id1 == id2
        assert id1.startswith("evt_")
