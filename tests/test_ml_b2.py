"""Tests for ML-B2 water change detection pipeline."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
import numpy as np
import pandas as pd

from ml.model import BaselineModel
from ml.data_adapter import load_real_data, load_synthetic_data
from ml.infer_dense import infer_dense
from ml.change_map import compute_change_map, polygonize_change_mask, change_map_to_geotiff
from ml.water_change import run_water_change, _extract_observations
from core.schemas.contracts.perception import PerceptionResult
from core.schemas.contracts.candidate import DetectionCandidate

ML_DIR = Path(__file__).resolve().parent.parent / "ml"
DATA_DIR = ML_DIR / "data"


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_rasters_exist():
    t1 = DATA_DIR / "test_s2_t1.tif"
    t2 = DATA_DIR / "test_s2_t2.tif"
    jrc = DATA_DIR / "test_jrc_occurrence.tif"
    return t1.exists() and t2.exists() and jrc.exists()


@pytest.fixture(scope="session")
def real_trained_model(tmp_path_factory):
    t1 = DATA_DIR / "test_s2_t1.tif"
    jrc = DATA_DIR / "test_jrc_occurrence.tif"
    if not t1.exists() or not jrc.exists():
        pytest.skip("Test rasters not found")
    (train_X, train_y), _, _ = load_real_data(t1, jrc, max_samples=800)
    model = BaselineModel(n_estimators=30, max_depth=8, random_state=42)
    model.train(train_X, train_y)
    cp = tmp_path_factory.mktemp("checkpoints") / "model.joblib"
    model.save(cp)
    return model, cp


@pytest.fixture(scope="session")
def synthetic_checkpoint(tmp_path_factory):
    (train_X, train_y), _, _ = load_synthetic_data()
    model = BaselineModel(n_estimators=20, max_depth=5, random_state=42)
    model.train(train_X, train_y)
    cp = tmp_path_factory.mktemp("checkpoints") / "synth.joblib"
    model.save(cp)
    return model, cp


# ── Test: Dense Inference ──────────────────────────────────────────────────

class TestInferDense:
    def test_infer_full_image_shape(self, real_trained_model):
        model, _ = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        result = infer_dense(model, t1, block_size=64)
        assert result["prob_map"].shape == (100, 100)
        assert result["mask"].shape == (100, 100)
        assert result["valid_count"] > 0

    def test_infer_probability_range(self, real_trained_model):
        model, _ = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        result = infer_dense(model, t1, block_size=64)
        probs = result["prob_map"][result["prob_map"] > 0]
        assert (probs >= 0).all() and (probs <= 1).all()

    def test_infer_block_size_independent(self, real_trained_model):
        model, _ = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        r1 = infer_dense(model, t1, block_size=50)
        r2 = infer_dense(model, t1, block_size=100)
        np.testing.assert_array_equal(r1["prob_map"], r2["prob_map"])

    def test_infer_output_geotiff(self, real_trained_model, tmp_path):
        model, _ = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        out = tmp_path / "prob.tif"
        result = infer_dense(model, t1, output_path=out, block_size=64)
        assert out.exists()
        assert out.stat().st_size > 0
        import rasterio
        with rasterio.open(out) as src:
            assert src.count == 2
            assert src.height == 100
            assert src.width == 100

    def test_infer_water_mask_binary(self, real_trained_model):
        model, _ = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        result = infer_dense(model, t1, block_size=64)
        mask = result["mask"]
        assert set(np.unique(mask)).issubset({0, 1, 255})
        assert mask.dtype == np.uint8

    def test_infer_preserves_transform(self, real_trained_model):
        model, _ = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        result = infer_dense(model, t1, block_size=64)
        import rasterio
        with rasterio.open(t1) as src:
            assert result["crs"] == src.crs
            assert result["transform"] == src.transform


# ── Test: Change Map ───────────────────────────────────────────────────────

class TestChangeMap:
    def test_compute_change_detects_gain(self):
        t1 = np.zeros((50, 50), dtype=np.uint8)
        t2 = np.zeros((50, 50), dtype=np.uint8)
        t2[10:20, 10:20] = 1  # new water
        result = compute_change_map(t1, t2)
        assert result["stats"]["gain_pixels"] == 100
        assert result["stats"]["loss_pixels"] == 0
        assert result["gain"].sum() == 100

    def test_compute_change_detects_loss(self):
        t1 = np.zeros((50, 50), dtype=np.uint8)
        t2 = np.zeros((50, 50), dtype=np.uint8)
        t1[10:20, 10:20] = 1  # water lost
        result = compute_change_map(t1, t2)
        assert result["stats"]["loss_pixels"] == 100
        assert result["stats"]["gain_pixels"] == 0

    def test_compute_change_detects_persistent(self):
        t1 = np.zeros((50, 50), dtype=np.uint8)
        t2 = np.zeros((50, 50), dtype=np.uint8)
        t1[10:20, 10:20] = 1
        t2[10:20, 10:20] = 1
        result = compute_change_map(t1, t2)
        assert result["stats"]["persistent_pixels"] == 100
        assert result["stats"]["gain_pixels"] == 0
        assert result["stats"]["loss_pixels"] == 0

    def test_change_mask_values(self):
        t1 = np.zeros((50, 50), dtype=np.uint8)
        t2 = np.zeros((50, 50), dtype=np.uint8)
        t1[0:10, 0:10] = 1   # loss area
        t2[20:30, 20:30] = 1  # gain area
        t1[40:50, 40:50] = 1  # persistent
        t2[40:50, 40:50] = 1
        result = compute_change_map(t1, t2)
        cm = result["change_mask"]
        assert (cm[0:10, 0:10] == 2).all()   # loss
        assert (cm[20:30, 20:30] == 1).all()  # gain
        assert (cm[40:50, 40:50] == 3).all()  # persistent
        assert (cm[0:10, 20:30] == 0).all()   # no change

    def test_no_change_when_identical(self):
        t1 = np.zeros((50, 50), dtype=np.uint8)
        result = compute_change_map(t1, t1)
        assert result["stats"]["total_changed"] == 0

    def test_change_map_stats(self):
        t1 = np.zeros((50, 50), dtype=np.uint8)
        t2 = np.zeros((50, 50), dtype=np.uint8)
        t1[0:10, 0:10] = 1
        t2[10:20, 10:20] = 1
        result = compute_change_map(t1, t2)
        s = result["stats"]
        assert s["gain_pixels"] + s["loss_pixels"] == s["total_changed"]
        assert s["total_pixels"] == 2500

    def test_polygonize_creates_features(self):
        t1 = np.zeros((100, 100), dtype=np.uint8)
        t2 = np.zeros((100, 100), dtype=np.uint8)
        t1[10:30, 10:30] = 1
        t2[10:30, 15:35] = 1  # shift right → loss left edge, gain right edge
        change = compute_change_map(t1, t2)
        from rasterio.transform import from_origin
        transform = from_origin(0, 100, 1, 1)
        import rasterio
        crs = rasterio.crs.CRS.from_epsg(4326)
        features = polygonize_change_mask(
            change["change_mask"], transform, crs, min_area_m2=10, pixel_area_m2=1,
        )
        assert len(features) > 0
        for feat in features:
            assert feat["type"] == "Feature"
            assert "geometry" in feat
            assert "change_type" in feat["properties"]
            assert feat["properties"]["change_type"] in ("water_gain", "water_loss")

    def test_polygonize_min_area_filter(self):
        t1 = np.zeros((100, 100), dtype=np.uint8)
        t2 = np.zeros((100, 100), dtype=np.uint8)
        t1[10:13, 10:13] = 1  # 9 pixels
        t2[10:13, 13:16] = 1  # tiny change
        change = compute_change_map(t1, t2)
        from rasterio.transform import from_origin
        transform = from_origin(0, 100, 1, 1)
        import rasterio
        crs = rasterio.crs.CRS.from_epsg(4326)
        # min_area_m2=100 should filter out small 9-pixel features
        features = polygonize_change_mask(
            change["change_mask"], transform, crs, min_area_m2=100, pixel_area_m2=1,
        )
        assert len(features) == 0

    def test_change_geotiff_output(self, tmp_path):
        t1 = np.zeros((50, 50), dtype=np.uint8)
        t2 = np.zeros((50, 50), dtype=np.uint8)
        t2[10:20, 10:20] = 1
        change = compute_change_map(t1, t2)
        from rasterio.transform import from_origin
        import rasterio
        out = tmp_path / "change.tif"
        result = change_map_to_geotiff(
            change, out,
            transform=from_origin(0, 50, 1, 1),
            crs=rasterio.crs.CRS.from_epsg(4326),
        )
        assert out.exists()
        with rasterio.open(out) as src:
            assert src.count == 1
            assert src.height == 50


# ── Test: Observations ─────────────────────────────────────────────────────

class TestObservations:
    def test_observation_has_real_coordinates(self, real_trained_model):
        model, _ = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        result = infer_dense(model, t1, block_size=64)
        import rasterio
        with rasterio.open(t1) as src:
            transform = src.transform
        obs = _extract_observations(
            result["prob_map"], result["mask"],
            transform, "EPSG:4326", "test-run", "T1", max_obs=10,
        )
        assert len(obs) > 0
        for o in obs:
            coords = o.geometry["coordinates"]
            assert len(coords) == 2
            assert 106.0 < coords[0] < 107.0  # longitude
            assert 29.0 < coords[1] < 30.0    # latitude

    def test_observation_has_valid_properties(self, real_trained_model):
        model, _ = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        result = infer_dense(model, t1, block_size=64)
        import rasterio
        with rasterio.open(t1) as src:
            transform = src.transform
        obs = _extract_observations(
            result["prob_map"], result["mask"],
            transform, "EPSG:4326", "test-run", "T1", max_obs=5,
        )
        for o in obs:
            assert o.observation_id.startswith("obs-t1-")
            assert o.score_type.value == "model_probability"
            assert o.coordinate_space == "geographic"
            assert "s2_t1" in o.source_asset_refs

    def test_observation_without_water(self):
        prob = np.zeros((20, 20), dtype=np.float32)
        mask = np.zeros((20, 20), dtype=np.uint8)
        from rasterio.transform import from_origin
        obs = _extract_observations(
            prob, mask, from_origin(0, 20, 1, 1), "EPSG:4326", "r", "T1",
        )
        assert len(obs) == 0


# ── Test: End-to-End Pipeline ──────────────────────────────────────────────

class TestWaterChangePipeline:
    def test_pipeline_runs_end_to_end(self, tmp_path, real_trained_model):
        model, cp = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        t2 = DATA_DIR / "test_s2_t2.tif"
        out = tmp_path / "pipeline_output"
        result = run_water_change(
            t1_path=t1, t2_path=t2,
            checkpoint_path=cp, output_dir=out,
            prob_threshold=0.4, block_size=64, min_area_m2=100,
            max_observations=50,
        )
        assert result["perception_result"] is not None
        assert result["t1_result"]["mask"].shape == (100, 100)
        assert result["t2_result"]["mask"].shape == (100, 100)
        assert result["stats"]["total_pixels"] == 10000

    def test_pipeline_produces_perception_result(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        t2 = DATA_DIR / "test_s2_t2.tif"
        result = run_water_change(
            t1, t2, cp, tmp_path / "out",
            prob_threshold=0.4, block_size=64, min_area_m2=100,
        )
        pr = result["perception_result"]
        assert isinstance(pr, PerceptionResult)
        assert pr.status.value == "succeeded_with_observations"

    def test_pipeline_produces_detection_candidate(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        t2 = DATA_DIR / "test_s2_t2.tif"
        result = run_water_change(
            t1, t2, cp, tmp_path / "out",
            prob_threshold=0.4, block_size=64, min_area_m2=100,
        )
        dc = result["detection_candidate"]
        assert isinstance(dc, DetectionCandidate)
        assert dc.candidate_type == "water_extent_change"
        assert dc.geometry is not None

    def test_pipeline_output_files(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        t2 = DATA_DIR / "test_s2_t2.tif"
        out = tmp_path / "out"
        result = run_water_change(t1, t2, cp, out, prob_threshold=0.4, block_size=64, min_area_m2=100)

        files = list(out.iterdir())
        names = [f.name for f in files]
        assert "water_prob_t1.tif" in names
        assert "water_prob_t2.tif" in names
        assert "change_mask.tif" in names
        assert "change_polygons.geojson" in names
        assert "pipeline_result.json" in names

    def test_pipeline_geojson_valid(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        t2 = DATA_DIR / "test_s2_t2.tif"
        out = tmp_path / "out"
        result = run_water_change(t1, t2, cp, out, prob_threshold=0.4, block_size=64, min_area_m2=100)

        geojson_path = out / "change_polygons.geojson"
        data = json.loads(geojson_path.read_text())
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) > 0
        for feat in data["features"]:
            assert feat["geometry"]["type"] in ("Polygon", "MultiPolygon")

    def test_pipeline_different_thresholds(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        t2 = DATA_DIR / "test_s2_t2.tif"
        r1 = run_water_change(t1, t2, cp, tmp_path / "t05", prob_threshold=0.5, block_size=64, min_area_m2=100)
        r2 = run_water_change(t1, t2, cp, tmp_path / "t07", prob_threshold=0.7, block_size=64, min_area_m2=100)
        # Higher threshold should produce fewer water pixels
        assert r1["stats"]["total_changed"] >= r2["stats"]["total_changed"]

    def test_pipeline_perception_result_serializable(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        t2 = DATA_DIR / "test_s2_t2.tif"
        result = run_water_change(t1, t2, cp, tmp_path / "out", prob_threshold=0.4, block_size=64, min_area_m2=100)
        pr = result["perception_result"]
        data = json.loads(pr.model_dump_json())
        pr2 = PerceptionResult.model_validate(data)
        assert pr2.perception_result_id == pr.perception_result_id

    def test_pipeline_detection_candidate_serializable(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        t2 = DATA_DIR / "test_s2_t2.tif"
        result = run_water_change(t1, t2, cp, tmp_path / "out", prob_threshold=0.4, block_size=64, min_area_m2=100)
        dc = result["detection_candidate"]
        if dc:
            data = json.loads(dc.model_dump_json())
            dc2 = DetectionCandidate.model_validate(data)
            assert dc2.candidate_id == dc.candidate_id

    def test_pipeline_diagnostics(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        t2 = DATA_DIR / "test_s2_t2.tif"
        result = run_water_change(t1, t2, cp, tmp_path / "out", prob_threshold=0.4, block_size=64, min_area_m2=100)
        diag = result["perception_result"].diagnostics
        assert diag["model"] == "RandomForest"
        assert "change_stats" in diag
        assert diag["n_polygons"] >= 0
        assert diag["n_observations"] >= 0

    def test_pipeline_raises_on_missing_checkpoint(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            run_water_change(
                t1_path=DATA_DIR / "test_s2_t1.tif",
                t2_path=DATA_DIR / "test_s2_t2.tif",
                checkpoint_path=tmp_path / "nonexistent.joblib",
            )

    def test_pipeline_different_block_sizes(self, tmp_path, real_trained_model):
        """Block size should not affect results."""
        _, cp = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        t2 = DATA_DIR / "test_s2_t2.tif"
        r1 = run_water_change(t1, t2, cp, tmp_path / "b32", prob_threshold=0.4, block_size=32, min_area_m2=100)
        r2 = run_water_change(t1, t2, cp, tmp_path / "b99", prob_threshold=0.4, block_size=99, min_area_m2=100)
        assert r1["stats"] == r2["stats"]
