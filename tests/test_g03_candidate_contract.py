"""
G0.3-A: DetectionCandidate Contract Freeze — 14 TDD scenarios.

Red → Green → Refactor 循环：
1. 写测试 → 运行确认失败 → 实现 → 运行确认通过 → 提交
"""

import pytest
from pydantic import ValidationError


# ── Helper: minimal candidate factory ───────────────────────────────

def _make_minimal_candidate(**overrides) -> "DetectionCandidate":
    from core.schemas.contracts.candidate import (
        DetectionCandidate, TemporalExtent,
    )
    kwargs = dict(
        candidate_id=overrides.pop("candidate_id", "a" * 64),
        candidate_track_id=overrides.pop("candidate_track_id", "b" * 64),
        observation_refs=overrides.pop("observation_refs", ["obs-1"]),
        temporal_extent=overrides.pop("temporal_extent",
                                      TemporalExtent(start_index=0, end_index=1)),
        candidate_type=overrides.pop("candidate_type", "water_gain"),
        score=overrides.pop("score", 0.5),
        rule_version=overrides.pop("rule_version", "r1"),
        **overrides,
    )
    return DetectionCandidate(**kwargs)


def _make_minimal_envelope(**overrides) -> "CandidateDeliveryEnvelope":
    from core.schemas.contracts.candidate_envelope import CandidateDeliveryEnvelope
    kwargs = dict(
        run_id=overrides.pop("run_id", "run-001"),
        scene_index=overrides.pop("scene_index", 0),
        total_candidates=overrides.pop("total_candidates", 0),
        candidates=overrides.pop("candidates", ()),
    )
    return CandidateDeliveryEnvelope(**kwargs)


# ════════════════════════════════════════════════════════════════════
# Task 1: Enums + TemporalExtent + schema_version Literal
# ════════════════════════════════════════════════════════════════════

class TestEnums:
    def test_score_type_within_run_ranking_only(self):
        from core.schemas.contracts.candidate import ScoreType
        assert ScoreType.WITHIN_RUN_RANKING.value == "within_run_ranking"
        # Should only have one value
        values = [e.value for e in ScoreType]
        assert values == ["within_run_ranking"]

    def test_lifecycle_values(self):
        from core.schemas.contracts.candidate import CandidateLifecycle
        assert CandidateLifecycle.PROPOSED.value == "proposed"
        assert CandidateLifecycle.SUPPRESSED.value == "suppressed"
        assert CandidateLifecycle.SUPERSEDED.value == "superseded"

    def test_candidate_status_values(self):
        from core.schemas.contracts.candidate import CandidateStatus
        assert CandidateStatus.PERSISTENT.value == "persistent"
        assert CandidateStatus.TRANSIENT.value == "transient"
        assert CandidateStatus.UNCERTAIN.value == "uncertain"


class TestTemporalExtent:
    def test_valid(self):
        from core.schemas.contracts.candidate import TemporalExtent
        te = TemporalExtent(
            start_index=0, end_index=5,
            start_time="2024-01-01T00:00:00Z",
            end_time="2024-06-01T00:00:00Z",
        )
        assert te.start_index == 0
        assert te.end_index == 5
        assert te.start_time == "2024-01-01T00:00:00Z"

    def test_index_cross_validation(self):
        from core.schemas.contracts.candidate import TemporalExtent
        with pytest.raises(ValidationError, match="end_index"):
            TemporalExtent(start_index=5, end_index=0)

    def test_minimal(self):
        from core.schemas.contracts.candidate import TemporalExtent
        te = TemporalExtent(start_index=0, end_index=1)
        assert te.start_time is None
        assert te.end_time is None
