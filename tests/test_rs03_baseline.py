"""
RS-03 — Perception→Candidate 行为基线

记录当前 Obs→Candidate 链的确定行为，防止无意退化。

基线范围:
1. Observation 字段完整性
2. PerceptionResult→Observation 双向引用
3. Observation→Candidate 映射规则
4. Idempotency / 多次运行 consistency
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from pydantic import ValidationError

from core.schemas.contracts import (
    ExecutionStatus, TaskType, ObservationType, ScoreType, AssetRole, Modality,
)
from core.schemas.contracts.task import (
    InferenceTask, TaskSpec, RunContext, TaskAssetBinding, InputSlotSpec,
)
from core.schemas.contracts.perception import Observation, PerceptionResult, QualityReport
from core.schemas.contracts.candidate import DetectionCandidate, EvidenceRef


class TestObservationBaseline:
    """Obs 最小契约基线"""

    def test_observation_minimal(self):
        """最小 Obs 应通过"""
        obs = Observation(
            observation_id="obs-001",
            perception_result_ref="pr-001",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
            label="change_candidate",
            score=0.85,
            score_type=ScoreType.RULE_BASED,
        )
        assert obs.observation_id == "obs-001"
        assert obs.schema_version == "rs-contract.v0.3"

    def test_observation_full(self):
        """完整 Obs 应通过"""
        obs = Observation(
            observation_id="obs-002",
            track_id="track-water-gain-001",
            perception_result_ref="pr-002",
            source_asset_refs=["s1_t1", "s1_t2"],
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.CHANGE_POLYGON,
            label="sar_water_extent_change",
            score=0.92,
            score_type=ScoreType.RULE_BASED,
            geometry={"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]},
            geometry_crs="EPSG:4326",
            bbox=[106.5, 29.5, 106.6, 29.6],
            temporal={"start": "2024-06", "end": "2025-01"},
            quality={"area_m2": 5000, "change_type": "water_gain"},
            model_run_ref="run-001",
            coordinate_space="geographic",
            created_at="2026-07-27T00:00:00Z",
        )
        assert obs.track_id == "track-water-gain-001"
        assert obs.bbox == [106.5, 29.5, 106.6, 29.6]

    def test_observation_required_fields(self):
        """必需字段缺失应拒绝"""
        with pytest.raises(ValidationError):
            Observation(
                observation_id="",
                perception_result_ref="",
                source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
                observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
                label="",
                score=-0.1,
                score_type=ScoreType.RULE_BASED,
            )

    def test_observation_score_bounds(self):
        """score 必须在 [0,1]"""
        with pytest.raises(ValidationError):
            Observation(
                observation_id="obs-bad", perception_result_ref="pr",
                source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
                observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
                label="x", score=1.5, score_type=ScoreType.RULE_BASED,
            )

    def test_coordinate_space_validation(self):
        """coordinate_space 必须是 geographic/pixel/unknown"""
        with pytest.raises(ValidationError):
            Observation(
                observation_id="obs-cs", perception_result_ref="pr",
                source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
                observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
                label="x", score=0.5, score_type=ScoreType.RULE_BASED,
                coordinate_space="utm",
            )

    def test_bbox_length(self):
        """bbox 必须恰好 4 个元素"""
        with pytest.raises(ValidationError):
            Observation(
                observation_id="obs-bbox", perception_result_ref="pr",
                source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
                observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
                label="x", score=0.5, score_type=ScoreType.RULE_BASED,
                bbox=[1, 2, 3],
            )


class TestPerceptionResultBaseline:
    """PerceptionResult 契约基线"""

    def test_minimal_result(self):
        """最小 PerceptionResult"""
        pr = PerceptionResult(
            perception_result_id="pr-001",
            inference_task_ref="task-001",
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            run_id="run-001",
            status=ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
        )
        assert pr.schema_version == "rs-contract.v0.3"
        assert pr.observations == []
        assert pr.artifact_refs == []

    def test_with_observations(self):
        """携带 Obs 的 PerceptionResult"""
        obs = Observation(
            observation_id="obs-001",
            perception_result_ref="pr-002",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.WATER_EXTENT,
            label="water_body",
            score=0.75,
            score_type=ScoreType.RULE_BASED,
        )
        pr = PerceptionResult(
            perception_result_id="pr-002",
            inference_task_ref="task-002",
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            run_id="run-001",
            status=ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
            observations=[obs],
            artifact_refs=["mask-001", "cand-001"],
            quality_report=QualityReport(
                valid_pixel_ratio=0.95,
                recommendations=["ok"],
            ),
        )
        assert len(pr.observations) == 1
        assert pr.observations[0].observation_id == "obs-001"
        assert pr.artifact_refs == ["mask-001", "cand-001"]

    def test_result_obs_ref_consistency(self):
        """Observation 的 perception_result_ref 必须匹配父 PerceptionResult"""
        obs = Observation(
            observation_id="obs-ref",
            perception_result_ref="pr-parent",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
            label="x", score=0.5, score_type=ScoreType.RULE_BASED,
        )
        pr = PerceptionResult(
            perception_result_id="pr-parent",
            inference_task_ref="task-ref",
            task_spec_ref="v1@1.0.0",
            run_id="run-ref",
            status=ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
            observations=[obs],
        )
        for o in pr.observations:
            assert o.perception_result_ref == pr.perception_result_id

    def test_succeeded_empty(self):
        """无观测时的状态"""
        pr = PerceptionResult(
            perception_result_id="pr-empty",
            inference_task_ref="task-empty",
            task_spec_ref="v1@1.0.0",
            run_id="run-empty",
            status=ExecutionStatus.SUCCEEDED_EMPTY,
        )
        assert pr.status == ExecutionStatus.SUCCEEDED_EMPTY

    def test_failed(self):
        """失败状态"""
        pr = PerceptionResult(
            perception_result_id="pr-fail",
            inference_task_ref="task-fail",
            task_spec_ref="v1@1.0.0",
            run_id="run-fail",
            status=ExecutionStatus.FAILED,
            diagnostics={"stage": "read", "error_type": "FileNotFoundError"},
        )
        assert pr.status == ExecutionStatus.FAILED
        assert "stage" in pr.diagnostics


class TestObservationToCandidateBaseline:
    """Observation→Candidate 行为基线"""

    def test_single_obs_to_candidate(self):
        """单 Obs 可产生 Candidate"""
        obs = Observation(
            observation_id="obs-to-cand",
            perception_result_ref="pr-tc",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.CHANGE_POLYGON,
            label="water_gain",
            score=0.85, score_type=ScoreType.RULE_BASED,
            geometry={"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]},
        )
        cand = DetectionCandidate(
            candidate_id="cand-from-obs",
            observation_refs=[obs.observation_id],
            temporal_extent={"start": "2024-06", "end": "2025-01"},
            candidate_type="water_extent_change",
            score=obs.score,
            rule_version="v1.0",
            geometry=obs.geometry,
        )
        assert obs.observation_id in cand.observation_refs
        assert cand.schema_version == "rs-contract.v0.3"
        assert cand.score == 0.85

    def test_multi_obs_to_candidate(self):
        """多 Obs 聚合为一个 Candidate"""
        obs1 = Observation(
            observation_id="obs-multi-1", perception_result_ref="pr-m",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
            label="water_gain", score=0.8, score_type=ScoreType.RULE_BASED,
        )
        obs2 = Observation(
            observation_id="obs-multi-2", perception_result_ref="pr-m",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.OPTICAL_WATER_INDEX_SUPPORT,
            label="water_gain_support", score=0.9, score_type=ScoreType.RULE_BASED,
        )
        cand = DetectionCandidate(
            candidate_id="cand-multi",
            observation_refs=[obs1.observation_id, obs2.observation_id],
            temporal_extent={"start": "2024-06", "end": "2025-01"},
            candidate_type="water_extent_change",
            score=min(obs1.score, obs2.score),
            rule_version="v1.0",
        )
        assert len(cand.observation_refs) == 2
        assert cand.score == 0.8  # min ensemble

    def test_candidate_with_evidence(self):
        """Candidate 可引用 EvidenceRef"""
        ev = EvidenceRef(
            evidence_id="ev-change-mask",
            source_asset_ref="s1_t1",
            evidence_type="change_mask",
        )
        cand = DetectionCandidate(
            candidate_id="cand-ev",
            observation_refs=["obs-ev"],
            temporal_extent={"start": "2024-06", "end": "2025-01"},
            candidate_type="water_extent_change",
            score=0.75, rule_version="v1.0",
            evidence_refs=[ev.evidence_id],
        )
        assert ev.evidence_id in cand.evidence_refs

    def test_candidate_minimal(self):
        """最小 Candidate 契约"""
        cand = DetectionCandidate(
            candidate_id="cand-min",
            observation_refs=["obs-min"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="unknown",
            score=0.0,
            rule_version="v0.1",
        )
        assert cand.candidate_id == "cand-min"
        assert cand.candidate_type == "unknown"

    def test_candidate_empty_obs_refs_rejected(self):
        """空的 observation_refs 应拒绝"""
        with pytest.raises(ValidationError):
            DetectionCandidate(
                candidate_id="cand-empty",
                observation_refs=[],
                temporal_extent={"start": "2026-01", "end": "2026-06"},
                candidate_type="water_extent_change",
                score=0.5,
                rule_version="v1.0",
            )

    def test_candidate_score_bounds(self):
        """Candidate score 必须在 [0,1]"""
        with pytest.raises(ValidationError):
            DetectionCandidate(
                candidate_id="cand-bad",
                observation_refs=["obs-x"],
                temporal_extent={"start": "2026-01", "end": "2026-06"},
                candidate_type="water_extent_change",
                score=1.5,
                rule_version="v1.0",
            )

    def test_evidence_ref_minimal(self):
        """最小 EvidenceRef"""
        ev = EvidenceRef(
            evidence_id="ev-min",
            source_asset_ref="asset-001",
            evidence_type="sar_vh",
        )
        assert ev.evidence_id == "ev-min"
        assert ev.schema_version == "rs-contract.v0.3"

    def test_evidence_ref_empty_id_rejected(self):
        """空 evidence_id 应拒绝"""
        with pytest.raises(ValidationError):
            EvidenceRef(
                evidence_id="",
                source_asset_ref="asset-001",
                evidence_type="sar_vh",
            )

    def test_evidence_ref_full(self):
        """完整 EvidenceRef"""
        ev = EvidenceRef(
            evidence_id="ev-full",
            source_asset_ref="s1_t1",
            derived_asset_ref="s1_t1_change_mask",
            evidence_type="change_mask",
            spatial_window={"x": 0, "y": 0, "width": 100, "height": 100},
            temporal_window={"start": "2024-06", "end": "2025-01"},
            description="VH change mask from multi-temporal detector",
            provenance={"tool": "SarTemporalChangeTool", "version": "1.0.0"},
        )
        assert ev.derived_asset_ref == "s1_t1_change_mask"
        assert ev.provenance["tool"] == "SarTemporalChangeTool"


class TestIdempotencyBaseline:
    """幂等性基线"""

    def test_same_input_same_obs_structure(self):
        """相同输入产生相同结构 (确定性)"""
        obs1 = Observation(
            observation_id="obs-idem",
            perception_result_ref="pr-idem",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.CHANGE_POLYGON,
            label="water_gain",
            score=0.75, score_type=ScoreType.RULE_BASED,
            geometry={"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]},
        )
        obs2 = Observation(
            observation_id="obs-idem",
            perception_result_ref="pr-idem",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.CHANGE_POLYGON,
            label="water_gain",
            score=0.75, score_type=ScoreType.RULE_BASED,
            geometry={"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]},
        )
        assert obs1.model_dump() == obs2.model_dump()

    def test_candidate_id_reproducible(self):
        """相同条件产生相同 candidate_id"""
        cand1 = DetectionCandidate(
            candidate_id="cand-repro",
            observation_refs=["obs-x"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            score=0.5, rule_version="v1.0",
        )
        cand2 = DetectionCandidate(
            candidate_id="cand-repro",
            observation_refs=["obs-x"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            score=0.5, rule_version="v1.0",
        )
        assert cand1.candidate_id == cand2.candidate_id
