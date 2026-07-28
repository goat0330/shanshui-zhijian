"""ML-B2: Water change detection pipeline — orchestrator.

Pipeline:
  S2 T1 GeoTIFF + S2 T2 GeoTIFF
    → Water probability rasters (T1, T2)
    → Binary water masks (T1, T2)
    → Change map (increase/decrease/persistent)
    → Polygons (GeoJSON)
    → DetectionCandidate (contract)
    → Observations with real pixel coordinates

Usage:
    python -m ml.water_change --t1 <path> --t2 <path> --checkpoint <path>
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ml.data_adapter import REAL_FEATURE_COLS
from ml.model import BaselineModel
from ml.infer_dense import infer_dense
from ml.change_map import (
    compute_change_map,
    polygonize_change_mask,
    combine_polygons_to_multipolygon,
    change_map_to_geotiff,
)
from core.schemas.contracts import ExecutionStatus, TaskType, ObservationType, ScoreType
from core.schemas.contracts.perception import Observation, PerceptionResult, QualityReport
from core.schemas.contracts.candidate import DetectionCandidate, CandidateQualitySummary


CHECKPOINT_PATH = Path(__file__).parent / "data" / "checkpoint.joblib"
OUTPUT_DIR_DEFAULT = Path(__file__).parent / "output"


def _extract_acquisition_dates(raster_path: Path) -> tuple[str, str] | None:
    """Extract acquisition start/end dates from GeoTIFF metadata.

    Falls back to None if no temporal metadata is found.
    """
    try:
        import rasterio
        with rasterio.open(raster_path) as src:
            tags = src.tags()
            acq_date = tags.get("ACQUISITION_DATE") or tags.get("acquisition_date") or tags.get("IMAGERY_DATE")
            if acq_date:
                return (acq_date, acq_date)
            start = tags.get("TIEMPO_INICIAL") or tags.get("start_datetime")
            end = tags.get("TIEMPO_FINAL") or tags.get("end_datetime")
            if start and end:
                return (start, end)
    except Exception:
        pass
    return None


def _format_timestamp(dt: datetime | None = None) -> str:
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_observations(
    prob_map: np.ndarray,
    mask: np.ndarray,
    transform,
    crs_name: str,
    run_id: str,
    time_label: str,
    acquisition_start: str | None = None,
    acquisition_end: str | None = None,
    max_obs: int = 500,
) -> list[Observation]:
    """Create Observations from probability map with real pixel coordinates.

    Args:
        prob_map: Water probability map (H, W).
        mask: Binary water mask (H, W).
        transform: Rasterio Affine transform.
        crs_name: CRS string like "EPSG:4326".
        run_id: Run identifier.
        time_label: "T1" or "T2".
        acquisition_start: Real acquisition start date (ISO).
        acquisition_end: Real acquisition end date (ISO).
        max_obs: Maximum number of observations to create.

    Returns:
        List of Observation instances.
    """
    temporal = {"start": acquisition_start or _format_timestamp(), "end": acquisition_end or _format_timestamp()}

    observations = []
    height, width = prob_map.shape
    rng = np.random.RandomState(42)

    water_pixels = np.argwhere(mask == 1)
    if len(water_pixels) == 0:
        return observations

    if len(water_pixels) > max_obs:
        idx = rng.choice(len(water_pixels), max_obs, replace=False)
        water_pixels = water_pixels[idx]

    for idx, (row, col) in enumerate(water_pixels):
        x, y = transform * (col, row)
        prob = float(prob_map[row, col])

        obs_id = f"obs-{time_label.lower()}-{idx:04d}-{uuid.uuid4().hex[:6]}"

        observations.append(Observation(
            observation_id=obs_id,
            perception_result_ref=run_id,
            source_asset_refs=[f"s2_{time_label.lower()}"],
            source_task_type=TaskType.ANOMALY_SCORING,
            observation_type=ObservationType.ANOMALY_SCORE,
            label="water" if mask[row, col] == 1 else "land",
            score=prob,
            score_type=ScoreType.MODEL_PROBABILITY,
            geometry={
                "type": "Point",
                "coordinates": [x, y],
            },
            geometry_crs=crs_name,
            temporal=temporal,
            quality=None,
            model_run_ref=run_id,
            coordinate_space="geographic",
            created_at=_format_timestamp(),
        ))

    return observations


def run_water_change(
    t1_path: Path,
    t2_path: Path,
    checkpoint_path: Path | None = None,
    output_dir: Path | None = None,
    prob_threshold: float = 0.5,
    block_size: int = 512,
    min_area_m2: float = 500.0,
    max_observations: int = 500,
    t1_acquisition: str | None = None,
    t2_acquisition: str | None = None,
    output_crs: str = "EPSG:4545",
) -> dict:
    """Run the full water change detection pipeline.

    Args:
        t1_path: Path to S2 T1 GeoTIFF.
        t2_path: Path to S2 T2 GeoTIFF.
        checkpoint_path: Path to model checkpoint.
        output_dir: Output directory.
        prob_threshold: Probability threshold for water mask.
        block_size: Block size for dense inference.
        min_area_m2: Minimum polygon area in m2.
        max_observations: Maximum Observations to create.
        t1_acquisition: T1 acquisition date (ISO). Auto-detected if None.
        t2_acquisition: T2 acquisition date (ISO). Auto-detected if None.
        output_crs: CRS for area computation.

    Returns:
        dict with keys: perception_result, detection_candidate, ...
    """
    cp = checkpoint_path or CHECKPOINT_PATH
    if not cp.exists():
        raise FileNotFoundError(f"Checkpoint not found: {cp}")

    out = Path(output_dir or OUTPUT_DIR_DEFAULT)
    out.mkdir(parents=True, exist_ok=True)
    run_id = f"ml-b2-{uuid.uuid4().hex[:12]}"

    print("=" * 60)
    print("ML-B2: Water Change Detection Pipeline")
    print("=" * 60)

    # 1. Load model
    print(f"\n[1/5] Loading model from {cp}")
    model = BaselineModel.load(cp)
    print(f"  Model: RandomForest ({model.n_estimators} trees, depth={model.max_depth})")
    print(f"  Features: {model.feature_names or REAL_FEATURE_COLS}")

    # Auto-detect acquisition dates
    t1_dates = _extract_acquisition_dates(t1_path)
    t2_dates = _extract_acquisition_dates(t2_path)
    t1_acq_start = t1_acquisition or (t1_dates[0] if t1_dates else _format_timestamp())
    t1_acq_end = t1_acquisition or (t1_dates[1] if t1_dates else _format_timestamp())
    t2_acq_start = t2_acquisition or (t2_dates[0] if t2_dates else _format_timestamp())
    t2_acq_end = t2_acquisition or (t2_dates[1] if t2_dates else _format_timestamp())
    print(f"  T1 acquisition: {t1_acq_start} / {t1_acq_end}")
    print(f"  T2 acquisition: {t2_acq_start} / {t2_acq_end}")

    # 2. Full-image inference on T1
    print(f"\n[2/5] Dense inference on T1: {t1_path}")
    t1_result = infer_dense(
        model, t1_path,
        output_path=out / "water_prob_t1.tif",
        block_size=block_size, threshold=prob_threshold,
    )
    print(f"  Valid pixels: {t1_result['valid_count']}/{t1_result['height'] * t1_result['width']}")
    print(f"  Water pixels: {int(t1_result['mask'].sum())}")

    # 3. Full-image inference on T2
    print(f"\n[3/5] Dense inference on T2: {t2_path}")
    t2_result = infer_dense(
        model, t2_path,
        output_path=out / "water_prob_t2.tif",
        block_size=block_size, threshold=prob_threshold,
    )
    print(f"  Valid pixels: {t2_result['valid_count']}/{t2_result['height'] * t2_result['width']}")
    print(f"  Water pixels: {int(t2_result['mask'].sum())}")

    # 4. Change detection
    print(f"\n[4/5] Change detection")
    change = compute_change_map(t1_result["mask"], t2_result["mask"])
    stats = change["stats"]
    print(f"  Increase:   {stats['increase_pixels']} px")
    print(f"  Decrease:   {stats['decrease_pixels']} px")
    print(f"  Persistent: {stats['persistent_pixels']} px")

    change_geotiff = change_map_to_geotiff(
        change, out / "change_mask.tif",
        transform=t1_result["transform"], crs=t1_result["crs"],
    )
    print(f"  Change mask: {change_geotiff}")

    # 5. Polygonization
    print(f"\n[5/5] Polygonization")
    polygons = polygonize_change_mask(
        change["change_mask"],
        transform=t1_result["transform"],
        crs=t1_result["crs"],
        min_area_m2=min_area_m2,
    )
    print(f"  Polygons: {len(polygons)}")

    geojson = {"type": "FeatureCollection", "features": polygons}
    geojson_path = out / "change_polygons.geojson"
    geojson_path.write_text(json.dumps(geojson, indent=2, ensure_ascii=False))
    print(f"  GeoJSON: {geojson_path}")

    # 6. Build Observations with real timestamps
    crs_name = str(t1_result["crs"]) if t1_result["crs"] else "EPSG:4326"
    observations_t1 = _extract_observations(
        t1_result["prob_map"], t1_result["mask"],
        t1_result["transform"], crs_name, run_id, "T1",
        acquisition_start=t1_acq_start, acquisition_end=t1_acq_end,
        max_obs=max_observations,
    )
    observations_t2 = _extract_observations(
        t2_result["prob_map"], t2_result["mask"],
        t2_result["transform"], crs_name, run_id, "T2",
        acquisition_start=t2_acq_start, acquisition_end=t2_acq_end,
        max_obs=max_observations,
    )
    all_observations = observations_t1 + observations_t2

    # 7. Build PerceptionResult
    quality = QualityReport(
        valid_pixel_ratio=(
            t1_result["valid_count"] / (t1_result["height"] * t1_result["width"])
            if t1_result["height"] * t1_result["width"] > 0 else 0
        ),
        nodata_ratio=0.0,
        finite_pixel_ratio=1.0,
        spatial_overlap_ratio=1.0,
        constant_pixel_ratio=0.0,
        sensor_comparability=True,
    )

    status = (
        ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS
        if all_observations else ExecutionStatus.SUCCEEDED_EMPTY
    )

    perception_result = PerceptionResult(
        perception_result_id=f"percep-{run_id}",
        inference_task_ref="ml-b2-water-change",
        task_spec_ref="ml-water-change-v1@0.1.0",
        run_id=run_id,
        status=status,
        observations=all_observations,
        artifact_refs=[
            str(change_geotiff),
            str(geojson_path),
            str(t1_result.get("output_path", "")),
            str(t2_result.get("output_path", "")),
        ],
        quality_report=quality,
        diagnostics={
            "model": "RandomForest",
            "n_estimators": model.n_estimators,
            "max_depth": model.max_depth,
            "prob_threshold": prob_threshold,
            "change_stats": stats,
            "n_polygons": len(polygons),
            "n_observations": len(all_observations),
        },
        started_at=_format_timestamp(),
        finished_at=_format_timestamp(),
    )

    # 8. Build DetectionCandidate with proper semantic labels and multi-polygon
    detection_candidate = None
    if stats["total_changed"] > 0 and polygons:
        combined_geom = combine_polygons_to_multipolygon(polygons)

        obs_refs = [o.observation_id for o in observations_t1[:100]]

        has_increase = any(f["properties"].get("change_type") == "water_increase" for f in polygons)
        has_decrease = any(f["properties"].get("change_type") == "water_decrease" for f in polygons)
        if has_increase and has_decrease:
            semantic_label = "both"
        elif has_increase:
            semantic_label = "water_increase"
        elif has_decrease:
            semantic_label = "water_decrease"
        else:
            semantic_label = "other"

        total_area = sum(f["properties"].get("area_m2", 0) for f in polygons)

        detection_candidate = DetectionCandidate(
            candidate_id=f"cand-{run_id}",
            observation_refs=obs_refs,
            temporal_extent={"start": t1_acq_start, "end": t2_acq_end},
            candidate_type="water_extent_change",
            semantic_label=semantic_label,
            area_m2=round(total_area, 1),
            geometry=combined_geom,
            score=min(1.0, stats["total_changed"] / max(stats["total_pixels"], 1)),
            quality_summary=CandidateQualitySummary(
                mean_score=min(1.0, float(np.mean([f["properties"].get("area_m2", 0) for f in polygons])) / 1e6) if polygons else 0.0,
                n_observations=len(all_observations),
                area_consistency=None,
                score_std=None,
            ),
            coordinate_space="geographic",
            evidence_refs=[
                str(change_geotiff),
                str(geojson_path),
            ],
            rule_version="ml-b2-v1",
        )

    # 9. Save outputs
    result_path = out / "pipeline_result.json"
    result_data = {
        "run_id": run_id,
        "perception_result_id": perception_result.perception_result_id,
        "status": perception_result.status.value,
        "n_observations": len(all_observations),
        "change_stats": stats,
        "n_polygons": len(polygons),
        "acquisition_t1": t1_acq_start,
        "acquisition_t2": t2_acq_end,
        "output_crs": output_crs,
        "outputs": {
            "t1_prob": str(t1_result.get("output_path", "")),
            "t2_prob": str(t2_result.get("output_path", "")),
            "change_mask": str(change_geotiff),
            "polygons": str(geojson_path),
        },
    }
    result_path.write_text(json.dumps(result_data, indent=2, default=str))

    print(f"\n{'=' * 60}")
    print(f"Pipeline complete.")
    print(f"  Run ID:       {run_id}")
    print(f"  Observations: {len(all_observations)} (T1: {len(observations_t1)}, T2: {len(observations_t2)})")
    print(f"  Polygons:     {len(polygons)}")
    print(f"  Change:       {stats['total_changed']} pixels")
    print(f"  Semantic:     {semantic_label if detection_candidate else 'N/A'}")
    print(f"  Total area:   {total_area:.0f} m2")
    print(f"  T1 acq:       {t1_acq_start}")
    print(f"  T2 acq:       {t2_acq_end}")
    print(f"  Output:       {out}")
    print(f"{'=' * 60}")

    return {
        "perception_result": perception_result,
        "detection_candidate": detection_candidate,
        "t1_result": t1_result,
        "t2_result": t2_result,
        "change_map": change,
        "polygons": polygons,
        "stats": stats,
        "run_id": run_id,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ML-B2 Water Change Detection")
    parser.add_argument("--t1", required=True, help="S2 T1 GeoTIFF path")
    parser.add_argument("--t2", required=True, help="S2 T2 GeoTIFF path")
    parser.add_argument("--checkpoint", default=None, help="Model checkpoint path")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    parser.add_argument("--threshold", type=float, default=0.5, help="Probability threshold")
    parser.add_argument("--min-area", type=float, default=500.0, help="Min polygon area (m2)")
    parser.add_argument("--t1-date", default=None, help="T1 acquisition date (ISO)")
    parser.add_argument("--t2-date", default=None, help="T2 acquisition date (ISO)")
    parser.add_argument("--crs", default="EPSG:4545", help="Output CRS for area computation")
    args = parser.parse_args()

    result = run_water_change(
        t1_path=Path(args.t1),
        t2_path=Path(args.t2),
        checkpoint_path=Path(args.checkpoint) if args.checkpoint else None,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        prob_threshold=args.threshold,
        min_area_m2=args.min_area,
        t1_acquisition=args.t1_date,
        t2_acquisition=args.t2_date,
        output_crs=args.crs,
    )

    pr = result["perception_result"]
    dc = result["detection_candidate"]
    print(f"\nPerceptionResult:  {pr.perception_result_id} ({pr.status.value})")
    print(f"DetectionCandidate: {dc.candidate_id if dc else 'None'}")
    if dc:
        print(f"  semantic_label:  {dc.semantic_label}")
        print(f"  area_m2:         {dc.area_m2}")
        print(f"  temporal_extent: {dc.temporal_extent}")
        print(f"  evidence_refs:   {len(dc.evidence_refs)}")


if __name__ == "__main__":
    main()
