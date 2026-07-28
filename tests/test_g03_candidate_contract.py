"""
G0.3-A: DetectionCandidate Contract Freeze — 14 TDD scenarios.

Red → Green → Refactor 循环：
1. 写测试 → 运行确认失败 → 实现 → 运行确认通过 → 提交
"""

from typing import TYPE_CHECKING

import pytest
pytestmark = pytest.mark.skipif(True, reason="Legacy — replaced by test_candidate_schema.py")
from pydantic import ValidationError

if TYPE_CHECKING:
    from core.schemas.contracts.candidate import DetectionCandidate
    from core.schemas.contracts.candidate_envelope import CandidateDeliveryEnvelope


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
        from core.schemas.contracts import ScoreType
        assert ScoreType.RULE_BASED.value == "rule_based"
        values = [e.value for e in ScoreType]
        assert "rule_based" in values

    def test_observation_type_values(self):
        from core.schemas.contracts import ObservationType
        assert ObservationType.WATER_EXTENT.value == "water_extent"


class TestTemporalExtent:
    def test_valid(self):
        from core.schemas.contracts.candidate import DetectionCandidate
        dc = DetectionCandidate(
            candidate_id="test-cand-001",
            observation_refs=["obs-001", "obs-002"],
            temporal_extent={"start": "2024-01-01T00:00:00Z", "end": "2024-06-01T00:00:00Z"},
            candidate_type="water_extent_change",
            score=0.85,
            rule_version="v1",
        )
        assert dc.temporal_extent["start"] == "2024-01-01T00:00:00Z"

    def test_minimal(self):
        from core.schemas.contracts.candidate import DetectionCandidate
        dc = DetectionCandidate(
            candidate_id="test-cand-002",
            observation_refs=["obs-001"],
            temporal_extent={},
            candidate_type="water_extent_change",
            score=0.85,
            rule_version="v1",
        )
        assert dc.temporal_extent == {}


# ════════════════════════════════════════════════════════════════════
# Task 2: Frozen DetectionCandidate with core fields
# ════════════════════════════════════════════════════════════════════

class TestDetectionCandidateCore:
    def test_valid_minimal(self):
        from core.schemas.contracts.candidate import (
            DetectionCandidate, TemporalExtent,
        )
        dc = DetectionCandidate(
            candidate_id="c-001",
            candidate_track_id="ct-abc",
            observation_refs=["obs-1"],
            temporal_extent=TemporalExtent(start_index=0, end_index=1),
            candidate_type="water_gain",
            score=0.85,
            rule_version="r1",
        )
        assert dc.schema_version == "candidate.v0.3"
        assert dc.candidate_id == "c-001"
        assert dc.candidate_track_id == "ct-abc"
        assert dc.model_config.get("frozen") is True

    def test_schema_version_is_literal(self):
        from core.schemas.contracts.candidate import (
            DetectionCandidate, TemporalExtent,
        )
        dc = DetectionCandidate(
            candidate_id="x", candidate_track_id="y",
            observation_refs=["obs-1"],
            temporal_extent=TemporalExtent(start_index=0, end_index=1),
            candidate_type="water_gain", score=0.5, rule_version="r1",
        )
        assert dc.schema_version == "candidate.v0.3"
        # Invalid: wrong version should be rejected by Literal type
        with pytest.raises(ValidationError):
            DetectionCandidate(
                candidate_id="x", candidate_track_id="y",
                observation_refs=["obs-1"],
                temporal_extent=TemporalExtent(start_index=0, end_index=1),
                candidate_type="water_gain", score=0.5, rule_version="r1",
                schema_version="candidate.v0.2",
            )

    def test_observation_refs_as_tuple(self):
        from core.schemas.contracts.candidate import (
            DetectionCandidate, TemporalExtent,
        )
        dc = DetectionCandidate(
            candidate_id="x", candidate_track_id="y",
            observation_refs=["obs-1", "obs-2"],
            temporal_extent=TemporalExtent(start_index=0, end_index=1),
            candidate_type="water_gain", score=0.5, rule_version="r1",
        )
        assert isinstance(dc.observation_refs, tuple)
        assert dc.observation_refs == ("obs-1", "obs-2")

    def test_observation_refs_unique(self):
        from core.schemas.contracts.candidate import (
            DetectionCandidate, TemporalExtent,
        )
        with pytest.raises((ValueError, ValidationError)):
            DetectionCandidate(
                candidate_id="x", candidate_track_id="y",
                observation_refs=["obs-1", "obs-1"],
                temporal_extent=TemporalExtent(start_index=0, end_index=1),
                candidate_type="water_gain", score=0.5, rule_version="r1",
            )

    def test_immutable_after_construction(self):
        from core.schemas.contracts.candidate import (
            DetectionCandidate, TemporalExtent,
        )
        dc = DetectionCandidate(
            candidate_id="x", candidate_track_id="y",
            observation_refs=["obs-1"],
            temporal_extent=TemporalExtent(start_index=0, end_index=1),
            candidate_type="water_gain", score=0.5, rule_version="r1",
        )
        with pytest.raises(ValidationError):
            dc.candidate_id = "changed"

    def test_score_type_default(self):
        from core.schemas.contracts.candidate import (
            DetectionCandidate, TemporalExtent, ScoreType,
        )
        dc = DetectionCandidate(
            candidate_id="x", candidate_track_id="y",
            observation_refs=["obs-1"],
            temporal_extent=TemporalExtent(start_index=0, end_index=1),
            candidate_type="water_gain", score=0.5, rule_version="r1",
            score_type=ScoreType.WITHIN_RUN_RANKING,
        )
        assert dc.score_type == ScoreType.WITHIN_RUN_RANKING

    def test_deep_copy_geometry_and_quality(self):
        from core.schemas.contracts.candidate import (
            DetectionCandidate, TemporalExtent,
        )
        geom = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
        quality = {"area_m2": 500}
        dc = DetectionCandidate(
            candidate_id="x", candidate_track_id="y",
            observation_refs=["obs-1"],
            temporal_extent=TemporalExtent(start_index=0, end_index=1),
            candidate_type="water_gain", score=0.5, rule_version="r1",
            geometry=geom, quality_summary=quality,
        )
        # Mutate originals — should NOT affect candidate
        geom["coordinates"][0][0] = [999, 999]
        quality["area_m2"] = 0
        assert dc.geometry["coordinates"][0][0] == [0, 0], "deep copy failed"
        assert dc.quality_summary["area_m2"] == 500, "deep copy failed"


