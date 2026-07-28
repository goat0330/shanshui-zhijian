"""Tests for ML-B1 real data pipeline."""

import json
from pathlib import Path

import pytest
import pandas as pd
import numpy as np

from ml.model import BaselineModel
from ml.infer import run_inference
from ml.data_adapter import load_data, load_real_data, REAL_FEATURE_COLS
from ml.data.dataset_registry import DatasetRegistry
from core.schemas.contracts.perception import PerceptionResult
from core.schemas.contracts.candidate import DetectionCandidate


ML_DIR = Path(__file__).resolve().parent.parent / "ml"
DATA_DIR = ML_DIR / "data"


class TestDatasetRegistry:
    def test_load_registry(self):
        registry = DatasetRegistry()
        datasets = registry.list_available()
        assert len(datasets) > 0

    def test_get_sentinel2(self):
        registry = DatasetRegistry()
        entry = registry.get("sentinel2_l2a")
        assert entry is not None
        assert entry.source_uri == "COPERNICUS/S2_SR_HARMONIZED"
        assert len(entry.bands) == 6

    def test_verify_license(self):
        registry = DatasetRegistry()
        result = registry.verify_license("sentinel2_l2a")
        assert result["ok"] is True
        assert "Copernicus" in result["license"]

    def test_get_local_datasets(self):
        registry = DatasetRegistry()
        local = registry.list_source_types("local_geotiff")
        assert len(local) >= 2

    def test_to_json(self):
        registry = DatasetRegistry()
        raw = registry.to_json()
        assert '"datasets"' in raw


class TestDataAdapterReal:
    @pytest.fixture
    def real_trained_model(self):
        s2 = DATA_DIR / "test_s2_t1.tif"
        jrc = DATA_DIR / "test_jrc_occurrence.tif"
        if not s2.exists() or not jrc.exists():
            pytest.skip("Test rasters not found")
        (train_X, train_y), _, _ = load_real_data(s2, jrc, max_samples=500)
        model = BaselineModel(n_estimators=20, max_depth=5, random_state=42)
        model.train(train_X, train_y)
        return model, train_X.columns.tolist()

    def test_real_data_loading(self):
        s2 = DATA_DIR / "test_s2_t1.tif"
        jrc = DATA_DIR / "test_jrc_occurrence.tif"
        if not s2.exists():
            pytest.skip("Test rasters not found")
        (train_X, train_y), (val_X, val_y), (test_X, test_y) = load_real_data(s2, jrc, max_samples=500)
        assert len(train_X) > 0
        assert len(val_X) > 0
        assert len(test_X) > 0
        for col in REAL_FEATURE_COLS:
            assert col in train_X.columns
        assert set(train_y.unique()).issubset({0, 1})

    def test_real_data_feature_values(self):
        s2 = DATA_DIR / "test_s2_t1.tif"
        jrc = DATA_DIR / "test_jrc_occurrence.tif"
        if not s2.exists():
            pytest.skip("Test rasters not found")
        (train_X, train_y), _, _ = load_real_data(s2, jrc, max_samples=300)
        assert train_X["ndwi"].between(-1, 1).all()
        assert train_X["ndvi"].between(-1, 1).all()

    def test_real_data_training(self, real_trained_model):
        model, feat_names = real_trained_model
        assert model.model is not None
        assert model.feature_names == feat_names

    def test_real_data_prediction(self, real_trained_model):
        model, feat_names = real_trained_model
        s2 = DATA_DIR / "test_s2_t1.tif"
        jrc = DATA_DIR / "test_jrc_occurrence.tif"
        (_, _), _, (test_X, test_y) = load_real_data(s2, jrc, max_samples=300)
        preds = model.predict(test_X)
        assert len(preds) == len(test_y)
        assert set(preds).issubset({0, 1})

    def test_real_data_evaluate(self, real_trained_model):
        model, _ = real_trained_model
        s2 = DATA_DIR / "test_s2_t1.tif"
        jrc = DATA_DIR / "test_jrc_occurrence.tif"
        (_, _), _, (test_X, test_y) = load_real_data(s2, jrc, max_samples=300)
        metrics = model.evaluate(test_X, test_y)
        assert "accuracy" in metrics
        assert "roc_auc" in metrics
        assert 0.0 <= metrics["accuracy"] <= 1.0


