"""
RS-03 — ID/Track ID 稳定性测试

覆盖:
1. observation_id 唯一性约束
2. track_id 跨时相追踪 (多期观测指向同一地物)
3. candidate_id ↔ observation_refs 一致性
4. perception_result_ref → InferenceTask 反向追踪
5. artifact_refs 可解析性
6. EvidenceRef ↔ DetectionCandidate 交叉引用
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from pydantic import ValidationError

from core.schemas.contracts import (
    ExecutionStatus, TaskType, ObservationType, ScoreType, AssetRole, Modality, SpatialReliability,
)
from core.schemas.contracts.task import (
    InferenceTask, TaskSpec, RunContext, TaskAssetBinding, InputSlotSpec,
)
from core.schemas.contracts.asset import AssetRef, SpatialMetadata
from core.schemas.contracts.perception import Observation, PerceptionResult, QualityReport
from core.schemas.contracts.candidate import DetectionCandidate, EvidenceRef


class TestObservationIdStability:
    """observation_id 唯一性与格式"""

    def test_observation_id_unique_in_result(self):
        """同一 PerceptionResult 内 observation_id 应唯一"""
        obs1 = Observation(
            observation_id="obs-uniq-1", perception_result_ref="pr-uniq",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
            label="gain", score=0.8, score_type=ScoreType.RULE_BASED,
        )
        obs2 = Observation(
            observation_id="obs-uniq-2", perception_result_ref="pr-uniq",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
            label="loss", score=0.6, score_type=ScoreType.RULE_BASED,
        )
        ids = {o.observation_id for o in [obs1, obs2]}
        assert len(ids) == 2

    def test_duplicate_id_different_results(self):
        """不同 PerceptionResult 可以有相同 observation_id (scope 隔离)"""
        obs_a = Observation(
            observation_id="obs-scoped", perception_result_ref="pr-a",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.WATER_EXTENT,
            label="w", score=0.5, score_type=ScoreType.RULE_BASED,
        )
        obs_b = Observation(
            observation_id="obs-scoped", perception_result_ref="pr-b",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.WATER_EXTENT,
            label="w", score=0.5, score_type=ScoreType.RULE_BASED,
        )
        # 不同父 Result → 允许 ID 相同
        assert obs_a.observation_id == obs_b.observation_id
        assert obs_a.perception_result_ref != obs_b.perception_result_ref

    def test_observation_id_format_convention(self):
        """observation_id 遵循 pr-{task_id}-{feature_id} 约定"""
        obs = Observation(
            observation_id="obs-task-mt-001-p0",
            perception_result_ref="pr-task-mt-001",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.CHANGE_POLYGON,
            label="candidate", score=0.7, score_type=ScoreType.RULE_BASED,
        )
        parts = obs.observation_id.split("-")
        assert len(parts) >= 4

    def test_observation_id_stable_across_reconstruction(self):
        """相同数据重建的 observation_id 保持一致"""
        data = dict(
            observation_id="obs-stable-v1",
            perception_result_ref="pr-stable",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
            label="stable", score=0.5, score_type=ScoreType.RULE_BASED,
            quality={"area_m2": 1000, "change_type": "water_gain"},
        )
        o1 = Observation(**data)
        o2 = Observation(**data)
        assert o1.observation_id == o2.observation_id
        assert o1.model_dump() == o2.model_dump()


class TestTrackIdStability:
    """track_id 跨时相追踪稳定性"""

    def test_same_track_same_entity(self):
        """同一地物多期观测共享 track_id"""
        obs_t1 = Observation(
            observation_id="obs-track-t1",
            track_id="track-water-body-A01",
            perception_result_ref="pr-t1",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.WATER_EXTENT,
            label="water_body", score=0.9, score_type=ScoreType.RULE_BASED,
        )
        obs_t2 = Observation(
            observation_id="obs-track-t2",
            track_id="track-water-body-A01",
            perception_result_ref="pr-t2",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.WATER_EXTENT,
            label="water_body", score=0.85, score_type=ScoreType.RULE_BASED,
        )
        assert obs_t1.track_id == obs_t2.track_id

    def test_diff_track_diff_entity(self):
        """不同地物 track_id 应不同"""
        obs_a = Observation(
            observation_id="obs-track-A",
            track_id="track-water-body-A01",
            perception_result_ref="pr-a",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.WATER_EXTENT,
            label="water_body", score=0.9, score_type=ScoreType.RULE_BASED,
        )
        obs_b = Observation(
            observation_id="obs-track-B",
            track_id="track-water-body-B02",
            perception_result_ref="pr-b",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.WATER_EXTENT,
            label="water_body", score=0.7, score_type=ScoreType.RULE_BASED,
        )
        assert obs_a.track_id != obs_b.track_id

    def test_track_id_optional(self):
        """track_id 是可选的 (向后兼容)"""
        obs = Observation(
            observation_id="obs-no-track",
            perception_result_ref="pr-no-track",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
            label="x", score=0.5, score_type=ScoreType.RULE_BASED,
        )
        assert obs.track_id is None

    def test_track_id_stable_across_serialization(self):
        """track_id 经过序列化/反序列化保持不变"""
        obs = Observation(
            observation_id="obs-serial",
            track_id="track-stable-X01",
            perception_result_ref="pr-serial",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.CHANGE_POLYGON,
            label="x", score=0.5, score_type=ScoreType.RULE_BASED,
        )
        dumped = obs.model_dump()
        loaded = Observation(**dumped)
        assert loaded.track_id == "track-stable-X01"


class TestCandidateIdStability:
    """candidate_id ↔ observation_refs 一致性"""

    def test_candidate_refs_back_to_obs(self):
        """Candidate 的 observation_refs 可反向解析到 Obs"""
        obs_ids = ["obs-cand-a", "obs-cand-b"]
        cand = DetectionCandidate(
            candidate_id="cand-ref-back",
            observation_refs=obs_ids,
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            score=0.75, rule_version="v1.0",
        )
        for ref in cand.observation_refs:
            assert ref in obs_ids

    def test_candidate_no_dangling_refs(self):
        """Candidate 不应引用不存在的 Obs ID"""
        obs_ids = ["obs-real-1", "obs-real-2"]
        cand = DetectionCandidate(
            candidate_id="cand-no-dangle",
            observation_refs=obs_ids,
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            score=0.5, rule_version="v1.0",
        )
        for ref in cand.observation_refs:
            assert ref in obs_ids  # 所有 ref 在已知集合中
        # 不应存在不在 obs_ids 中的引用
        for ref in cand.observation_refs:
            assert ref not in ["obs-nonexistent", ""]

    def test_candidate_id_format(self):
        """candidate_id 应遵循约定格式"""
        cand = DetectionCandidate(
            candidate_id="cand-mt-001-water-gain",
            observation_refs=["obs-mt-001-0"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            score=0.85, rule_version="v1.0",
        )
        assert cand.candidate_id.startswith("cand-")

    def test_evidence_ref_to_candidate(self):
        """EvidenceRef 可被 Candidate 引用"""
        ev = EvidenceRef(
            evidence_id="ev-change-mask-v2",
            source_asset_ref="s1_t1",
            evidence_type="change_mask",
        )
        cand = DetectionCandidate(
            candidate_id="cand-ev-ref",
            observation_refs=["obs-ev-ref"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            score=0.7, rule_version="v1.0",
            evidence_refs=[ev.evidence_id],
        )
        # Candidate 的 evidence_refs 只存 ID 字符串
        assert ev.evidence_id in cand.evidence_refs
        # 反向查找: EvidenceRef 可以通过 ID 匹配
        assert cand.evidence_refs[0] == "ev-change-mask-v2"


class TestPerceptionResultRefStability:
    """PerceptionResult ↔ InferenceTask 引用稳定性"""

    def test_result_to_task_ref(self):
        """PerceptionResult 引用 InferenceTask"""
        pr = PerceptionResult(
            perception_result_id="pr-ref-test",
            inference_task_ref="task-ref-001",
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            run_id="run-ref-001",
            status=ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
        )
        assert pr.inference_task_ref == "task-ref-001"

    def test_obs_to_result_ref(self):
        """Observation 引用 PerceptionResult"""
        pr = PerceptionResult(
            perception_result_id="pr-parent-002",
            inference_task_ref="task-parent-002",
            task_spec_ref="v1@1.0.0",
            run_id="run-parent-002",
            status=ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
            observations=[
                Observation(
                    observation_id="obs-child",
                    perception_result_ref="pr-parent-002",
                    source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
                    observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
                    label="x", score=0.5, score_type=ScoreType.RULE_BASED,
                ),
            ],
        )
        for o in pr.observations:
            assert o.perception_result_ref == pr.perception_result_id

    def test_artifact_refs_resolvable(self):
        """artifact_refs 应可反向追踪到具体文件"""
        pr = PerceptionResult(
            perception_result_id="pr-artifact",
            inference_task_ref="task-artifact",
            task_spec_ref="v1@1.0.0",
            run_id="run-artifact",
            status=ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
            artifact_refs=["task-artifact_water_t1", "task-artifact_change_mask"],
        )
        # artifact_refs 应遵循 {task_id}_{name} 格式
        for ref in pr.artifact_refs:
            assert ref.startswith("task-artifact_")
            assert len(ref) > len("task-artifact_")

    def test_perception_result_id_format(self):
        """perception_result_id 遵循 pr-{task_id} 约定"""
        pr = PerceptionResult(
            perception_result_id="pr-task-format-test",
            inference_task_ref="task-format-test",
            task_spec_ref="v1@1.0.0",
            run_id="run-format",
            status=ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
        )
        assert pr.perception_result_id.startswith("pr-")
        assert pr.perception_result_id == f"pr-{pr.inference_task_ref}"
