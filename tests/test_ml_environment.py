import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pytest
from pydantic import ValidationError

from ml.artifacts import ModelCheckpoint, save_checkpoint, load_checkpoint, ArtifactMetadata
from ml.config import DataConfig, ModelConfig, TrainingConfig, TrainConfig
from ml.metrics import accuracy, precision, recall, f1_score, confusion_matrix, classification_report, mse, mae, r2_score
from ml.run_manifest import MlRunManifest, build_ml_manifest


class TestConfig:
    def test_default_creation(self):
        cfg = TrainConfig()
        assert cfg.training.max_epochs == 50
        assert cfg.training.seed == 42
        assert cfg.data.batch_size == 32
        assert cfg.model.backbone == "resnet18"

    def test_custom_values(self):
        cfg = TrainConfig(
            training=TrainingConfig(max_epochs=10, seed=99),
            data=DataConfig(batch_size=64),
        )
        assert cfg.training.max_epochs == 10
        assert cfg.training.seed == 99
        assert cfg.data.batch_size == 64

    def test_validation_error_on_invalid_batch_size(self):
        with pytest.raises(ValidationError):
            DataConfig(batch_size=0)

    def test_validation_error_on_invalid_learning_rate(self):
        with pytest.raises(ValidationError):
            TrainingConfig(learning_rate=0)

    def test_smoke_defaults(self):
        cfg = TrainConfig.smoke_defaults()
        assert cfg.training.max_epochs == 2
        assert cfg.data.batch_size == 4
        assert cfg.data.num_workers == 0

    def test_to_json_roundtrip(self):
        cfg1 = TrainConfig(training=TrainingConfig(max_epochs=5, seed=123))
        raw = cfg1.to_json()
        data = json.loads(raw)
        assert data["training"]["max_epochs"] == 5
        assert data["training"]["seed"] == 123


class TestMetrics:
    def test_accuracy_perfect(self):
        y_true = np.array([0, 1, 0, 1])
        y_pred = np.array([0, 1, 0, 1])
        assert accuracy(y_true, y_pred) == 1.0

    def test_accuracy_half(self):
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 1, 0, 1])
        assert accuracy(y_true, y_pred) == 0.5

    def test_precision_recall_f1(self):
        y_true = np.array([0, 1, 1, 1, 0, 0])
        y_pred = np.array([0, 1, 0, 1, 0, 1])
        p = precision(y_true, y_pred, pos_label=1)
        r = recall(y_true, y_pred, pos_label=1)
        f1 = f1_score(y_true, y_pred, pos_label=1)
        assert 0 < p <= 1.0
        assert 0 < r <= 1.0
        assert 0 < f1 <= 1.0

    def test_empty_arrays(self):
        y_true = np.array([], dtype=int)
        y_pred = np.array([], dtype=int)
        assert accuracy(y_true, y_pred) == 0.0
        assert precision(y_true, y_pred) == 0.0
        assert recall(y_true, y_pred) == 0.0
        assert f1_score(y_true, y_pred) == 0.0

    def test_confusion_matrix(self):
        y_true = np.array([0, 0, 1, 1, 2, 2])
        y_pred = np.array([0, 1, 1, 1, 2, 0])
        cm = confusion_matrix(y_true, y_pred, num_classes=3)
        assert cm.shape == (3, 3)
        assert cm[0, 0] == 1
        assert cm[0, 1] == 1
        assert cm[1, 1] == 2

    def test_regression_metrics(self):
        y_true = np.array([1.0, 2.0, 3.0, 4.0])
        y_pred = np.array([1.1, 2.0, 2.9, 4.2])
        assert mse(y_true, y_pred) > 0
        assert mae(y_true, y_pred) > 0
        assert 0 < r2_score(y_true, y_pred) <= 1.0

    def test_classification_report(self):
        y_true = np.array([0, 0, 1, 1, 2, 2])
        y_pred = np.array([0, 0, 1, 1, 2, 2])
        report = classification_report(y_true, y_pred)
        assert report["accuracy"] == 1.0
        assert "class_0_f1" in report
        assert report["class_0_f1"] == 1.0


