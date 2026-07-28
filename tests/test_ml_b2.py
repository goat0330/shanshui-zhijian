"""Tests for ML-B2 water change detection pipeline — including Cycle 3.1 fixes."""

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
from ml.change_map import (
    compute_change_map,
    polygonize_change_mask,
    combine_polygons_to_multipolygon,
    change_map_to_geotiff,
)
from ml.water_change import run_water_change, _extract_observations, _extract_acquisition_dates
from core.schemas.contracts.perception import PerceptionResult, Observation
from core.schemas.contracts.candidate import DetectionCandidate, CandidateQualitySummary

ML_DIR = Path(__file__).resolve().parent.parent / "ml"
DATA_DIR = ML_DIR / "data"


# ── Session Fixtures ──────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_rasters_exist():
    return all(
        (DATA_DIR / f).exists()
        for f in ["test_s2_t1.tif", "test_s2_t2.tif", "test_jrc_occurrence.tif"]
    )


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


# ── Dense Inference ───────────────────────────────────────────────────────

class TestInferDense:
    def test_full_image_shape(self, real_trained_model):
        model, _ = real_trained_model
        result = infer_dense(model, DATA_DIR / "test_s2_t1.tif", block_size=64)
        assert result["prob_map"].shape == (100, 100)
        assert result["valid_count"] > 0

    def test_probability_range(self, real_trained_model):
        model, _ = real_trained_model
        result = infer_dense(model, DATA_DIR / "test_s2_t1.tif", block_size=64)
        probs = result["prob_map"][result["prob_map"] > 0]
        assert (probs >= 0).all() and (probs <= 1).all()

    def test_block_size_independent(self, real_trained_model):
        model, _ = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        r1 = infer_dense(model, t1, block_size=50)
        r2 = infer_dense(model, t1, block_size=100)
        np.testing.assert_array_equal(r1["prob_map"], r2["prob_map"])

    def test_output_geotiff(self, real_trained_model, tmp_path):
        model, _ = real_trained_model
        out = tmp_path / "prob.tif"
        infer_dense(model, DATA_DIR / "test_s2_t1.tif", output_path=out, block_size=64)
        assert out.exists() and out.stat().st_size > 0
        import rasterio
        with rasterio.open(out) as src:
            assert src.count == 2

    def test_water_mask_binary(self, real_trained_model):
        model, _ = real_trained_model
        result = infer_dense(model, DATA_DIR / "test_s2_t1.tif", block_size=64)
        assert set(np.unique(result["mask"])).issubset({0, 1, 255})

    def test_preserves_transform(self, real_trained_model):
        model, _ = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        result = infer_dense(model, t1, block_size=64)
        import rasterio
        with rasterio.open(t1) as src:
            assert result["crs"] == src.crs
            assert result["transform"] == src.transform


# ── Change Map ────────────────────────────────────────────────────────────