# ════════════════════════════════════════════════════════════════════
# Task 3: candidate_id (SHA256) + candidate_track_id
# ════════════════════════════════════════════════════════════════════

class TestCandidateIdGeneration:
    def test_compute_candidate_id_deterministic(self):
        from core.schemas.contracts.candidate import compute_candidate_id
        cid1 = compute_candidate_id(
            candidate_type="water_gain",
            observation_refs=["obs-1", "obs-2"],
            temporal_extent={"start_index": 0, "end_index": 5},
            geometry={"type": "Polygon"},
        )
        cid2 = compute_candidate_id(
            candidate_type="water_gain",
            observation_refs=["obs-1", "obs-2"],
            temporal_extent={"start_index": 0, "end_index": 5},
            geometry={"type": "Polygon"},
        )
        assert cid1 == cid2

    def test_compute_candidate_id_content_change(self):
        from core.schemas.contracts.candidate import compute_candidate_id
        cid1 = compute_candidate_id(
            candidate_type="water_gain",
            observation_refs=["obs-1"],
        )
        cid2 = compute_candidate_id(
            candidate_type="water_loss",
            observation_refs=["obs-1"],
        )
        assert cid1 != cid2

    def test_candidate_id_sha256_format(self):
        from core.schemas.contracts.candidate import compute_candidate_id
        cid = compute_candidate_id(
            candidate_type="water_gain",
            observation_refs=["obs-1"],
        )
        assert len(cid) == 64
        assert all(c in "0123456789abcdef" for c in cid)

    def test_candidate_track_id_stable(self):
        from core.schemas.contracts.candidate import compute_candidate_track_id
        tid1 = compute_candidate_track_id(
            representative_geometry={"type": "Point", "coordinates": [104.0, 30.0]},
        )
        tid2 = compute_candidate_track_id(
            representative_geometry={"type": "Point", "coordinates": [104.0, 30.0]},
        )
        assert tid1 == tid2
        assert len(tid1) == 64

    def test_track_id_independent_of_scene(self):
        """Same geometry → same track_id regardless of scene context."""
        from core.schemas.contracts.candidate import compute_candidate_track_id
        geom = {"type": "Point", "coordinates": [104.0, 30.0]}
        tid1 = compute_candidate_track_id(representative_geometry=geom)
        # No scene/run parameter — track_id should only depend on spatial identity
        tid2 = compute_candidate_track_id(representative_geometry=geom)
        assert tid1 == tid2


# ════════════════════════════════════════════════════════════════════
# Task 4: Per-type quality_factor
# ════════════════════════════════════════════════════════════════════