class TestArtifacts:
    def test_checkpoint_save_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.pt"
            state = {"epoch": 5, "val_acc": 0.95, "weights": np.array([1, 2, 3])}
            save_checkpoint(state, path)
            assert path.exists()
            loaded = load_checkpoint(str(path))
            assert loaded["epoch"] == 5
            assert loaded["val_acc"] == 0.95

    def test_model_checkpoint_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ckpt.pt"
            save_checkpoint({"a": 1}, path)
            ckpt = ModelCheckpoint(path)
            assert ckpt.exists()
            assert ckpt.size_bytes() > 0
            assert len(ckpt.sha256()) == 64

    def test_artifact_metadata_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "model.pt"
            file_path.write_text("dummy content")
            meta = ArtifactMetadata(
                artifact_id="test-model",
                file_path=file_path,
                artifact_type="model",
                extra={"epoch": 5},
            )
            meta_path = Path(tmp) / "metadata.json"
            meta.save_metadata(meta_path)
            assert meta_path.exists()
            loaded = ArtifactMetadata.from_file(meta_path)
            assert loaded.artifact_id == "test-model"
            assert loaded.artifact_type == "model"
            assert loaded.extra["epoch"] == 5


class TestRunManifest:
    def test_create_and_finalize(self):
        manifest = MlRunManifest(run_id="test-run-001")
        manifest.record_config(TrainConfig.smoke_defaults())
        manifest.record_dataset("train_data", "data/train", sha256="a" * 64)
        run_manifest = manifest.finalize()
        assert run_manifest.run_id == "test-run-001"
        assert run_manifest.manifest_sha256 is not None
        assert len(run_manifest.manifest_sha256) == 64

    def test_save_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = MlRunManifest(run_id="save-test")
            path = manifest.save(Path(tmp) / "manifest.json")
            assert path.exists()
            loaded = json.loads(path.read_text(encoding="utf-8"))
            assert loaded["run_id"] == "save-test"
            assert loaded["status"] == "succeeded"

    def test_record_metrics_in_manifest(self):
        manifest = MlRunManifest(run_id="metrics-test")
        manifest.record_metrics({"val_acc": 0.95, "train_loss": 0.23})
        run_manifest = manifest.finalize()
        assert run_manifest.tool_config.get("metrics", {}).get("val_acc") == 0.95
        assert run_manifest.tool_config["metrics"]["train_loss"] == 0.23


class TestTrainSmoke:
    def test_smoke_creates_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "ml_output"
            from ml.train import _train_smoke
            config = TrainConfig.smoke_defaults()
            ckpt = _train_smoke(config, "smoke-test", output_dir)
            assert Path(ckpt).exists()
            assert Path(ckpt).stat().st_size > 0

    def test_smoke_creates_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "ml_output"
            from ml.train import _train_smoke
            config = TrainConfig.smoke_defaults()
            _train_smoke(config, "smoke-test-2", output_dir)
            manifest_path = output_dir / "run_manifest.json"
            assert manifest_path.exists()
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert data["run_id"] == "smoke-test-2"

    def test_smoke_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            from ml.train import _train_smoke
            config = TrainConfig.smoke_defaults()
            ckpt1 = _train_smoke(config, "det-1", Path(tmp1))
            ckpt2 = _train_smoke(config, "det-2", Path(tmp2))
            from ml.artifacts import load_checkpoint
            s1 = load_checkpoint(ckpt1)
            s2 = load_checkpoint(ckpt2)
            for k in s1["model_state_dict"]:
                assert (s1["model_state_dict"][k] == s2["model_state_dict"][k]).all(), f"Mismatch at {k}"


