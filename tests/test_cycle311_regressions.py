"""Regression gates added by the Cycle 3.1.1 overlay."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import numpy as np
import pytest


def _write_raster(path: Path, array: np.ndarray, transform, crs="EPSG:4326", descriptions=None):
    import rasterio

    if array.ndim == 2:
        array = array[np.newaxis, ...]
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=array.shape[1],
        width=array.shape[2],
        count=array.shape[0],
        dtype=str(array.dtype),
        crs=crs,
        transform=transform,
        nodata=-9999 if np.issubdtype(array.dtype, np.floating) else 255,
    ) as dst:
        dst.write(array)
        for index, description in enumerate(descriptions or [], start=1):
            dst.set_band_description(index, description)


def test_real_mode_missing_files_is_fail_closed(tmp_path):
    from ml.data_adapter import load_data

    with pytest.raises(FileNotFoundError, match="--real was requested"):
        load_data(
            use_real=True,
            s2_path=tmp_path / "missing-s2.tif",
            jrc_path=tmp_path / "missing-jrc.tif",
        )


def test_jrc_label_is_reprojected_to_exact_reference_grid(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    from ml.data_adapter import _reproject_label_to_reference

    s2_path = tmp_path / "s2.tif"
    label_path = tmp_path / "jrc.tif"
    _write_raster(
        s2_path,
        np.zeros((6, 32, 32), dtype=np.float32),
        from_origin(0, 320, 10, 10),
        crs="EPSG:3857",
        descriptions=["blue", "green", "red", "nir", "swir1", "swir2"],
    )
    label = np.zeros((16, 16), dtype=np.float32)
    label[:, 8:] = 100
    _write_raster(label_path, label, from_origin(0, 320, 20, 20), crs="EPSG:3857")

    with rasterio.open(s2_path) as reference:
        aligned = _reproject_label_to_reference(label_path, reference)
    assert aligned.shape == (32, 32)
    assert np.nanmean(aligned[:, :15]) == pytest.approx(0.0)
    assert np.nanmean(aligned[:, 17:]) == pytest.approx(100.0)


def test_change_map_preserves_nodata():
    from ml.change_map import compute_change_map

    t1 = np.array([[0, 1, 255], [0, 1, 0]], dtype=np.uint8)
    t2 = np.array([[1, 0, 1], [0, 1, 255]], dtype=np.uint8)
    result = compute_change_map(t1, t2)
    assert result["change_mask"].tolist() == [[1, 2, 255], [0, 3, 255]]
    assert result["stats"]["nodata_pixels"] == 2
    assert result["stats"]["valid_pixels"] == 4


def test_polygonisation_records_requested_area_crs():
    import rasterio
    from rasterio.transform import from_origin
    from ml.change_map import polygonize_change_mask

    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[2:8, 2:8] = 1
    features = polygonize_change_mask(
        mask,
        from_origin(106.5, 29.6, 0.0001, 0.0001),
        rasterio.crs.CRS.from_epsg(4326),
        min_area_m2=1,
        area_crs="EPSG:4545",
    )
    assert features
    assert features[0]["properties"]["area_crs"] == "EPSG:4545"
    assert features[0]["properties"]["area_m2"] > 0


def test_full_no_change_pipeline_succeeds_empty(tmp_path, monkeypatch):
    from rasterio.transform import from_origin
    import ml.water_change as water_change

    t1 = tmp_path / "t1.tif"
    t2 = tmp_path / "t2.tif"
    array = np.ones((6, 8, 8), dtype=np.float32)
    descriptions = ["blue", "green", "red", "nir", "swir1", "swir2"]
    _write_raster(t1, array, from_origin(106.5, 29.6, 0.0001, 0.0001), descriptions=descriptions)
    _write_raster(t2, array, from_origin(106.5, 29.6, 0.0001, 0.0001), descriptions=descriptions)
    checkpoint = tmp_path / "model.joblib"
    checkpoint.write_bytes(b"placeholder")

    class DummyModel:
        n_estimators = 1
        max_depth = 1
        feature_names = list(water_change.REAL_FEATURE_COLS)

    monkeypatch.setattr(water_change.BaselineModel, "load", classmethod(lambda cls, path: DummyModel()))

    def fake_infer(model, raster_path, output_path=None, **kwargs):
        import rasterio

        with rasterio.open(raster_path) as src:
            shape = (src.height, src.width)
            return {
                "prob_map": np.zeros(shape, dtype=np.float32),
                "mask": np.zeros(shape, dtype=np.uint8),
                "valid_map": np.ones(shape, dtype=bool),
                "crs": src.crs,
                "transform": src.transform,
                "bounds": src.bounds,
                "height": src.height,
                "width": src.width,
                "valid_count": src.height * src.width,
                "nodata_count": 0,
                "output_path": str(output_path),
            }

    monkeypatch.setattr(water_change, "infer_dense", fake_infer)
    result = water_change.run_water_change(
        t1,
        t2,
        checkpoint_path=checkpoint,
        output_dir=tmp_path / "out",
        min_area_m2=1,
        t1_acquisition="2026-05-01T00:00:00Z",
        t2_acquisition="2026-06-01T00:00:00Z",
    )
    assert result["stats"]["total_changed"] == 0
    assert result["detection_candidate"] is None
    assert result["perception_result"].status.value == "succeeded_empty"
    payload = json.loads((tmp_path / "out/pipeline_result.json").read_text(encoding="utf-8"))
    assert payload["total_area_m2"] == 0.0
    assert payload["semantic_label"] is None


def test_candidate_store_uses_one_file_backed_database(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKBENCH_DB_PATH", str(tmp_path / "workbench.db"))
    import apps.workbench_api.db as db
    import apps.workbench_api.candidate_store as candidate_store

    importlib.reload(db)
    importlib.reload(candidate_store)
    inserted = candidate_store.seed_demo_candidates(count=3, replace=True)
    first, first_total = candidate_store.list_candidates()
    second, second_total = candidate_store.list_candidates()
    assert inserted == 3
    assert first_total == second_total == 3
    assert [row["candidate_id"] for row in first] == [row["candidate_id"] for row in second]
    assert candidate_store.get_candidate_dict("CAND-0002")["candidate_track_id"] == "TRACK-0002"


def test_real_run_service_does_not_fall_back_to_mock(monkeypatch):
    import apps.workbench_api.manifest_service as manifest_service
    import apps.workbench_api.real_service as real_service

    monkeypatch.setattr(manifest_service, "get_runs", lambda execution_status=None: [])
    monkeypatch.setattr(manifest_service, "get_run", lambda run_id: None)
    monkeypatch.setattr(manifest_service, "get_artifact", lambda artifact_id: None)
    assert real_service.get_runs() == []
    assert real_service.get_run("missing") is None
    assert real_service.get_artifact("missing") is None