class TestDataAdapterSynthetic:
    def test_synthetic_fallback(self):
        (train_X, train_y), (val_X, val_y), (test_X, test_y) = load_data(use_real=False)
        assert len(train_X) == 2000
        assert len(val_X) == 500
        assert len(test_X) == 500

    def test_synthetic_with_use_real_flag(self):
        (train_X, train_y), _, _ = load_data(use_real=True)
        assert len(train_X) == 2000

    def test_auto_data_detection(self):
        (train_X, train_y), _, _ = load_data()
        assert len(train_X) == 2000


class TestMLB1Inference:
    @pytest.fixture
    def trained_checkpoint(self, tmp_path):
        from ml.data_adapter import load_synthetic_data
        (train_X, train_y), _, _ = load_synthetic_data()
        model = BaselineModel(n_estimators=20, max_depth=5, random_state=42)
        model.train(train_X, train_y)
        cp = tmp_path / "checkpoint.joblib"
        model.save(cp)
        return cp

    @pytest.fixture
    def multi_row_csv(self, tmp_path):
        from ml.data_adapter import SYNTH_FEATURE_COLS
        rows = [
            {c: 0.0 for c in SYNTH_FEATURE_COLS},
            {c: 0.0 for c in SYNTH_FEATURE_COLS} | {"ndwi": -0.5},
            {c: 0.0 for c in SYNTH_FEATURE_COLS} | {"ph": 9.5},
        ]
        path = tmp_path / "multi_sample.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        return path

    def test_inference_produces_perception_result(self, multi_row_csv, trained_checkpoint):
        pr, dc = run_inference(str(multi_row_csv), checkpoint_path=trained_checkpoint)
        assert isinstance(pr, PerceptionResult)
        assert pr.status.value == "succeeded_with_observations"
        assert len(pr.observations) > 0

    def test_inference_detection_candidate(self, multi_row_csv, trained_checkpoint):
        pr, dc = run_inference(str(multi_row_csv), checkpoint_path=trained_checkpoint)
        assert isinstance(dc, DetectionCandidate)
        assert dc.candidate_type == "water_anomaly"

    def test_inference_no_candidate_when_normal(self, tmp_path, trained_checkpoint):
        from ml.data_adapter import SYNTH_FEATURE_COLS
        row = {c: 0.0 for c in SYNTH_FEATURE_COLS}
        path = tmp_path / "normal.csv"
        pd.DataFrame([row]).to_csv(path, index=False)
        pr, dc = run_inference(str(path), checkpoint_path=trained_checkpoint)
        assert dc is None

    def test_perception_result_serialization(self, multi_row_csv, trained_checkpoint):
        pr, _ = run_inference(str(multi_row_csv), checkpoint_path=trained_checkpoint)
        data = json.loads(pr.model_dump_json())
        pr2 = PerceptionResult.model_validate(data)
        assert pr2.perception_result_id == pr.perception_result_id

    def test_detection_candidate_serialization(self, multi_row_csv, trained_checkpoint):
        _, dc = run_inference(str(multi_row_csv), checkpoint_path=trained_checkpoint)
        data = json.loads(dc.model_dump_json())
        dc2 = DetectionCandidate.model_validate(data)
        assert dc2.candidate_id == dc.candidate_id

    def test_geotiff_inference(self, trained_checkpoint):
        s2 = DATA_DIR / "test_s2_t1.tif"
        if not s2.exists():
            pytest.skip("Test rasters not found")
        pr, dc = run_inference(geotiff_path=str(s2), checkpoint_path=trained_checkpoint)
        assert isinstance(pr, PerceptionResult)
        assert len(pr.observations) > 0

    def test_train_checkpoint_loading(self, trained_checkpoint):
        assert trained_checkpoint.exists()
        model = BaselineModel.load(trained_checkpoint)
        assert model.model is not None

    def test_smoke_train_evaluate_infer(self, tmp_path, trained_checkpoint):
        from ml.data_adapter import load_synthetic_data
        _, (_, _), (test_X, test_y) = load_synthetic_data()
        model = BaselineModel.load(trained_checkpoint)
        metrics = model.evaluate(test_X, test_y)
        assert metrics["accuracy"] > 0.0

        row = {c: 0.0 for c in ["ndwi", "mndwi", "turbidity_index", "chlorophyll_index", "ph", "temperature", "rainfall_7d", "upstream_landuse"]} | {"ndwi": -0.5}
        csv_path = tmp_path / "sample.csv"
        pd.DataFrame([row]).to_csv(csv_path, index=False)
        pr, dc = run_inference(str(csv_path), checkpoint_path=trained_checkpoint)
        assert len(pr.observations) == 1