class TestChangeMap:
    def test_detects_increase(self):
        t1, t2 = np.zeros((50, 50), dtype=np.uint8), np.zeros((50, 50), dtype=np.uint8)
        t2[10:20, 10:20] = 1
        r = compute_change_map(t1, t2)
        assert r["stats"]["increase_pixels"] == 100
        assert r["stats"]["decrease_pixels"] == 0
        assert r["increase"].sum() == 100

    def test_detects_decrease(self):
        t1, t2 = np.zeros((50, 50), dtype=np.uint8), np.zeros((50, 50), dtype=np.uint8)
        t1[10:20, 10:20] = 1
        r = compute_change_map(t1, t2)
        assert r["stats"]["decrease_pixels"] == 100
        assert r["stats"]["increase_pixels"] == 0

    def test_detects_persistent(self):
        t1, t2 = np.zeros((50, 50), dtype=np.uint8), np.zeros((50, 50), dtype=np.uint8)
        t1[10:20, 10:20] = t2[10:20, 10:20] = 1
        r = compute_change_map(t1, t2)
        assert r["stats"]["persistent_pixels"] == 100

    def test_change_mask_values(self):
        t1, t2 = np.zeros((50, 50), dtype=np.uint8), np.zeros((50, 50), dtype=np.uint8)
        t1[0:10, 0:10] = 1          # loss
        t2[20:30, 20:30] = 1         # gain
        t1[40:50, 40:50] = t2[40:50, 40:50] = 1  # persistent
        r = compute_change_map(t1, t2)
        cm = r["change_mask"]
        assert (cm[0:10, 0:10] == 2).all()
        assert (cm[20:30, 20:30] == 1).all()
        assert (cm[40:50, 40:50] == 3).all()

    def test_stats_total(self):
        t1, t2 = np.zeros((50, 50), dtype=np.uint8), np.zeros((50, 50), dtype=np.uint8)
        t1[0:10, 0:10] = t2[10:20, 10:20] = 1
        r = compute_change_map(t1, t2)
        assert r["stats"]["increase_pixels"] + r["stats"]["decrease_pixels"] == r["stats"]["total_changed"]

    def test_no_change_when_identical(self):
        t = np.zeros((50, 50), dtype=np.uint8)
        assert compute_change_map(t, t)["stats"]["total_changed"] == 0

    def test_polygonize_semantic_labels(self):
        t1, t2 = np.zeros((100, 100), dtype=np.uint8), np.zeros((100, 100), dtype=np.uint8)
        t1[10:30, 10:30] = t2[10:30, 15:35] = 1
        change = compute_change_map(t1, t2)
        from rasterio.transform import from_origin
        import rasterio
        feats = polygonize_change_mask(change["change_mask"], from_origin(0, 100, 1, 1),
                                        rasterio.crs.CRS.from_epsg(4326), min_area_m2=10, pixel_area_m2=1)
        for f in feats:
            assert f["properties"]["change_type"] in ("water_increase", "water_decrease")
            assert f["properties"]["semantic_label"] == f["properties"]["change_type"]
            assert f["properties"]["area_m2"] > 0

    def test_polygonize_min_area_filter(self):
        t1, t2 = np.zeros((100, 100), dtype=np.uint8), np.zeros((100, 100), dtype=np.uint8)
        t1[10:13, 10:13] = t2[10:13, 13:16] = 1
        change = compute_change_map(t1, t2)
        from rasterio.transform import from_origin
        import rasterio
        feats = polygonize_change_mask(change["change_mask"], from_origin(0, 100, 1, 1),
                                        rasterio.crs.CRS.from_epsg(4326), min_area_m2=100, pixel_area_m2=1)
        assert len(feats) == 0

    def test_change_geotiff(self, tmp_path):
        t1, t2 = np.zeros((50, 50), dtype=np.uint8), np.zeros((50, 50), dtype=np.uint8)
        t2[10:20, 10:20] = 1
        change = compute_change_map(t1, t2)
        from rasterio.transform import from_origin
        import rasterio
        out = tmp_path / "change.tif"
        change_map_to_geotiff(change, out, from_origin(0, 50, 1, 1), rasterio.crs.CRS.from_epsg(4326))
        assert out.exists()

    def test_combine_multipolygon(self):
        from rasterio.transform import from_origin
        feats = [
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]}},
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[2,2],[3,2],[3,3],[2,3],[2,2]]]}},
        ]
        combined = combine_polygons_to_multipolygon(feats)
        assert combined["type"] == "MultiPolygon"
        assert len(combined["coordinates"]) == 2

    def test_combine_single_polygon(self):
        feats = [
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]}},
        ]
        combined = combine_polygons_to_multipolygon(feats)
        assert combined["type"] == "Polygon"

    def test_combine_empty(self):
        assert combine_polygons_to_multipolygon([]) is None


# ── Observations ──────────────────────────────────────────────────────────

