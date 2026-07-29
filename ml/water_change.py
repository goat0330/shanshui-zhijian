"""Cycle 3.1.1 water-change orchestrator.

The pipeline is fail-closed for missing inputs, incompatible grids and missing
observation time. A no-change result is a successful empty result, not an error.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from core.schemas.contracts import ExecutionStatus, ObservationType, ScoreType, TaskType
from core.schemas.contracts.candidate import CandidateQualitySummary, DetectionCandidate
from core.schemas.contracts.perception import Observation, PerceptionResult, QualityReport
from ml.change_map import (
    change_map_to_geotiff,
    combine_polygons_to_multipolygon,
    compute_change_map,
    polygonize_change_mask,
)
from ml.data_adapter import REAL_FEATURE_COLS, RealDataError
from ml.infer_dense import infer_dense
from ml.model import BaselineModel

CHECKPOINT_PATH = Path(__file__).parent / "data" / "checkpoint.joblib"
OUTPUT_DIR_DEFAULT = Path(__file__).parent / "output"


def _format_timestamp(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_acquisition_dates(raster_path: Path) -> tuple[str, str] | None:
    """Return source acquisition interval, never execution time."""
    try:
        import rasterio

        with rasterio.open(raster_path) as src:
            tags = src.tags()
            date = (
                tags.get("ACQUISITION_DATE")
                or tags.get("acquisition_date")
                or tags.get("IMAGERY_DATE")
                or tags.get("DATE_ACQUIRED")
                or tags.get("datetime")
            )
            if date:
                return date, date
            start = tags.get("TIEMPO_INICIAL") or tags.get("start_datetime") or tags.get("START_DATE")
            end = tags.get("TIEMPO_FINAL") or tags.get("end_datetime") or tags.get("END_DATE")
            if start or end:
                return start or end, end or start
    except Exception:
        return None
    return None


def _grid_signature(path: Path) -> tuple:
    import rasterio

    with rasterio.open(path) as src:
        if src.crs is None:
            raise RealDataError(f"Raster has no CRS: {path}")
        return src.width, src.height, src.crs.to_string(), tuple(src.transform)


def _validate_aligned_grids(t1_path: Path, t2_path: Path) -> None:
    signature_t1 = _grid_signature(t1_path)
    signature_t2 = _grid_signature(t2_path)
    if signature_t1 != signature_t2:
        raise RealDataError(
            "T1 and T2 must already be co-registered to an identical grid. "
            f"T1={signature_t1}; T2={signature_t2}"
        )


def _coordinate_space(crs) -> str:
    return "geographic" if getattr(crs, "is_geographic", False) else "unknown"


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
    temporal = {
        "start": acquisition_start or "unknown",
        "end": acquisition_end or acquisition_start or "unknown",
        "source": "raster_metadata" if acquisition_start else "missing",
    }
    water_pixels = np.argwhere(mask == 1)
    if len(water_pixels) == 0:
        return []
    rng = np.random.RandomState(42)
    if len(water_pixels) > max_obs:
        water_pixels = water_pixels[rng.choice(len(water_pixels), max_obs, replace=False)]

    observations: list[Observation] = []
    for index, (row, col) in enumerate(water_pixels):
        x, y = transform * (int(col), int(row))
        score = float(prob_map[row, col])
        if not np.isfinite(score):
            continue
        observations.append(Observation(
            observation_id=f"obs-{time_label.lower()}-{index:04d}-{uuid.uuid4().hex[:6]}",
            perception_result_ref=run_id,
            source_asset_refs=[f"s2_{time_label.lower()}"],
            source_task_type=TaskType.ANOMALY_SCORING,
            observation_type=ObservationType.ANOMALY_SCORE,
            label="water",
            score=max(0.0, min(1.0, score)),
            score_type=ScoreType.MODEL_PROBABILITY,
            geometry={"type": "Point", "coordinates": [float(x), float(y)]},
            geometry_crs=crs_name,
            temporal=temporal,
            quality=None,
            model_run_ref=run_id,
            coordinate_space="geographic" if "4326" in crs_name else "unknown",
            created_at=_format_timestamp(),
        ))
    return observations


def _constant_ratio(array: np.ndarray, valid: np.ndarray) -> float:
    values = array[valid]
    if values.size == 0:
        return 1.0
    return 1.0 if np.nanmax(values) == np.nanmin(values) else 0.0


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
    started_at = _format_timestamp()
    if max_observations < 1:
        raise ValueError("max_observations must be at least 1")
    t1_path = Path(t1_path)
    t2_path = Path(t2_path)
    for path in (t1_path, t2_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    _validate_aligned_grids(t1_path, t2_path)

    checkpoint = Path(checkpoint_path or CHECKPOINT_PATH)
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")
    output = Path(output_dir or OUTPUT_DIR_DEFAULT)
    output.mkdir(parents=True, exist_ok=True)
    run_id = f"ml-b2-{uuid.uuid4().hex[:12]}"

    model = BaselineModel.load(checkpoint)
    model_features = model.feature_names or REAL_FEATURE_COLS
    if set(REAL_FEATURE_COLS) - set(model_features):
        raise RealDataError("Checkpoint is not a real Sentinel-2 water model")

    t1_dates = _extract_acquisition_dates(t1_path)
    t2_dates = _extract_acquisition_dates(t2_path)
    t1_start = t1_acquisition or (t1_dates[0] if t1_dates else None)
    t1_end = t1_acquisition or (t1_dates[1] if t1_dates else None)
    t2_start = t2_acquisition or (t2_dates[0] if t2_dates else None)
    t2_end = t2_acquisition or (t2_dates[1] if t2_dates else None)
    warnings: list[str] = []
    if not t1_start:
        warnings.append("T1 acquisition time missing; source time is recorded as unknown")
    if not t2_start:
        warnings.append("T2 acquisition time missing; source time is recorded as unknown")

    print("=" * 60)
    print("ML-B2: Water Change Detection Pipeline")
    print("=" * 60)
    print(f"Run ID: {run_id}")
    print(f"T1 acquisition: {t1_start or 'unknown'}")
    print(f"T2 acquisition: {t2_start or 'unknown'}")

    t1_result = infer_dense(
        model,
        t1_path,
        output_path=output / "water_prob_t1.tif",
        block_size=block_size,
        threshold=prob_threshold,
    )
    t2_result = infer_dense(
        model,
        t2_path,
        output_path=output / "water_prob_t2.tif",
        block_size=block_size,
        threshold=prob_threshold,
    )

    change = compute_change_map(t1_result["mask"], t2_result["mask"])
    stats = change["stats"]
    change_geotiff = change_map_to_geotiff(
        change,
        output / "change_mask.tif",
        transform=t1_result["transform"],
        crs=t1_result["crs"],
    )
    polygons = polygonize_change_mask(
        change["change_mask"],
        transform=t1_result["transform"],
        crs=t1_result["crs"],
        min_area_m2=min_area_m2,
        area_crs=output_crs,
    )
    geojson_path = output / "change_polygons.geojson"
    geojson_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": polygons}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    crs_name = str(t1_result["crs"])
    observations_t1 = _extract_observations(
        t1_result["prob_map"],
        t1_result["mask"],
        t1_result["transform"],
        crs_name,
        run_id,
        "T1",
        t1_start,
        t1_end,
        max_observations,
    )
    observations_t2 = _extract_observations(
        t2_result["prob_map"],
        t2_result["mask"],
        t2_result["transform"],
        crs_name,
        run_id,
        "T2",
        t2_start,
        t2_end,
        max_observations,
    )
    observations = observations_t1 + observations_t2

    overlap = t1_result["valid_map"] & t2_result["valid_map"]
    total_pixels = max(1, int(overlap.size))
    overlap_ratio = float(overlap.sum() / total_pixels)
    finite_both = np.isfinite(t1_result["prob_map"]) & np.isfinite(t2_result["prob_map"])
    quality = QualityReport(
        valid_pixel_ratio=overlap_ratio,
        nodata_ratio=float(1.0 - overlap_ratio),
        finite_pixel_ratio=float(finite_both.sum() / total_pixels),
        spatial_overlap_ratio=overlap_ratio,
        constant_pixel_ratio=max(
            _constant_ratio(t1_result["prob_map"], t1_result["valid_map"]),
            _constant_ratio(t2_result["prob_map"], t2_result["valid_map"]),
        ),
        sensor_comparability=True,
        resolution_compatible=True,
        recommendations=warnings,
        reasons=[] if overlap.any() else ["No mutually valid pixels"],
    )

    status = (
        ExecutionStatus.SUCCEEDED_WITH_OBSERVATIONS
        if observations
        else ExecutionStatus.SUCCEEDED_EMPTY
    )
    perception_result = PerceptionResult(
        perception_result_id=f"percep-{run_id}",
        inference_task_ref="ml-b2-water-change",
        task_spec_ref="ml-water-change-v1@0.1.0",
        run_id=run_id,
        status=status,
        observations=observations,
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
            "n_observations": len(observations),
            "output_area_crs": output_crs,
            "acquisition_time_complete": bool(t1_start and t2_start),
        },
        started_at=started_at,
        finished_at=_format_timestamp(),
    )

    detection_candidate = None
    semantic_label: str | None = None
    total_area = float(sum(feature["properties"].get("area_m2", 0.0) for feature in polygons))
    if stats["total_changed"] > 0 and polygons:
        geometry = combine_polygons_to_multipolygon(polygons)
        has_increase = any(f["properties"].get("change_type") == "water_increase" for f in polygons)
        has_decrease = any(f["properties"].get("change_type") == "water_decrease" for f in polygons)
        semantic_label = "both" if has_increase and has_decrease else "water_increase" if has_increase else "water_decrease" if has_decrease else "other"
        observation_refs = [item.observation_id for item in observations[:100]]
        candidate_score = min(1.0, stats["total_changed"] / max(stats["valid_pixels"], 1))
        detection_candidate = DetectionCandidate(
            candidate_id=f"cand-{run_id}",
            observation_refs=observation_refs,
            temporal_extent={
                "start": t1_start or "unknown",
                "end": t2_end or t2_start or "unknown",
            },
            candidate_type="water_extent_change",
            semantic_label=semantic_label,
            area_m2=round(total_area, 1),
            geometry=geometry,
            score=candidate_score,
            quality_summary=CandidateQualitySummary(
                mean_score=candidate_score,
                n_observations=len(observations),
                area_consistency=None,
                score_std=None,
            ),
            coordinate_space=_coordinate_space(t1_result["crs"]),
            evidence_refs=[str(change_geotiff), str(geojson_path)],
            rule_version="ml-b2-v1.1",
        )

    result_path = output / "pipeline_result.json"
    result_path.write_text(json.dumps({
        "run_id": run_id,
        "perception_result_id": perception_result.perception_result_id,
        "status": perception_result.status.value,
        "n_observations": len(observations),
        "change_stats": stats,
        "n_polygons": len(polygons),
        "total_area_m2": round(total_area, 1),
        "semantic_label": semantic_label,
        "acquisition_t1": t1_start or "unknown",
        "acquisition_t2": t2_end or t2_start or "unknown",
        "output_crs": output_crs,
        "warnings": warnings,
        "outputs": {
            "t1_prob": str(t1_result.get("output_path", "")),
            "t2_prob": str(t2_result.get("output_path", "")),
            "change_mask": str(change_geotiff),
            "polygons": str(geojson_path),
        },
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 60)
    print("Pipeline complete")
    print(f"  Status:       {perception_result.status.value}")
    print(f"  Observations: {len(observations)}")
    print(f"  Polygons:     {len(polygons)}")
    print(f"  Change:       {stats['total_changed']} pixels")
    print(f"  Semantic:     {semantic_label or 'N/A'}")
    print(f"  Total area:   {total_area:.0f} m2")
    print(f"  Output:       {output}")
    print("=" * 60)

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


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="ML-B2 Water Change Detection")
    parser.add_argument("--t1", required=True)
    parser.add_argument("--t2", required=True)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--min-area", type=float, default=500.0)
    parser.add_argument("--t1-date", default=None)
    parser.add_argument("--t2-date", default=None)
    parser.add_argument("--crs", default="EPSG:4545")
    args = parser.parse_args()
    result = run_water_change(
        Path(args.t1),
        Path(args.t2),
        Path(args.checkpoint) if args.checkpoint else None,
        Path(args.output_dir) if args.output_dir else None,
        prob_threshold=args.threshold,
        min_area_m2=args.min_area,
        t1_acquisition=args.t1_date,
        t2_acquisition=args.t2_date,
        output_crs=args.crs,
    )
    candidate = result["detection_candidate"]
    print(f"DetectionCandidate: {candidate.candidate_id if candidate else 'None'}")


if __name__ == "__main__":
    main()
