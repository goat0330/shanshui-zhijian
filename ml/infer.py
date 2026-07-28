"""
ML Baseline — Inference script.

Usage:
  python -m ml.infer                                # uses test.csv first row
  python -m ml.infer --input ml/data/sample.csv     # custom CSV input

Produces:
  - Console output: PerceptionResult with Observations
  - ml/data/inference_result.json: serialized PerceptionResult
  - ml/data/detection_result.json: serialized DetectionCandidate (via ObservationAggregator)
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ml.data_adapter import FEATURE_COLS, WaterQualityDataset
from ml.model import BaselineModel
from core.schemas.contracts import (
    ExecutionStatus,
    TaskType,
    ObservationType,
    ScoreType,
)
from core.schemas.contracts.perception import Observation, PerceptionResult, QualityReport
from core.schemas.contracts.candidate import DetectionCandidate, CandidateQualitySummary
from tools.observation_aggregator import ObservationAggregator


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
) -> Observation:
    obs_id = f"ml-inf-{obs_index:04d}-{uuid.uuid4().hex[:8]}"
    label = "water_anomaly" if pred_class == 1 else "normal_water"

    geometry = {
        "type": "Point",
        "coordinates": [106.5, 29.5],
    }

    temporal = {"start": _now_iso(), "end": _now_iso()}

    return Observation(
        observation_id=obs_id,
        perception_result_ref=run_id,
        source_asset_refs=["ml-inference-input"],
        source_task_type=TaskType.ANOMALY_SCORING,
        observation_type=ObservationType.ANOMALY_SCORE,
        label=label,
        score=pred_prob,
        score_type=ScoreType.MODEL_PROBABILITY,
        geometry=geometry,
        geometry_crs="EPSG:4326",
        bbox=[106.4, 29.4, 106.6, 29.6],
        temporal=temporal,
        quality=None,
        model_run_ref=run_id,
        coordinate_space="geographic",
        created_at=_now_iso(),
    )


def run_inference(input_path: str | None = None) -> tuple[PerceptionResult, DetectionCandidate]:
    if not CHECKPOINT_PATH.exists():
        raise FileNotFoundError(f"Checkpoint not found: {CHECKPOINT_PATH}. Run 'python -m ml.train' first.")

    model = BaselineModel.load(CHECKPOINT_PATH)

    if input_path:
        df = pd.read_csv(input_path)
    else:
        ds = WaterQualityDataset()
        df, _ = ds.load_split("test")
        df = df.head(1)

    if FEATURE_COLS[0] not in df.columns:
        raise ValueError(f"Input CSV must contain columns: {FEATURE_COLS}")

    X = df[FEATURE_COLS]
    y_pred = model.predict(X)
    y_prob = model.predict_proba(X)[:, 1]

    run_id = f"run-ml-baseline-{uuid.uuid4().hex[:12]}"
    result_id = f"percep-{run_id}"

    observations = [
        _build_observation(
            features=row.to_dict(),
            pred_class=int(y_pred[i]),
            pred_prob=round(float(y_prob[i]), 4),
            obs_index=i,
            run_id=run_id,
        )
        for i, (_, row) in enumerate(X.iterrows())
    ]

    quality = QualityReport(
        valid_pixel_ratio=1.0,
        nodata_ratio=0.0,
        finite_pixel_ratio=1.0,
        spatial_overlap_ratio=1.0,
        constant_pixel_ratio=0.0,
        sensor_comparability=True,
    )

    perception_result = PerceptionResult(
        perception_result_id=result_id,
        inference_task_ref="smoke-test-baseline",
        task_spec_ref="ml-anomaly-scoring-v1@0.1.0",
        run_id=run_id,
        status=ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS,
        observations=observations,
        artifact_refs=[],
        quality_report=quality,
        diagnostics={
            "model": "RandomForest",
            "n_estimators": model.n_estimators,
            "max_depth": model.max_depth,
            "n_samples": len(observations),
        },
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    aggregator = ObservationAggregator()
    detection_candidate = aggregator.aggregate(
        observations=observations,
        candidate_type="water_anomaly",
    )

    return perception_result, detection_candidate


def main():
    import argparse

    parser = argparse.ArgumentParser(description="ML Baseline Inference")
    parser.add_argument("--input", type=str, default=None, help="Path to input CSV")
    args = parser.parse_args()

    print("=" * 50)
    print("ML Baseline: Inference")
    print("=" * 50)

    try:
        perception_result, detection_candidate = run_inference(args.input)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    print(f"\n--- PerceptionResult ---")
    print(f"  ID:      {perception_result.perception_result_id}")
    print(f"  Run ID:  {perception_result.run_id}")
    print(f"  Status:  {perception_result.status.value}")
    print(f"  Obs:     {len(perception_result.observations)}")
    for obs in perception_result.observations:
        prob = obs.score
        print(f"    [{obs.observation_id}] {obs.label} (p={prob:.4f})")

    print(f"\n--- DetectionCandidate ---")
    print(f"  ID:           {detection_candidate.candidate_id}")
    print(f"  Type:         {detection_candidate.candidate_type}")
    print(f"  Score:        {detection_candidate.score:.4f}")
    print(f"  Observations: {len(detection_candidate.observation_refs)}")
    if detection_candidate.quality_summary:
        qs = detection_candidate.quality_summary
        print(f"  Mean score:   {qs.mean_score:.4f}")
        print(f"  Score std:    {qs.score_std or 'N/A'}")

    result_data = json.loads(perception_result.model_dump_json())
    INFERENCE_RESULT_PATH.write_text(json.dumps(result_data, indent=2, default=str))
    print(f"\nPerceptionResult saved: {INFERENCE_RESULT_PATH}")

    candidate_data = json.loads(detection_candidate.model_dump_json())
    DETECTION_RESULT_PATH.write_text(json.dumps(candidate_data, indent=2, default=str))
    print(f"DetectionCandidate saved: {DETECTION_RESULT_PATH}")

    return perception_result, detection_candidate


if __name__ == "__main__":
    main()
