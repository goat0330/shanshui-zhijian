"""
RS-03 — Candidate 合同冻结 v0.3

验收标准:
1. 所有合同版本号统一为 v0.3
2. DetectionCandidate + EvidenceRef 带 schema_version
3. Observation 带 track_id (可选)
4. PerceptionResult 输出结构完整
5. JSON Schema 稳定导出
6. 新旧版本兼容 (v0.3 读旧数据不崩溃)
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
from core.schemas.contracts.prediction import (
    PredictionRecord, ChangePrediction,
)


# ── Test 1: 版本号统一 ──────────────────────────────────────────

class TestVersionUniformity:
    """所有合同版本号统一为 v0.3"""

    def test_observation_schema_version(self):
        obs = Observation(
            observation_id="obs-v", perception_result_ref="pr-v",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
            label="x", score=0.5, score_type=ScoreType.RULE_BASED,
        )
        assert obs.schema_version == "rs-contract.v0.3"

    def test_perception_result_schema_version(self):
        pr = PerceptionResult(
            perception_result_id="pr-v", inference_task_ref="task-v",
            task_spec_ref="v1@1.0.0", run_id="run-v",
            status=ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
        )
        assert pr.schema_version == "rs-contract.v0.3"

    def test_detection_candidate_schema_version(self):
        cand = DetectionCandidate(
            candidate_id="cand-v",
            observation_refs=["obs-v"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            score=0.5, rule_version="v1.0",
        )
        assert cand.schema_version == "rs-contract.v0.3"

    def test_evidence_ref_schema_version(self):
        ev = EvidenceRef(
            evidence_id="ev-v", source_asset_ref="asset-v",
            evidence_type="change_mask",
        )
        assert ev.schema_version == "rs-contract.v0.3"

    def test_task_spec_schema_version(self):
        ts = TaskSpec(
            task_spec_id="ts-v", version="1.0.0",
            task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            input_slots=[InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR])],
        )
        assert ts.schema_version == "rs-contract.v0.3"

    def test_inference_task_schema_version(self):
        it = InferenceTask(
            task_id="it-v", sample_id="s", task_order=0,
            task_spec_ref="v1@1.0.0",
            asset_bindings=[TaskAssetBinding(asset_ref="a", role=AssetRole.BEFORE)],
        )
        assert it.schema_version == "rs-contract.v0.3"

    def test_run_context_schema_version(self):
        rc = RunContext(run_id="rc-v")
        assert rc.schema_version == "rs-contract.v0.3"

    def test_prediction_record_schema_version(self):
        pr = PredictionRecord(
            record_id="pr-v", inference_task_ref="task-v",
            execution_status="succeeded_with_observations",
            payload=ChangePrediction(change_pixels=100),
        )
        assert pr.schema_version == "rs-contract.v0.3"


# ── Test 2: v0.3 模式向后兼容 ──────────────────────────────────

class TestBackwardCompatibility:
    """v0.3 可以读旧版本 (v0.2) 数据"""

    def test_read_v02_observation(self):
        """旧版 v0.2 Observation 数据可以被 v0.3 模式解析"""
        v02_data = {
            "schema_version": "rs-contract.v0.2",
            "observation_id": "obs-old",
            "perception_result_ref": "pr-old",
            "source_task_type": "temporal_change_detection",
            "observation_type": "sar_backscatter_change",
            "label": "old_candidate",
            "score": 0.75,
            "score_type": "rule_based",
        }
        # 不应抛出 ValidationError
        obs = Observation(**v02_data)
        assert obs.observation_id == "obs-old"
        # track_id 在旧数据中不存在，应为 None
        assert obs.track_id is None
        # 版本自动升级到最新
        assert obs.schema_version == "rs-contract.v0.2"

    def test_read_v02_perception_result(self):
        """旧版 v0.2 PerceptionResult 可读"""
        v02_data = {
            "schema_version": "rs-contract.v0.2",
            "perception_result_id": "pr-old",
            "inference_task_ref": "task-old",
            "task_spec_ref": "v1@1.0.0",
            "run_id": "run-old",
            "status": "succeeded_empty",
        }
        pr = PerceptionResult(**v02_data)
        assert pr.status == ExecutionStatus.SUCCEEDED_EMPTY

    def test_old_task_spec_still_works(self):
        """旧 v0.2 TaskSpec 仍可解析"""
        v02_data = {
            "schema_version": "rs-contract.v0.2",
            "task_spec_id": "old-spec", "version": "1.0.0",
            "task_type": "temporal_change_detection",
            "input_slots": [{"role": "before", "modalities": ["sar"], "min_items": 1, "max_items": 1}],
        }
        ts = TaskSpec(**v02_data)
        assert ts.task_spec_id == "old-spec"

    def test_create_candidate_without_schema_version(self):
        """不传 schema_version 时使用默认值 v0.3"""
        # 用户代码可以不传 schema_version
        cand = DetectionCandidate(
            candidate_id="cand-auto",
            observation_refs=["obs-auto"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            score=0.5,
            rule_version="v1.0",
        )
        assert cand.schema_version == "rs-contract.v0.3"


# ── Test 3: JSON Schema 稳定导出 ────────────────────────────────

class TestJsonSchemaStability:
    """JSON Schema 稳定导出"""

    def test_observation_schema(self):
        schema = Observation.model_json_schema()
        assert "properties" in schema
        props = schema["properties"]
        assert "observation_id" in props
        assert "track_id" in props
        assert "perception_result_ref" in props
        assert "geometry_crs" in props

    def test_perception_result_schema(self):
        schema = PerceptionResult.model_json_schema()
        assert "properties" in schema
        assert "observations" in schema["properties"]
        assert "quality_report" in schema["properties"]

    def test_detection_candidate_schema(self):
        schema = DetectionCandidate.model_json_schema()
        assert "properties" in schema
        assert "candidate_id" in schema["properties"]
        assert "observation_refs" in schema["properties"]
        assert "evidence_refs" in schema["properties"]
        assert "schema_version" in schema["properties"]
        assert schema["properties"]["schema_version"]["default"] == "rs-contract.v0.3"

    def test_evidence_ref_schema(self):
        schema = EvidenceRef.model_json_schema()
        assert "properties" in schema
        assert "evidence_id" in schema["properties"]
        assert "schema_version" in schema["properties"]

    def test_prediction_record_schema(self):
        schema = PredictionRecord.model_json_schema()
        assert "properties" in schema
        assert "record_id" in schema["properties"]
        assert "payload" in schema["properties"]


# ── Test 4: 合同字段完整性 ──────────────────────────────────────

class TestContractFieldCompleteness:
    """v0.3 合同字段完整性"""

    def test_observation_has_all_v03_fields(self):
        """Observation v0.3 拥有全部必需字段"""
        obs = Observation(
            observation_id="obs-full",
            track_id="track-full",
            perception_result_ref="pr-full",
            source_asset_refs=["a1"],
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.CHANGE_POLYGON,
            label="full",
            score=0.85,
            score_type=ScoreType.RULE_BASED,
            geometry={"type": "Point", "coordinates": [0, 0]},
            geometry_crs="EPSG:4326",
            bbox=[106.5, 29.5, 106.6, 29.6],
            temporal={"start": "2024-06", "end": "2025-01"},
            quality={"area_m2": 5000},
            model_run_ref="run-full",
            coordinate_space="geographic",
            created_at="2026-07-27T00:00:00Z",
        )
        assert obs.track_id is not None
        assert obs.bbox is not None
        assert obs.quality is not None

    def test_candidate_has_all_v03_fields(self):
        """DetectionCandidate v0.3 拥有全部必需字段"""
        cand = DetectionCandidate(
            candidate_id="cand-full",
            observation_refs=["obs-full"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            geometry={"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]},
            score=0.85,
            quality_summary={"mean_score": 0.85, "n_observations": 3},
            evidence_refs=["ev-001", "ev-002"],
            rule_version="v1.0",
        )
        assert cand.candidate_id == "cand-full"
        assert len(cand.evidence_refs) == 2
        assert cand.quality_summary.mean_score == 0.85

    def test_evidence_ref_has_all_v03_fields(self):
        """EvidenceRef v0.3 拥有全部可选字段"""
        ev = EvidenceRef(
            evidence_id="ev-complete",
            source_asset_ref="source-001",
            derived_asset_ref="derived-001",
            evidence_type="change_mask",
            spatial_window={"x": 0, "y": 0, "width": 256, "height": 256},
            temporal_window={"start": "2026-01", "end": "2026-06"},
            description="Change mask from VV/VH threshold",
            provenance={"algorithm": "otsu", "threshold": -15.0},
        )
        assert ev.derived_asset_ref == "derived-001"
        assert ev.description is not None
        assert ev.provenance["algorithm"] == "otsu"


# ── Test 5: 版本号格式校验 ──────────────────────────────────────

class TestVersionFormat:
    """schema_version 格式校验"""

    def test_valid_version_format(self):
        """schema_version 必须匹配 rs-contract.v 模式"""
        obs = Observation(
            observation_id="obs-vfmt", perception_result_ref="pr",
            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
            observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
            label="x", score=0.5, score_type=ScoreType.RULE_BASED,
        )
        import re
        assert re.match(r"^rs-contract\.v[\d.]+$", obs.schema_version)

    def test_bad_version_format(self):
        """无效版本格式被拒绝"""
        with pytest.raises(ValidationError):
            Observation(
                observation_id="obs-badv",
                schema_version="v0.3",
                perception_result_ref="pr",
                source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
                observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
                label="x", score=0.5, score_type=ScoreType.RULE_BASED,
            )

    def test_inference_task_bad_version(self):
        with pytest.raises(ValidationError):
            InferenceTask(
                task_id="t", sample_id="s", task_order=0,
                task_spec_ref="v1", schema_version="bad-version",
                asset_bindings=[TaskAssetBinding(asset_ref="a", role=AssetRole.BEFORE)],
            )