class TestObservations:
    def test_real_coordinates(self, real_trained_model):
        model, _ = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        result = infer_dense(model, t1, block_size=64)
        import rasterio
        with rasterio.open(t1) as src:
            tr = src.transform
        obs = _extract_observations(result["prob_map"], result["mask"], tr, "EPSG:4326", "r", "T1", max_obs=10)
        for o in obs:
            lon, lat = o.geometry["coordinates"]
            assert 106.0 < lon < 107.0
            assert 29.0 < lat < 30.0

    def test_valid_properties(self, real_trained_model):
        model, _ = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        result = infer_dense(model, t1, block_size=64)
        import rasterio
        with rasterio.open(t1) as src:
            tr = src.transform
        obs = _extract_observations(result["prob_map"], result["mask"], tr, "EPSG:4326", "r", "T1", max_obs=5)
        for o in obs:
            assert o.observation_id.startswith("obs-t1-")
            assert o.coordinate_space == "geographic"

    def test_acquisition_timestamps(self, real_trained_model):
        model, _ = real_trained_model
        t1 = DATA_DIR / "test_s2_t1.tif"
        result = infer_dense(model, t1, block_size=64)
        import rasterio
        with rasterio.open(t1) as src:
            tr = src.transform
        obs = _extract_observations(result["prob_map"], result["mask"], tr, "EPSG:4326", "r", "T1",
                                     acquisition_start="2026-05-15T00:00:00Z",
                                     acquisition_end="2026-05-31T23:59:59Z",
                                     max_obs=3)
        for o in obs:
            assert o.temporal["start"] == "2026-05-15T00:00:00Z"
            assert o.temporal["end"] == "2026-05-31T23:59:59Z"

    def test_no_water(self):
        prob, mask = np.zeros((20, 20), dtype=np.float32), np.zeros((20, 20), dtype=np.uint8)
        from rasterio.transform import from_origin
        assert len(_extract_observations(prob, mask, from_origin(0, 20, 1, 1), "EPSG:4326", "r", "T1")) == 0

    def test_extract_acquisition_dates_from_metadata(self, tmp_path):
        """Write a GeoTIFF with acquisition metadata and verify extraction."""
        import rasterio
        arr = np.zeros((10, 10), dtype=np.float32)
        path = tmp_path / "tagged.tif"
        with rasterio.open(path, "w", driver="GTiff", height=10, width=10, count=1, dtype=np.float32) as dst:
            dst.write(arr, 1)
            dst.update_tags(ACQUISITION_DATE="2026-06-01")
        dates = _extract_acquisition_dates(path)
        assert dates is not None
        assert "2026-06-01" in dates


# ── Candidate Schema ──────────────────────────────────────────────────────

