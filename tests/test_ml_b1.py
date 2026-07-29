"""Tests for ML-B1 real data pipeline."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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

HAS_REAL_RASTERS = (DATA_DIR / "test_s2_t1.tif").exists() and (DATA_DIR / "test_jrc_occurrence.tif").exists()
skip_no_rasters = pytest.mark.skipif(not HAS_REAL_RASTERS, reason="Real test rasters not available")


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

    @skip_no_rasters
    def test_real_data_loading(self):
        s2 = DATA_DIR / "test_s2_t1.tif"
        jrc = DATA_DIR / "test_jrc_occurrence.tif"
        (train_X, train_y), (val_X, val_y), (test_X, test_y) = load_real_data(s2, jrc, max_samples=500)
        assert len(train_X) > 0
        assert len(val_X) > 0
        assert len(test_X) > 0
        for col in REAL_FEATURE_COLS:
            assert col in train_X.columns
        assert set(train_y.unique()).issubset({0, 1})

    @skip_no_rasters
    def test_real_data_feature_values(self):
        s2 = DATA_DIR / "test_s2_t1.tif"
        jrc = DATA_DIR / "test_jrc_occurrence.tif"
        (train_X, train_y), _, _ = load_real_data(s2, jrc, max_samples=300)
        assert train_X["ndwi"].between(-1, 1).all()
        assert train_X["ndvi"].between(-1, 1).all()

    @skip_no_rasters
    def test_real_data_training(self, real_trained_model):
        model, feat_names = real_trained_model
        assert model.model is not None
        assert model.feature_names == feat_names

    @skip_no_rasters
    def test_real_data_prediction(self, real_trained_model):
        model, feat_names = real_trained_model
        s2 = DATA_DIR / "test_s2_t1.tif"
        jrc = DATA_DIR / "test_jrc_occurrence.tif"
        (_, _), _, (test_X, test_y) = load_real_data(s2, jrc, max_samples=300)
        preds = model.predict(test_X)
        assert len(preds) == len(test_y)
        assert set(preds).issubset({0, 1})

    @skip_no_rasters
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

    def test_real_mode_is_fail_closed(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_data(
                use_real=True,
                s2_path=tmp_path / "missing-s2.tif",
                jrc_path=tmp_path / "missing-jrc.tif",
            )

    def test_auto_data_detection(self):
        (train_X, train_y), _, _ = load_data()
        assert len(train_X) == 2000


class TestMLB1Model:
    def test_model_train(self):
        from ml.data_adapter import load_synthetic_data
        (train_X, train_y), _, _ = load_synthetic_data()
        model = BaselineModel(n_estimators=20, max_depth=5, random_state=42)
        model.train(train_X, train_y)
        assert model.model is not None

    def test_model_predict(self):
        from ml.data_adapter import load_synthetic_data
        (train_X, train_y), _, _ = load_synthetic_data()
        model = BaselineModel(n_estimators=20, max_depth=5, random_state=42)
        model.train(train_X, train_y)
        preds = model.predict(train_X.head(10))
        assert len(preds) == 10

    def test_model_save_load(self, tmp_path):
        from ml.data_adapter import load_synthetic_data
        (train_X, train_y), _, _ = load_synthetic_data()
        model = BaselineModel(n_estimators=20, max_depth=5, random_state=42)
        model.train(train_X, train_y)
        cp = tmp_path / "model.joblib"
        model.save(cp)
        loaded = BaselineModel.load(cp)
        assert loaded.model is not None
        preds = loaded.predict(train_X.head(5))
        assert len(preds) == 5

    def test_model_get_params(self):
        model = BaselineModel(n_estimators=50, max_depth=8, random_state=99)
        params = model.get_params()
        assert params["n_estimators"] == 50
        assert params["max_depth"] == 8
        assert params["random_state"] == 99


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

    @skip_no_rasters
    def test_geotiff_inference(self, tmp_path):
        s2 = DATA_DIR / "test_s2_t1.tif"
        jrc = DATA_DIR / "test_jrc_occurrence.tif"
        (train_X, train_y), _, _ = load_real_data(s2, jrc, max_samples=500)
        model = BaselineModel(n_estimators=20, max_depth=5, random_state=42)
        model.train(train_X, train_y)
        cp = tmp_path / "checkpoint_real.joblib"
        model.save(cp)
        pr, dc = run_inference(geotiff_path=str(s2), checkpoint_path=cp)
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

        from ml.data_adapter import SYNTH_FEATURE_COLS
        row = {c: 0.0 for c in SYNTH_FEATURE_COLS} | {"ndwi": -0.5}
        csv_path = tmp_path / "sample.csv"
        pd.DataFrame([row]).to_csv(csv_path, index=False)
        pr, dc = run_inference(str(csv_path), checkpoint_path=trained_checkpoint)
        assert len(pr.observations) == 1