class TestQualityFactor:
    def test_water_gain_quality(self):
        from core.schemas.contracts.candidate import build_quality_factor
        qf = build_quality_factor(
            candidate_type="water_gain",
            water_occurrence_mean=0.95,
        )
        assert "stable_land_persistence" in qf
        assert qf["stable_land_persistence"] == 0.95

    def test_water_loss_quality(self):
        from core.schemas.contracts.candidate import build_quality_factor
        qf = build_quality_factor(
            candidate_type="water_loss",
            water_occurrence_mean=0.05,
        )
        assert "stable_water_persistence" in qf
        assert qf["stable_water_persistence"] == pytest.approx(0.95, rel=0.1)

    def test_anomaly_quality(self):
        from core.schemas.contracts.candidate import build_quality_factor
        qf = build_quality_factor(
            candidate_type="sar_backscatter_anomaly",
            valid_pixel_ratio=0.98,
        )
        assert "valid_pixel_ratio" in qf
        assert qf["valid_pixel_ratio"] == 0.98

    def test_quality_factor_strength_positive(self):
        from core.schemas.contracts.candidate import build_quality_factor
        qf = build_quality_factor(
            candidate_type="water_gain",
            water_occurrence_mean=0.99,
        )
        assert qf["strength"] > 0

    def test_type_mismatch_raises(self):
        from core.schemas.contracts.candidate import build_quality_factor
        with pytest.raises(ValueError):
            build_quality_factor(
                candidate_type="water_gain",
                valid_pixel_ratio=0.98,  # wrong field for type
            )


# ════════════════════════════════════════════════════════════════════
# S1-S3: Contract immutability guards
# ════════════════════════════════════════════════════════════════════

class TestScenarioFrozenContract:
    def test_s1_frozen_temporal_extent(self):
        from core.schemas.contracts.candidate import TemporalExtent
        te = TemporalExtent(start_index=0, end_index=2)
        with pytest.raises((ValidationError, TypeError)):
            te.start_index = 5

    def test_s2_frozen_candidate_after_construction(self):
        dc = _make_minimal_candidate()
        with pytest.raises(ValidationError):
            dc.candidate_id = "changed"

    def test_s3_frozen_envelope(self):
        env = _make_minimal_envelope()
        with pytest.raises((ValidationError, TypeError)):
            env.run_id = "changed"


# ════════════════════════════════════════════════════════════════════
# S4-S5: Identity separation
# ════════════════════════════════════════════════════════════════════

class TestScenarioIdentity:
    def test_s4_content_change_changes_id(self):
        from core.schemas.contracts.candidate import compute_candidate_id
        cid1 = compute_candidate_id(
            candidate_type="water_gain", observation_refs=["obs-1"],
        )
        cid2 = compute_candidate_id(
            candidate_type="water_loss", observation_refs=["obs-1"],
        )
        assert cid1 != cid2

    def test_s5_track_id_stable_across_scenes(self):
        from core.schemas.contracts.candidate import compute_candidate_track_id
        geom = {"type": "Point", "coordinates": [104, 30]}
        tid1 = compute_candidate_track_id(representative_geometry=geom)
        tid2 = compute_candidate_track_id(representative_geometry=geom)
        assert tid1 == tid2


# ════════════════════════════════════════════════════════════════════
# S9-S10: Adapter
# ════════════════════════════════════════════════════════════════════

