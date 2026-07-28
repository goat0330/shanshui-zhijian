"""Tests for ML baseline pipeline — smoke test."""

import json
import shutil
from pathlib import Path

import pytest

from ml.data_adapter import load_data, WaterQualityDataset, FEATURE_COLS
from ml.model import BaselineModel
from core.schemas.contracts.perception import PerceptionResult
from core.schemas.contracts.candidate import DetectionCandidate


CHECKPOINT = Path(__file__).parent.parent / "ml" / "data" / "checkpoint.joblib"


@pytest.fixture(scope="module")
def trained_model():
    model = BaselineModel(n_estimators=20, max_depth=5, random_state=42)
    (train_X, train_y), _, _ = load_data()
    model.train(train_X, train_y)
    return model


class TestDataAdapter:
    def test_load_splits(self):
        (train_X, train_y), (val_X, val_y), (test_X, test_y) = load_data()
        assert len(train_X) == 2000
        assert len(val_X) == 500
        assert len(test_X) == 500
        assert all(c in train_X.columns for c in FEATURE_COLS)
        assert set(train_y.unique()) == {0, 1}

    def test_water_quality_dataset(self):
        ds = WaterQualityDataset()
        X, y = ds.load_split("train")
        assert len(X) > 0
        assert list(X.columns) == FEATURE_COLS

    def test_missing_split_raises(self):
        ds = WaterQualityDataset(Path("/nonexistent"))
        with pytest.raises(FileNotFoundError):
            ds.load_split("train")


class TestBaselineModel:
    def test_train_and_predict(self, trained_model):
        (_, _), (_, _), (test_X, test_y) = load_data()
        preds = trained_model.predict(test_X)
        assert len(preds) == len(test_y)
        assert set(preds).issubset({0, 1})

    def test_predict_proba(self, trained_model):
        (_, _), (_, _), (test_X, _) = load_data()
        proba = trained_model.predict_proba(test_X)
        assert proba.shape == (len(test_X), 2)
        assert (proba >= 0).all() and (proba <= 1).all()

    def test_evaluate(self, trained_model):
        (_, _), (_, _), (test_X, test_y) = load_data()
        metrics = trained_model.evaluate(test_X, test_y)
        assert "accuracy" in metrics
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1_score" in metrics
        assert 0.0 <= metrics["accuracy"] <= 1.0

    def test_save_load_roundtrip(self, trained_model, tmp_path):
        path = tmp_path / "test_model.joblib"
        trained_model.save(path)
        assert path.exists()
        loaded = BaselineModel.load(path)
        (_, _), (_, _), (test_X, _) = load_data()
        orig_preds = trained_model.predict(test_X)
        loaded_preds = loaded.predict(test_X)
        assert (orig_preds == loaded_preds).all()


class TestCheckpointExists:
    def test_checkpoint_present(self):
        assert CHECKPOINT.exists(), (
            "Run 'python -m ml.train' to generate checkpoint before tests"
        )

    def test_checkpoint_loadable(self):
        model = BaselineModel.load(CHECKPOINT)
        assert model.model is not None

    def test_checkpoint_inference(self):
        model = BaselineModel.load(CHECKPOINT)
        from ml.data_adapter import WaterQualityDataset
        ds = WaterQualityDataset()
        X, _ = ds.load_split("test")
        sample = X.head(1)
        pred = model.predict(sample)
        prob = model.predict_proba(sample)[:, 1]
        assert pred[0] in (0, 1)
        assert 0.0 <= prob[0] <= 1.0


class TestContractConversion:
    def test_inference_produces_perception_result(self):
        from ml.infer import run_inference
        pr, dc = run_inference()
        assert isinstance(pr, PerceptionResult)
        assert pr.status.value == "succeeded_with_observations"
        assert len(pr.observations) > 0

    def test_inference_produces_detection_candidate(self):
        from ml.infer import run_inference
        pr, dc = run_inference()
        assert isinstance(dc, DetectionCandidate)
        assert dc.candidate_type == "water_anomaly"
        assert len(dc.observation_refs) > 0

    def test_perception_result_serialization(self):
        from ml.infer import run_inference
        pr, _ = run_inference()
        data = json.loads(pr.model_dump_json())
        pr2 = PerceptionResult.model_validate(data)
        assert pr2.perception_result_id == pr.perception_result_id

    def test_detection_candidate_serialization(self):
        from ml.infer import run_inference
        _, dc = run_inference()
        data = json.loads(dc.model_dump_json())
        dc2 = DetectionCandidate.model_validate(data)
        assert dc2.candidate_id == dc.candidate_id

    def test_custom_csv_input(self, tmp_path):
        import pandas as pd
        from ml.data_adapter import FEATURE_COLS
        csv_path = tmp_path / "sample.csv"
        row = {c: 0.0 for c in FEATURE_COLS}
        pd.DataFrame([row]).to_csv(csv_path, index=False)

        from ml.infer import run_inference
        pr, dc = run_inference(str(csv_path))
        assert len(pr.observations) == 1
        assert dc.candidate_type == "water_anomaly"