class TestCandidateSchema:
    def test_detection_candidate_semantic_label(self):
        dc = DetectionCandidate(
            candidate_id="test-001", observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            semantic_label="water_increase",
            area_m2=5000.0,
            geometry={"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]},
            score=0.85,
            rule_version="ml-b2-v1",
        )
        assert dc.semantic_label == "water_increase"
        assert dc.area_m2 == 5000.0

    def test_detection_candidate_quality_summary(self):
        qs = CandidateQualitySummary(mean_score=0.5, n_observations=100)
        assert qs.mean_score == 0.5
        assert qs.n_observations == 100

    def test_detection_candidate_serialization(self):
        dc = DetectionCandidate(
            candidate_id="test-002", observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            semantic_label="water_decrease",
            area_m2=2500.0,
            geometry={"type": "MultiPolygon", "coordinates": [[[[0,0],[1,0],[1,1],[0,1],[0,0]]], [[[2,2],[3,2],[3,3],[2,3],[2,2]]]]},
            score=0.75,
            evidence_refs=["change_mask.tif", "polygons.geojson"],
            rule_version="ml-b2-v1",
        )
        data = json.loads(dc.model_dump_json())
        dc2 = DetectionCandidate.model_validate(data)
        assert dc2.candidate_id == dc.candidate_id
        assert dc2.semantic_label == "water_decrease"
        assert dc2.area_m2 == 2500.0
        assert len(dc2.evidence_refs) == 2

    def test_observation_real_temporal(self):
        obs = Observation(
            observation_id="obs-t1-0000",
            perception_result_ref="run-test",
            source_asset_refs=["s2_t1"],
            source_task_type="anomaly_scoring",
            observation_type="anomaly_score",
            label="water",
            score=0.9,
            score_type="model_probability",
            geometry={"type": "Point", "coordinates": [106.5, 29.5]},
            temporal={"start": "2026-05-15T00:00:00Z", "end": "2026-05-31T23:59:59Z"},
            model_run_ref="run-test",
            coordinate_space="geographic",
        )
        assert obs.temporal["start"] == "2026-05-15T00:00:00Z"
        assert obs.geometry["coordinates"] == [106.5, 29.5]

    def test_detection_candidate_validation(self):
        with pytest.raises(Exception):
            DetectionCandidate(
                candidate_id="test-bad",
                observation_refs=["obs-1"],
                temporal_extent={},
                candidate_type="water_extent_change",
                score=1.5,  # must be <= 1.0
                rule_version="ml-b2-v1",
            )

    def test_detection_candidate_scored_edge_cases(self):
        dc = DetectionCandidate(
            candidate_id="test-003", observation_refs=["obs-1"],
            temporal_extent={"start": "2026-01", "end": "2026-06"},
            candidate_type="water_extent_change",
            score=0.0,
            rule_version="ml-b2-v1",
        )
        assert dc.score == 0.0


# ── End-to-End Pipeline ───────────────────────────────────────────────────

class TestWaterChangePipeline:
    def test_e2e(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        result = run_water_change(
            DATA_DIR / "test_s2_t1.tif", DATA_DIR / "test_s2_t2.tif",
            cp, tmp_path / "out", prob_threshold=0.4, block_size=64, min_area_m2=100,
        )
        assert result["perception_result"] is not None
        assert result["t1_result"]["mask"].shape == (100, 100)
        assert result["stats"]["total_pixels"] == 10000

    def test_produces_perception_result(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        result = run_water_change(
            DATA_DIR / "test_s2_t1.tif", DATA_DIR / "test_s2_t2.tif",
            cp, tmp_path / "out", prob_threshold=0.4, block_size=64, min_area_m2=100,
        )
        pr = result["perception_result"]
        assert isinstance(pr, PerceptionResult)
        assert pr.status.value == "succeeded_with_observations"

    def test_produces_detection_candidate(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        result = run_water_change(
            DATA_DIR / "test_s2_t1.tif", DATA_DIR / "test_s2_t2.tif",
            cp, tmp_path / "out", prob_threshold=0.4, block_size=64, min_area_m2=100,
        )
        dc = result["detection_candidate"]
        assert isinstance(dc, DetectionCandidate)
        assert dc.candidate_type == "water_extent_change"
        assert dc.geometry is not None
        assert dc.semantic_label is not None
        assert dc.area_m2 is not None and dc.area_m2 > 0

    def test_semantic_label_in_candidate(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        result = run_water_change(
            DATA_DIR / "test_s2_t1.tif", DATA_DIR / "test_s2_t2.tif",
            cp, tmp_path / "out", prob_threshold=0.4, block_size=64, min_area_m2=100,
        )
        dc = result["detection_candidate"]
        assert dc.semantic_label in ("water_increase", "water_decrease", "both", "other")

    def test_temporal_extent_uses_acquisition_dates(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        result = run_water_change(
            DATA_DIR / "test_s2_t1.tif", DATA_DIR / "test_s2_t2.tif",
            cp, tmp_path / "out", prob_threshold=0.4, block_size=64, min_area_m2=100,
            t1_acquisition="2026-05-15T00:00:00Z",
            t2_acquisition="2026-06-15T00:00:00Z",
        )
        dc = result["detection_candidate"]
        assert dc.temporal_extent["start"] == "2026-05-15T00:00:00Z"
        assert dc.temporal_extent["end"] == "2026-06-15T00:00:00Z"

    def test_output_files(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        out = tmp_path / "out"
        run_water_change(DATA_DIR / "test_s2_t1.tif", DATA_DIR / "test_s2_t2.tif",
                          cp, out, prob_threshold=0.4, block_size=64, min_area_m2=100)
        names = {f.name for f in out.iterdir()}
        assert "water_prob_t1.tif" in names
        assert "water_prob_t2.tif" in names
        assert "change_mask.tif" in names
        assert "change_polygons.geojson" in names
        assert "pipeline_result.json" in names

    def test_geojson_change_types(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        out = tmp_path / "out"
        run_water_change(DATA_DIR / "test_s2_t1.tif", DATA_DIR / "test_s2_t2.tif",
                          cp, out, prob_threshold=0.4, block_size=64, min_area_m2=100)
        data = json.loads((out / "change_polygons.geojson").read_text())
        for feat in data["features"]:
            assert feat["properties"]["change_type"] in ("water_increase", "water_decrease")
            assert feat["properties"]["semantic_label"] == feat["properties"]["change_type"]
            assert feat["properties"]["area_m2"] > 0

    def test_candidate_area_m2_nonzero(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        result = run_water_change(
            DATA_DIR / "test_s2_t1.tif", DATA_DIR / "test_s2_t2.tif",
            cp, tmp_path / "out", prob_threshold=0.4, block_size=64, min_area_m2=100,
        )
        assert result["detection_candidate"].area_m2 > 0

    def test_candidate_serialization(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        result = run_water_change(
            DATA_DIR / "test_s2_t1.tif", DATA_DIR / "test_s2_t2.tif",
            cp, tmp_path / "out", prob_threshold=0.4, block_size=64, min_area_m2=100,
        )
        pr, dc = result["perception_result"], result["detection_candidate"]
        pr_data = json.loads(pr.model_dump_json())
        PerceptionResult.model_validate(pr_data)
        dc_data = json.loads(dc.model_dump_json())
        dc2 = DetectionCandidate.model_validate(dc_data)
        assert dc2.candidate_id == dc.candidate_id
        assert dc2.semantic_label == dc.semantic_label
        assert dc2.area_m2 == dc.area_m2
        assert len(dc2.evidence_refs) > 0

    def test_different_thresholds(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        t1, t2 = DATA_DIR / "test_s2_t1.tif", DATA_DIR / "test_s2_t2.tif"
        r05 = run_water_change(t1, t2, cp, tmp_path / "t05", prob_threshold=0.5, block_size=64, min_area_m2=100)
        r07 = run_water_change(t1, t2, cp, tmp_path / "t07", prob_threshold=0.7, block_size=64, min_area_m2=100)
        assert r05["stats"]["total_changed"] >= r07["stats"]["total_changed"]

    def test_raises_on_missing_checkpoint(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            run_water_change(DATA_DIR / "test_s2_t1.tif", DATA_DIR / "test_s2_t2.tif",
                              checkpoint_path=tmp_path / "nonexistent.joblib")

    def test_block_size_determinism(self, tmp_path, real_trained_model):
        _, cp = real_trained_model
        t1, t2 = DATA_DIR / "test_s2_t1.tif", DATA_DIR / "test_s2_t2.tif"
        r1 = run_water_change(t1, t2, cp, tmp_path / "b32", prob_threshold=0.4, block_size=32, min_area_m2=100)
        r2 = run_water_change(t1, t2, cp, tmp_path / "b99", prob_threshold=0.4, block_size=99, min_area_m2=100)
        assert r1["stats"] == r2["stats"]