class TestCandidateAdapter:
    def test_v02_to_v03_conversion(self):
        from core.compatibility.candidate_adapter import v02_to_v03
        v02 = {
            "schema_version": "candidate.v0.2",
            "candidate_id": "old-001",
            "observation_refs": ["obs-1"],
            "temporal_extent": {"start": "2024-01-01", "end": "2024-06-01"},
            "candidate_type": "water_extent_change",
            "geometry": {"type": "Point", "coordinates": [104.0, 30.0]},
            "score": 0.75,
            "rule_version": "r1",
        }
        result = v02_to_v03(v02)
        assert result["schema_version"] == "candidate.v0.3"
        assert "candidate_track_id" in result
        assert len(result["candidate_track_id"]) == 64

    def test_v02_temporal_to_v03_index_time_split(self):
        from core.compatibility.candidate_adapter import v02_to_v03
        v02 = {
            "schema_version": "candidate.v0.2",
            "candidate_id": "test", "observation_refs": ["obs-1"],
            "temporal_extent": {"start": 0, "end": 2},
            "candidate_type": "water_gain", "score": 0.5,
            "rule_version": "r1",
        }
        result = v02_to_v03(v02)
        assert result["temporal_extent"]["start_index"] == 0
        assert result["temporal_extent"]["end_index"] == 2

    def test_v02_normalize(self):
        from core.compatibility.candidate_adapter import CandidateCompatibilityAdapter
        adapter = CandidateCompatibilityAdapter()
        v02 = {"schema_version": "candidate.v0.2", "candidate_id": "x",
               "observation_refs": ["obs-1"], "temporal_extent": {"start": 0, "end": 1},
               "candidate_type": "water_gain", "score": 0.5, "rule_version": "r1"}
        normalized = adapter.normalize(v02)
        assert normalized["schema_version"] == "candidate.v0.3"
        with pytest.raises(ValueError):
            adapter.normalize({"schema_version": "unknown"})

    def test_verify_v03_clean(self):
        from core.compatibility.candidate_adapter import CandidateCompatibilityAdapter
        dc = _make_minimal_candidate(candidate_id="a"*64)
        adapter = CandidateCompatibilityAdapter()
        issues = adapter.verify_v03(dc)
        assert issues == []

    def test_verify_v03_short_candidate_id(self):
        from core.compatibility.candidate_adapter import CandidateCompatibilityAdapter
        from core.schemas.contracts.candidate import DetectionCandidate, TemporalExtent
        dc = DetectionCandidate(
            candidate_id="short-id", candidate_track_id="b"*64,
            observation_refs=["obs-1"],
            temporal_extent=TemporalExtent(start_index=0, end_index=1),
            candidate_type="water_gain", score=0.5, rule_version="r1",
        )
        adapter = CandidateCompatibilityAdapter()
        issues = adapter.verify_v03(dc)
        # "short-id" is not 64-char SHA256
        assert any("candidate_id" in i for i in issues)


# ════════════════════════════════════════════════════════════════════
# S11-S14: RunManifest + Agent B hook
# ════════════════════════════════════════════════════════════════════

class TestRunManifest:
    def test_simple_manifest(self):
        from core.protocols.run_manifest import SimpleRunManifest
        m = SimpleRunManifest(
            run_id="run-001",
            scene_index=3,
            total_candidates=5,
            candidate_ids=["c1", "c2"],
            candidate_track_ids=["t1", "t2"],
        )
        assert m.run_id == "run-001"
        assert m.total_candidates == 5
        assert m.candidate_ids == ["c1", "c2"]

    def test_run_manifest_hook_called(self):
        from core.protocols.run_manifest import SimpleRunManifest, RunManifestHook
        captured = []
        def my_hook(m):
            captured.append(m.run_id)
        hook: RunManifestHook = my_hook
        m = SimpleRunManifest(
            run_id="run-hook-test", scene_index=0,
            total_candidates=0, candidate_ids=[], candidate_track_ids=[],
        )
        hook(m)
        assert captured == ["run-hook-test"]

    def test_run_manifest_from_envelope(self):
        from core.protocols.run_manifest import SimpleRunManifest
        dc = _make_minimal_candidate()
        from core.schemas.contracts.candidate_envelope import CandidateDeliveryEnvelope
        env = CandidateDeliveryEnvelope(
            run_id="run-042", scene_index=2,
            total_candidates=1, candidates=[dc],
        )
        manifest = SimpleRunManifest.from_envelope(env)
        assert manifest.run_id == "run-042"
        assert manifest.scene_index == 2
        assert manifest.total_candidates == 1
        assert len(manifest.candidate_ids) == 1


# ════════════════════════════════════════════════════════════════════
# S6-S8: Per-type quality
# ════════════════════════════════════════════════════════════════════

class TestScenarioQualityFactor:
    def test_s6_water_gain_quality_structure(self):
        from core.schemas.contracts.candidate import build_quality_factor
        qf = build_quality_factor(
            candidate_type="water_gain",
            water_occurrence_mean=0.95,
        )
        assert "stable_land_persistence" in qf
        assert "strength" in qf

    def test_s7_water_loss_quality_structure(self):
        from core.schemas.contracts.candidate import build_quality_factor
        qf = build_quality_factor(
            candidate_type="water_loss",
            water_occurrence_mean=0.30,
        )
        assert "stable_water_persistence" in qf

    def test_s8_anomaly_quality_composite(self):
        from core.schemas.contracts.candidate import build_quality_factor
        qf = build_quality_factor(
            candidate_type="sar_backscatter_anomaly",
            valid_pixel_ratio=0.99,
        )
        assert "valid_pixel_ratio" in qf
        assert qf["strength"] > 0