class TestBuildManifest:
    def test_build_minimal(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = build_ml_manifest(run_id="build-min")
            assert manifest.run_id == "build-min"
            assert manifest.status.value == "succeeded"
            assert len(manifest.manifest_sha256) == 64

    def test_build_with_metrics(self):
        manifest = build_ml_manifest(
            run_id="build-metrics",
            metrics={"accuracy": 0.95, "f1_score": 0.93},
        )
        assert manifest.tool_config["metrics"]["accuracy"] == 0.95
        assert manifest.tool_config["metrics"]["f1_score"] == 0.93

    def test_build_with_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            ckpt_path = Path(tmp) / "model.pt"
            from ml.artifacts import save_checkpoint
            save_checkpoint({"epoch": 3}, ckpt_path)
            manifest = build_ml_manifest(
                run_id="build-ckpt",
                checkpoint_path=ckpt_path,
            )
            artifacts = manifest.output_artifacts
            assert len(artifacts) == 1
            assert artifacts[0].artifact_id == "model_checkpoint"
            assert len(artifacts[0].sha256) == 64

    def test_build_with_dataset(self):
        manifest = build_ml_manifest(
            run_id="build-ds",
            dataset_paths={"train": "data/train", "val": "data/val"},
        )
        assert len(manifest.input_assets) == 2
        assert manifest.input_assets[0].asset_id == "train"

    def test_build_with_seed(self):
        manifest = build_ml_manifest(run_id="build-seed", seed=777)
        assert manifest.random_seed == 777


class TestPipeline:
    def test_pipeline_smoke_creates_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "pipe_output"
            from ml.pipeline import train_pipeline
            config = TrainConfig.smoke_defaults()
            result = train_pipeline(config, "pipe-test", output_dir, use_smoke=True)
            assert Path(result["checkpoint"]).exists()
            assert Path(result["manifest"]).exists()
            assert result["run_id"] == "pipe-test"
            assert len(result["checkpoint_sha256"]) == 64

    def test_pipeline_metrics_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "pipe_metrics"
            from ml.pipeline import train_pipeline
            config = TrainConfig.smoke_defaults()
            result = train_pipeline(config, "pipe-metrics", output_dir, use_smoke=True)
            assert "val_acc_epoch_0" in result["metrics"]
            assert "val_f1_epoch_0" in result["metrics"]
            assert result["metrics"]["val_acc_epoch_0"] >= 0

    def test_pipeline_manifest_has_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "pipe_config"
            from ml.pipeline import train_pipeline
            config = TrainConfig.smoke_defaults()
            train_pipeline(config, "pipe-cfg", output_dir, use_smoke=True)
            manifest_data = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
            assert "training_config" in manifest_data.get("tool_config", {})
            assert manifest_data["tool_config"]["training_config"]["training"]["seed"] == 42


class TestEvaluate:
    def test_evaluate_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            from ml.pipeline import train_pipeline
            config = TrainConfig.smoke_defaults()
            train_result = train_pipeline(config, "eval-train", Path(tmp) / "train", use_smoke=True)

            from ml.evaluate import evaluate_checkpoint
            eval_result = evaluate_checkpoint(
                checkpoint_path=train_result["checkpoint"],
                config=config,
                run_id="eval-smoke",
                output_dir=Path(tmp) / "eval",
                use_smoke=True,
            )
            assert eval_result["num_test_samples"] > 0
            assert 0 <= eval_result["metrics"]["accuracy"] <= 1.0
            assert 0 <= eval_result["metrics"]["f1_score"] <= 1.0

    def test_evaluate_manifest_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            from ml.pipeline import train_pipeline
            config = TrainConfig.smoke_defaults()
            train_result = train_pipeline(config, "eval-manifest", Path(tmp) / "train", use_smoke=True)

            from ml.evaluate import evaluate_checkpoint
            eval_result = evaluate_checkpoint(
                checkpoint_path=train_result["checkpoint"],
                config=config,
                run_id="eval-manifest-test",
                output_dir=Path(tmp) / "eval",
                use_smoke=True,
            )
            manifest_path = Path(eval_result["manifest"])
            assert manifest_path.exists()
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert manifest_data["run_id"] == "eval-manifest-test"
            assert manifest_data["status"] == "succeeded"

    def test_evaluate_confusion_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            from ml.pipeline import train_pipeline
            config = TrainConfig.smoke_defaults()
            train_result = train_pipeline(config, "eval-cm", Path(tmp) / "train", use_smoke=True)

            from ml.evaluate import evaluate_checkpoint
            eval_result = evaluate_checkpoint(
                checkpoint_path=train_result["checkpoint"],
                config=config,
                run_id="eval-cm-test",
                output_dir=Path(tmp) / "eval",
                use_smoke=True,
            )
            cm = eval_result["confusion_matrix"]
            assert len(cm) == 2  # binary classification
            assert len(cm[0]) == 2
