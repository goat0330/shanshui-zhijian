"""ML-B1 — Inference script.

Usage:
    python -m ml.infer                                  # synthetic CSV (smoke)
    python -m ml.infer --geotiff <path>                 # real GeoTIFF
    python -m ml.infer --input <path>                   # custom CSV
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ml.data_adapter import REAL_FEATURE_COLS, SYNTH_FEATURE_COLS, DATA_DIR
from ml.model import BaselineModel
from core.schemas.contracts import ExecutionStatus, TaskType, ObservationType, ScoreType
from core.schemas.contracts.perception import Observation, PerceptionResult, QualityReport
from core.schemas.contracts.candidate import DetectionCandidate

CHECKPOINT_PATH = Path(__file__).parent / "data" / "checkpoint.joblib"
INFERENCE_RESULT_PATH = Path(__file__).parent / "data" / "inference_result.json"
DETECTION_RESULT_PATH = Path(__file__).parent / "data" / "detection_result.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_observation(
    features: dict,
    pred_class: int,
    pred_prob: float,
    obs_index: int,
    run_id: str,
    is_synthetic: bool = True,
) -> Observation:
    obs_id = f"ml-b1-{obs_index:04d}-{uuid.uuid4().hex[:8]}"
    label = "water_anomaly" if pred_class == 1 else "normal_water"

    geometry = {
        "type": "Point",
        "coordinates": [106.5, 29.5],
    }
    temporal = {"start": _now_iso(), "end": _now_iso()}

    if is_synthetic:
        geometry["synthetic"] = True
        temporal["synthetic"] = True

    return Observation(
        observation_id=obs_id,
        perception_result_ref=run_id,
        source_asset_refs=["synthetic-ml-input" if is_synthetic else "real-s2-t1"],
        source_task_type=TaskType.ANOMALY_SCORING,
        observation_type=ObservationType.ANOMALY_SCORE,
        label=label,
        score=pred_prob,
        score_type=ScoreType.MODEL_PROBABILITY,
        geometry=geometry,
        geometry_crs="EPSG:4326",
        bbox=[106.4, 29.4, 106.6, 29.6],
        temporal=temporal,
        quality={"is_synthetic": is_synthetic},
        model_run_ref=run_id,
        coordinate_space="geographic",
        created_at=_now_iso(),
    )


def infer_on_csv(
    input_path: str | None,
    model: BaselineModel,
    run_id: str,
) -> tuple[list[Observation], list[dict]]:
    if input_path:
        df = pd.read_csv(input_path)
    else:
        df, _ = pd.read_csv(DATA_DIR / "test.csv"), None
        if df is None or len(df) == 0:
            raise FileNotFoundError("No test.csv available for inference")
        df = df.head(10)

    # Detect feature set
    if "ndwi" in df.columns and "turbidity_index" in df.columns:
        X = df[SYNTH_FEATURE_COLS]
    elif "ndwi" in df.columns:
        X = df[[c for c in REAL_FEATURE_COLS if c in df.columns]]
    else:
        raise ValueError(f"Unknown feature columns in input CSV")

    y_pred = model.predict(X)
    y_prob = model.predict_proba(X)[:, 1]

    raw_features = []
    observations = []
    for i, (_, row) in enumerate(X.iterrows()):
        feat = row.to_dict()
        obs = _build_observation(
            features=feat,
            pred_class=int(y_pred[i]),
            pred_prob=round(float(y_prob[i]), 4),
            obs_index=i,
            run_id=run_id,
            is_synthetic=True,
        )
        observations.append(obs)
        raw_features.append(feat)

    return observations, raw_features


def infer_on_geotiff(
    geotiff_path: Path,
    model: BaselineModel,
    run_id: str,
    max_pixels: int = 1000,
) -> tuple[list[Observation], np.ndarray]:
    """Run inference directly on a GeoTIFF raster."""
    import rasterio
    from ml.data_adapter import _compute_indices

    with rasterio.open(geotiff_path) as src:
        array = src.read().astype(np.float32)
        height, width = src.height, src.width
        transform = src.transform
        crs = src.crs
        band_names = list(src.descriptions) if src.descriptions and any(src.descriptions) else [f"b{i+1}" for i in range(array.shape[0])]

    has_nir = any("nir" in b.lower() or "b8" in b.lower() or b == "nir" for b in band_names)
    has_green = any("green" in b.lower() or "b3" in b.lower() or b == "green" for b in band_names)
    has_red = any("red" in b.lower() or "b4" in b.lower() or b == "red" for b in band_names)
    has_swir1 = any("swir1" in b.lower() or "b11" in b.lower() or b == "swir1" for b in band_names)

    uses_indices = has_nir and has_green and has_red

    rng = np.random.RandomState(42)
    valid_mask = np.isfinite(array).all(axis=0)
    coords = np.argwhere(valid_mask)
    if len(coords) > max_pixels:
        idx = rng.choice(len(coords), max_pixels, replace=False)
        coords = coords[idx]

    observations = []
    prob_map = np.zeros((height, width), dtype=np.float32)

    if uses_indices:
        bmap = {}
        for i, b in enumerate(band_names):
            bl = b.lower()
            if "blue" in bl or "b2" in bl:
                bmap["blue"] = i
            elif "green" in bl or "b3" in bl:
                bmap["green"] = i
            elif "red" in bl or "b4" in bl:
                bmap["red"] = i
            elif "nir" in bl or "b8" in bl:
                bmap["nir"] = i
            elif "swir1" in bl or "swir" in bl and "1" in bl or "b11" in bl:
                bmap["swir1"] = i
            elif "swir2" in bl or "b12" in bl:
                bmap["swir2"] = i

        indices = _compute_indices(array, bmap)

        for y, x in coords:
            row = {
                "ndwi": indices["ndwi"][y, x],
                "mndwi": indices["mndwi"][y, x],
                "ndvi": indices["ndvi"][y, x],
            }
            for bname, bidx in bmap.items():
                row[bname] = float(array[bidx, y, x])

            feat_df = pd.DataFrame([row])
            feat_cols = [c for c in REAL_FEATURE_COLS if c in feat_df.columns]
            pred = model.predict(feat_df[feat_cols])[0]
            prob = model.predict_proba(feat_df[feat_cols])[0, 1]

            prob_map[y, x] = prob
            obs = _build_observation(row, int(pred), round(float(prob), 4), len(observations), run_id, is_synthetic=False)
            observations.append(obs)
    else:
        for y, x in coords:
            row = {f"band_{i}": float(array[i, y, x]) for i in range(array.shape[0])}
            feat_df = pd.DataFrame([row])
            pred = model.predict(feat_df)[0]
            prob = model.predict_proba(feat_df)[0, 1]
            prob_map[y, x] = prob
            obs = _build_observation(row, int(pred), round(float(prob), 4), len(observations), run_id, is_synthetic=False)
            observations.append(obs)

    return observations, prob_map


def run_inference(
    input_path: str | None = None,
    geotiff_path: str | None = None,
    checkpoint_path: Path | None = None,
) -> tuple[PerceptionResult, DetectionCandidate | None]:
    cp = checkpoint_path or CHECKPOINT_PATH
    if not cp.exists():
        raise FileNotFoundError(f"Checkpoint not found: {cp}. Run 'python -m ml.train' first.")

    model = BaselineModel.load(cp)
    run_id = f"run-ml-b1-{uuid.uuid4().hex[:12]}"
    result_id = f"percep-{run_id}"

    if geotiff_path:
        observations, _ = infer_on_geotiff(Path(geotiff_path), model, run_id)
    else:
        observations, _ = infer_on_csv(input_path, model, run_id)

    quality = QualityReport(
        valid_pixel_ratio=1.0, nodata_ratio=0.0, finite_pixel_ratio=1.0,
        spatial_overlap_ratio=1.0, constant_pixel_ratio=0.0, sensor_comparability=True,
    )

    status = (
        ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS
        if observations else ExecutionStatus.SUCCEEDED_EMPTY
    )

    perception_result = PerceptionResult(
        perception_result_id=result_id,
        inference_task_ref="ml-b1-inference",
        task_spec_ref="ml-water-classifier-v1@0.1.0",
        run_id=run_id,
        status=status,
        observations=observations,
        artifact_refs=[],
        quality_report=quality,
        diagnostics={
            "model": "RandomForest",
            "n_estimators": model.n_estimators,
            "max_depth": model.max_depth,
            "n_samples": len(observations),
            "data_source": "geotiff" if geotiff_path else "csv",
        },
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    anomaly_obs = [o for o in observations if o.label == "water_anomaly"]
    if anomaly_obs:
        from tools.observation_aggregator import ObservationAggregator
        detection_candidate = ObservationAggregator().aggregate(
            observations=anomaly_obs, candidate_type="water_anomaly",
        )
    else:
        detection_candidate = None

    return perception_result, detection_candidate


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ML-B1 Inference")
    parser.add_argument("--input", type=str, default=None, help="Path to input CSV")
    parser.add_argument("--geotiff", type=str, default=None, help="Path to GeoTIFF for raster inference")
    args = parser.parse_args()

    print("=" * 50)
    print("ML-B1: Inference")
    print("=" * 50)

    try:
        pr, dc = run_inference(args.input, args.geotiff)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    print(f"\n--- PerceptionResult ---")
    print(f"  ID:      {pr.perception_result_id}")
    print(f"  Status:  {pr.status.value}")
    print(f"  Obs:     {len(pr.observations)}")
    for obs in pr.observations[:5]:
        print(f"    [{obs.observation_id}] {obs.label} (p={obs.score:.4f})")
    if len(pr.observations) > 5:
        print(f"    ... and {len(pr.observations) - 5} more")

    if dc:
        print(f"\n--- DetectionCandidate ---")
        print(f"  ID:    {dc.candidate_id}")
        print(f"  Type:  {dc.candidate_type}")
        print(f"  Score: {dc.score:.4f}")
        print(f"  Obs:   {len(dc.observation_refs)}")
    else:
        print(f"\n--- No anomalies detected ---")

    result_data = json.loads(pr.model_dump_json())
    INFERENCE_RESULT_PATH.write_text(json.dumps(result_data, indent=2, default=str))
    print(f"\nPerceptionResult saved: {INFERENCE_RESULT_PATH}")

    if dc:
        candidate_data = json.loads(dc.model_dump_json())
        DETECTION_RESULT_PATH.write_text(json.dumps(candidate_data, indent=2, default=str))
        print(f"DetectionCandidate saved: {DETECTION_RESULT_PATH}")


if __name__ == "__main__":
    main()
