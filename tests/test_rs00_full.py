"""
RS-00 A2-A7 综合验收测试

覆盖: 所有新契约 + Fixture + Adapter + Exporter + Validator + 兼容适配 + TaskDrivenRunner
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from pydantic import ValidationError

from core.schemas.contracts import Modality, AssetRole, ExecutionStatus, TaskType, ObservationType
from core.schemas.contracts.asset import AssetRef, SpatialMetadata
from core.schemas.contracts.task import (
    TaskAssetBinding, InputSlotSpec, TaskSpec, InferenceTask, RunContext,
)
from core.schemas.contracts.perception import Observation, QualityReport, PerceptionResult
from core.schemas.contracts.prediction import (
    PredictionRecord, ChangePrediction, ClassificationPrediction,
    DetectionPrediction, SegmentationPrediction, AnomalyScorePrediction,
)
from core.schemas.contracts.candidate import DetectionCandidate, EvidenceRef
from competition.adapters.competition_input_adapter import CompetitionInputAdapter
from competition.mappers.competition_mapper import CompetitionMapper
from competition.exporters.competition_exporter import CompetitionExporter, SubmissionBundle
from competition.validators.validator import SubmissionValidator
from core.compatibility.detection_result_adapter import DetectionResultAdapter

FIXTURES_DIR = ROOT / "competition" / "fixtures"


# ── A2: DetectionCandidate + EvidenceRef + PredictionRecord 测试 ──

class TestA2Contracts:
    def test_evidence_ref(self):
        er = EvidenceRef(evidence_id="evd-001", source_asset_ref="s1_t1", evidence_type="sar_vh")
        assert er.evidence_id == "evd-001"

    def test_evidence_ref_empty_id(self):
        with pytest.raises(ValidationError):
            EvidenceRef(evidence_id="", source_asset_ref="x", evidence_type="y")

    def test_detection_candidate(self):
        dc = DetectionCandidate(
            candidate_id="cand-001",
            observation_refs=["obs-001", "obs-002"],
            temporal_extent={"start": "2026-05", "end": "2026-06"},
            candidate_type="water_extent_change",
            score=0.85,
            rule_version="v1.0",
        )
        assert dc.candidate_id == "cand-001"

    def test_classification_prediction(self):
        cp = ClassificationPrediction(class_id=3, class_name="water", confidence=0.92)
        assert cp.prediction_type == "classification"

    def test_change_prediction(self):
        cp = ChangePrediction(change_mask_ref="mask-001", change_pixels=5084)
        assert cp.prediction_type == "change_detection"

    def test_prediction_record(self):
        pr = PredictionRecord(
            record_id="pred-cq-001",
            inference_task_ref="task-cq-001",
            execution_status="succeeded_with_observations",
            prediction_type="change_detection",
            payload={"prediction_type": "change_detection", "change_pixels": 100},
        )
        assert pr.record_id == "pred-cq-001"


# ── A3: CompetitionInputAdapter 测试 ──

class TestA3InputAdapter:
    def test_parse_whole_scene(self):
        adapter = CompetitionInputAdapter()
        manifest_path = str(FIXTURES_DIR / "whole_scene.json")
        assets, tasks = adapter.parse_manifest(manifest_path)
        assert len(assets) == 1
        assert assets[0].modality == Modality.OPTICAL
        assert len(tasks) == 1
        assert tasks[0].task_order == 0
        assert tasks[0].asset_bindings[0].role == AssetRole.CURRENT

    def test_parse_all_fixtures(self):
        adapter = CompetitionInputAdapter()
        for name in ["whole_scene.json", "png_tile.json", "t1_t2_pair.json", "multi_asset.json"]:
            manifest_path = str(FIXTURES_DIR / name)
            assets, tasks = adapter.parse_manifest(manifest_path)
            assert len(assets) >= 1
            assert len(tasks) == 1

    def test_parse_dict_manifest(self):
        adapter = CompetitionInputAdapter()
        manifest = {
            "fixture_type": "test",
            "assets": [{"asset_id": "a1", "uri": "x.tif", "media_type": "image/tiff", "modality": "optical"}],
            "inference_task": {
                "task_id": "task-001", "sample_id": "s-001", "task_order": 0,
                "task_spec_ref": "spec-v1",
                "asset_bindings": [{"asset_ref": "a1", "role": "current"}],
            },
        }
        assets, tasks = adapter.parse_manifest(manifest)
        assert len(assets) == 1
        assert tasks[0].task_id == "task-001"

    def test_missing_inference_task(self):
        adapter = CompetitionInputAdapter()
        with pytest.raises(Exception):
            adapter.parse_manifest({"assets": []})

    def test_missing_file(self):
        adapter = CompetitionInputAdapter()
        with pytest.raises(FileNotFoundError):
            adapter.parse_manifest("/nonexistent/manifest.json")

    def test_not_guess_from_filename(self):
        """验证适配器不从文件名猜测任务类型"""
        adapter = CompetitionInputAdapter()
        manifest_path = str(FIXTURES_DIR / "multi_asset.json")
        assets, tasks = adapter.parse_manifest(manifest_path)
        # 任务类型来自 manifest 中的 task_spec_ref，不是文件名
        assert tasks[0].task_spec_ref == "sar-temporal-change-v1@1.0.0"


# ── A4: CompetitionMapper + Exporter + Validator 测试 ──

class TestA4MapperExporterValidator:
    def test_mapper_empty_result(self):
        mapper = CompetitionMapper()
        task = InferenceTask(
            task_id="task-001", sample_id="s-001", task_order=0,
            task_spec_ref="spec-v1",
            asset_bindings=[TaskAssetBinding(asset_ref="a1", role=AssetRole.BEFORE)],
        )
        result = PerceptionResult(
            perception_result_id="pr-001",
            inference_task_ref="task-001",
            task_spec_ref="spec-v1",
            run_id="run-001",
            status=ExecutionStatus.SUCCEEDED_EMPTY,
        )
        pr = mapper.map_result(result, task, TaskType.TEMPORAL_CHANGE_DETECTION)
        assert pr.inference_task_ref == "task-001"
        assert pr.execution_status == "succeeded_empty"

    def test_exporter_creates_bundle(self):
        exporter = CompetitionExporter()
        pr = PredictionRecord(
            record_id="pred-001",
            inference_task_ref="task-001",
            execution_status="succeeded_with_observations",
            prediction_type="change_detection",
            payload={"prediction_type": "change_detection", "change_pixels": 100},
        )
        bundle = exporter.export([pr])
        assert bundle.schema_version == "submission.internal.v0.2"
        assert len(bundle.predictions) == 1
        assert bundle.bundle_checksum

    def test_validator_passes(self):
        validator = SubmissionValidator()
        exporter = CompetitionExporter()
        pr = PredictionRecord(
            record_id="pred-001",
            inference_task_ref="task-001",
            execution_status="succeeded_with_observations",
            prediction_type="change_detection",
            payload={"prediction_type": "change_detection", "change_pixels": 100},
        )
        bundle = exporter.export([pr])
        report = validator.validate(bundle)
        assert report.passed, f"校验失败: {report.errors}"

    def test_validator_detects_duplicate(self):
        validator = SubmissionValidator()
        pr1 = PredictionRecord(
            record_id="pred-001",
            inference_task_ref="task-001",
            execution_status="succeeded_with_observations",
            payload=ChangePrediction(change_pixels=0),
        )
        pr2 = PredictionRecord(
            record_id="pred-002",
            inference_task_ref="task-001",
            execution_status="succeeded_empty",
            payload=ChangePrediction(change_pixels=0),
        )
        bundle = SubmissionBundle(
            bundle_id="test-dup",
            predictions=[pr1, pr2],
        )
        bundle.bundle_checksum = bundle.compute_checksum()
        report = validator.validate(bundle)
        assert not report.passed
        assert any("重复" in e for e in report.errors)

    def test_validator_empty_bundle(self):
        validator = SubmissionValidator()
        exporter = CompetitionExporter()
        bundle = exporter.export([])
        report = validator.validate(bundle)
        assert report.passed  # 允许空 bundle
        assert any("没有" in w for w in report.warnings)

    def test_validator_checksum_mismatch(self):
        validator = SubmissionValidator()
        bundle = SubmissionBundle(
            bundle_id="bad-bundle",
            predictions=[],
            bundle_checksum="bad-checksum",
        )
        report = validator.validate(bundle)
        assert not report.passed


# ── A5: DetectionResultAdapter 测试 ──

class TestA5DetectionResultAdapter:
    def test_to_perception_result(self):
        adapter = DetectionResultAdapter()
        task = InferenceTask(
            task_id="task-cq-001", sample_id="cq-001", task_order=0,
            task_spec_ref="spec-v1",
            asset_bindings=[TaskAssetBinding(asset_ref="s1_t1", role=AssetRole.BEFORE)],
        )
        ctx = RunContext(run_id="run-001")
        dr_list = [
            {"detection_id": "DR-001", "category": "change", "confidence": 0.8,
             "source_assets": ["s1_t1", "s1_t2"], "observed_at": "2026-06",
             "evidence_refs": ["mask-001", "score-001"]},
        ]
        pr = adapter.to_perception_result(dr_list, task, ctx)
        assert pr.status == ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS
        assert len(pr.observations) == 1
        assert pr.observations[0].score == 0.8
        assert "mask-001" in pr.artifact_refs

    def test_to_prediction_record(self):
        adapter = DetectionResultAdapter()
        task = InferenceTask(
            task_id="task-cq-001", sample_id="cq-001", task_order=0,
            task_spec_ref="spec-v1",
            asset_bindings=[TaskAssetBinding(asset_ref="s1_t1", role=AssetRole.BEFORE)],
        )
        ctx = RunContext(run_id="run-001")
        dr_list = [
            {"detection_id": "DR-001", "category": "change", "confidence": 0.8,
             "source_assets": ["s1_t1"], "observed_at": "2026-06", "evidence_refs": ["m-001"]},
            {"detection_id": "DR-002", "category": "change", "confidence": 0.6,
             "source_assets": ["s1_t2"], "observed_at": "2026-06", "evidence_refs": ["m-002"]},
        ]
        perception_result = adapter.to_perception_result(dr_list, task, ctx)
        pr = adapter.to_prediction_record(perception_result, task)

        # 一个 InferenceTask 对应一个 PredictionRecord
        assert pr.inference_task_ref == "task-cq-001"
        assert pr.execution_status == "succeeded_with_observations"
        assert pr.payload.prediction_type == "change_detection"

    def test_empty_dr_list(self):
        adapter = DetectionResultAdapter()
        task = InferenceTask(
            task_id="task-empty", sample_id="e", task_order=0,
            task_spec_ref="spec-v1",
            asset_bindings=[TaskAssetBinding(asset_ref="a1", role=AssetRole.BEFORE)],
        )
        ctx = RunContext(run_id="run-empty")
        pr = adapter.to_perception_result([], task, ctx)
        assert pr.status == ExecutionStatus.SUCCEEDED_EMPTY


# ── A7: 回归测试 ──

class TestA7Regression:
    def test_idempotency_key(self):
        """幂等键可以设置"""
        task = InferenceTask(
            task_id="task-001", sample_id="s-001", task_order=0,
            task_spec_ref="spec-v1",
            asset_bindings=[TaskAssetBinding(asset_ref="a1", role=AssetRole.BEFORE)],
            idempotency_key="src:s1_t1:rule-v1",
        )
        assert task.idempotency_key == "src:s1_t1:rule-v1"

    def test_task_order_zero_based(self):
        """task_order 从 0 开始"""
        t0 = InferenceTask(task_id="t0", sample_id="s0", task_order=0, task_spec_ref="v1",
                            asset_bindings=[TaskAssetBinding(asset_ref="a", role=AssetRole.BEFORE)])
        t1 = InferenceTask(task_id="t1", sample_id="s1", task_order=1, task_spec_ref="v1",
                            asset_bindings=[TaskAssetBinding(asset_ref="a", role=AssetRole.BEFORE)])
        assert t0.task_order == 0
        assert t1.task_order == 1

    def test_fingerprint_computation(self):
        """TaskSpec 和 RunContext 的指纹可以手动计算"""
        ts = TaskSpec(task_spec_id="v1", version="1.0.0", task_type="temporal_change_detection",
                      input_slots=[InputSlotSpec(role=AssetRole.BEFORE, modalities=[Modality.SAR], min_items=1, max_items=1)])
        fp = ts.compute_fingerprint()
        assert len(fp) == 16

        rc = RunContext(run_id="run-001", tool_config={"threshold": 0.5}, model_version="v1")
        rfp = rc.compute_fingerprint()
        assert len(rfp) == 16

    def test_sequence_index(self):
        """多时相场景的 sequence_index"""
        b0 = TaskAssetBinding(asset_ref="s2_t1", role=AssetRole.OPTICAL_SUPPORT, sequence_index=0)
        b1 = TaskAssetBinding(asset_ref="s2_t2", role=AssetRole.OPTICAL_SUPPORT, sequence_index=1)
        assert b0.sequence_index == 0
        assert b1.sequence_index == 1

    def test_bad_modality_rejected(self):
        with pytest.raises(ValidationError):
            AssetRef(asset_id="x", uri="x.tif", media_type="image/tiff", modality="invalid_modality")

    def test_bad_role_rejected(self):
        with pytest.raises(ValidationError):
            TaskAssetBinding(asset_ref="x", role="invalid_role")

    def test_fixture_plus_adapter_plus_exporter_end_to_end(self):
        """端到端：Fixture → Adapter → Mapper → Exporter → Validator"""
        adapter = CompetitionInputAdapter()
        mapper = CompetitionMapper()
        exporter = CompetitionExporter()
        validator = SubmissionValidator()

        all_tasks = []
        for name in ["whole_scene.json", "png_tile.json", "t1_t2_pair.json", "multi_asset.json"]:
            assets, tasks = adapter.parse_manifest(str(FIXTURES_DIR / name))
            for task in tasks:
                # 模拟 PerceptionResult
                result = PerceptionResult(
                    perception_result_id=f"pr-{task.task_id}",
                    inference_task_ref=task.task_id,
                    task_spec_ref=task.task_spec_ref,
                    run_id=f"run-{task.task_id}",
                    status=ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
                    observations=[
                        Observation(
                            observation_id=f"obs-{task.task_id}-0",
                            perception_result_ref=f"pr-{task.task_id}",
                            source_asset_refs=[b.asset_ref for b in task.asset_bindings],
                            source_task_type=TaskType.TEMPORAL_CHANGE_DETECTION,
                            observation_type=ObservationType.SAR_BACKSCATTER_CHANGE,
                            label="change_candidate",
                            score=0.75,
                            score_type="rule_based",
                        )
                    ],
                )
                pr = mapper.map_result(result, task)
                all_tasks.append(pr)

        bundle = exporter.export(all_tasks, bundle_id="test-e2e-all")
        report = validator.validate(bundle)
        assert report.passed, f"E2E 校验失败: {report.errors}"
        assert len(bundle.predictions) == 4

    def test_detection_result_adapter_chain(self):
        """旧 DetectionResult → Adapter → Mapper → Exporter → Validator"""
        adapter = DetectionResultAdapter()
        mapper = CompetitionMapper()
        exporter = CompetitionExporter()
        validator = SubmissionValidator()

        task = InferenceTask(
            task_id="task-legacy-001", sample_id="s-001", task_order=0,
            task_spec_ref="sar-temporal-change-v1@1.0.0",
            asset_bindings=[TaskAssetBinding(asset_ref="s1_t1", role=AssetRole.BEFORE)],
        )
        ctx = RunContext(run_id="run-legacy-001")
        dr_list = [
            {"detection_id": "SAR-CHG-001", "category": "change", "confidence": 0.7,
             "source_assets": ["s1_t1", "s1_t2"], "observed_at": "2026-06",
             "evidence_refs": ["mask-001"]},
        ]
        perception_result = adapter.to_perception_result(dr_list, task, ctx)
        pr = adapter.to_prediction_record(perception_result, task)
        bundle = exporter.export([pr])
        report = validator.validate(bundle)
        assert report.passed
        assert pr.inference_task_ref == "task-legacy-001"
