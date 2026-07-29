"""Training-data adapter for the Cycle 3.1.1 water baseline.

Two modes are intentionally separate:

* ``use_real=False`` loads deterministic synthetic CSVs for smoke tests.
* ``use_real=True`` is fail-closed. Missing, invalid or unusable GeoTIFFs raise
  an explicit exception and never silently become a synthetic experiment.

Real Sentinel-2 features are sampled after the label raster is reprojected onto
exactly the same CRS, transform, width and height. Train/validation/test splits
are made by spatial blocks instead of randomly splitting neighbouring pixels.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

REAL_FEATURE_COLS = [
    "ndwi",
    "mndwi",
    "ndvi",
    "blue",
    "green",
    "red",
    "nir",
    "swir1",
    "swir2",
]
REAL_TARGET_COL = "water_flag"

SYNTH_FEATURE_COLS = [
    "ndwi",
    "mndwi",
    "turbidity_index",
    "chlorophyll_index",
    "ph",
    "temperature",
    "rainfall_7d",
    "upstream_landuse",
]
SYNTH_TARGET_COL = "anomaly_flag"

logger = logging.getLogger(__name__)


class RealDataError(ValueError):
    """Raised when a requested real-data experiment is not trustworthy."""


def _ensure_synthetic_csvs(data_dir: Path) -> None:
    if not (data_dir / "train.csv").exists():
        from ml.data.generate_synthetic_data import main as generate

        generate()


def _safe_ratio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    denominator = a + b
    denominator = np.where(np.abs(denominator) < 1e-10, 1e-10, denominator)
    return (a - b) / denominator


def _compute_indices(array: np.ndarray, band_map: dict[str, int]) -> dict[str, np.ndarray]:
    missing = {"green", "red", "nir", "swir1"} - set(band_map)
    if missing:
        raise RealDataError(f"Required Sentinel-2 bands missing: {sorted(missing)}")
    green = array[band_map["green"]]
    red = array[band_map["red"]]
    nir = array[band_map["nir"]]
    swir1 = array[band_map["swir1"]]
    return {
        "ndwi": _safe_ratio(green, nir),
        "mndwi": _safe_ratio(green, swir1),
        "ndvi": _safe_ratio(nir, red),
    }


def _normalise_description(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "").replace("_", "")


def _resolve_band_map(descriptions: Iterable[str | None], band_count: int) -> dict[str, int]:
    aliases = {
        "blue": {"blue", "b2", "band2"},
        "green": {"green", "b3", "band3"},
        "red": {"red", "b4", "band4"},
        "nir": {"nir", "b8", "band8", "b8a", "band8a"},
        "swir1": {"swir1", "b11", "band11"},
        "swir2": {"swir2", "b12", "band12"},
    }
    resolved: dict[str, int] = {}
    for index, raw in enumerate(descriptions):
        name = _normalise_description(raw)
        for canonical, names in aliases.items():
            if name in names:
                resolved[canonical] = index

    # The project contract for unlabelled six-band rasters is B2/B3/B4/B8/B11/B12.
    if not resolved and band_count == 6:
        return {"blue": 0, "green": 1, "red": 2, "nir": 3, "swir1": 4, "swir2": 5}

    missing = set(REAL_FEATURE_COLS[3:]) - set(resolved)
    if missing:
        raise RealDataError(
            "Cannot resolve six required S2 bands from descriptions; "
            f"missing={sorted(missing)}, descriptions={list(descriptions)}"
        )
    return resolved


def _reproject_label_to_reference(jrc_path: Path, reference) -> np.ndarray:
    """Nearest-neighbour reproject of labels to the exact reference grid."""
    import rasterio
    from rasterio.warp import Resampling, reproject

    if reference.crs is None:
        raise RealDataError("Sentinel-2 raster has no CRS")

    destination = np.full((reference.height, reference.width), np.nan, dtype=np.float32)
    with rasterio.open(jrc_path) as label_src:
        if label_src.crs is None:
            raise RealDataError("JRC label raster has no CRS")
        source = label_src.read(1).astype(np.float32)
        source_nodata = label_src.nodata
        reproject(
            source=source,
            destination=destination,
            src_transform=label_src.transform,
            src_crs=label_src.crs,
            src_nodata=source_nodata,
            dst_transform=reference.transform,
            dst_crs=reference.crs,
            dst_nodata=np.nan,
            resampling=Resampling.nearest,
        )
    return destination


def _assign_spatial_splits(
    frame: pd.DataFrame,
    val_ratio: float,
    test_ratio: float,
    random_state: int,
) -> pd.Series:
    """Assign whole spatial blocks while retaining both classes per split.

    The retry loop changes only block allocation, never pixel membership. It
    prevents a small water body from accidentally leaving validation or test
    with land-only labels while still guaranteeing zero spatial-group overlap.
    """
    if not 0 < val_ratio < 1 or not 0 < test_ratio < 1 or val_ratio + test_ratio >= 1:
        raise ValueError("val_ratio and test_ratio must be positive and sum to less than 1")

    groups = frame["_spatial_group"].drop_duplicates().to_numpy()
    if len(groups) < 3:
        raise RealDataError(f"At least three spatial groups are required, got {len(groups)}")
    n_groups = len(groups)
    n_test = max(1, int(round(n_groups * test_ratio)))
    n_val = max(1, int(round(n_groups * val_ratio)))
    if n_test + n_val >= n_groups:
        n_test = 1
        n_val = 1

    def make_assignment(order: np.ndarray) -> pd.Series:
        test_groups = set(order[:n_test].tolist())
        val_groups = set(order[n_test : n_test + n_val].tolist())
        return frame["_spatial_group"].map(
            lambda group: "test" if group in test_groups else "val" if group in val_groups else "train"
        )

    # Deterministic retries find a valid group allocation without leaking pixels.
    for attempt in range(512):
        rng = np.random.RandomState(random_state + attempt)
        order = groups.copy()
        rng.shuffle(order)
        assignment = make_assignment(order)
        valid = True
        for split_name in ("train", "val", "test"):
            labels = frame.loc[assignment == split_name, REAL_TARGET_COL]
            if labels.empty or labels.nunique() < 2:
                valid = False
                break
        if valid:
            return assignment

    raise RealDataError(
        "Could not allocate spatial groups with both classes in train/val/test. "
        "Use more scenes/AOIs or reduce spatial_block_size."
    )


def load_real_data(
    s2_t1_path: Path,
    jrc_path: Path,
    max_samples: int = 50_000,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_state: int = 42,
    spatial_block_size: int = 16,
    minimum_samples: int = 30,
) -> tuple[tuple[pd.DataFrame, pd.Series], ...]:
    """Load one real S2 scene and a weak JRC stable-water label.

    JRC occurrence is a weak, historical stable-water target and must not be
    interpreted as date-specific change ground truth.
    """
    import rasterio

    s2_t1_path = Path(s2_t1_path)
    jrc_path = Path(jrc_path)
    missing = [str(path) for path in (s2_t1_path, jrc_path) if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Real mode requires existing GeoTIFFs; missing: {missing}")
    if max_samples < minimum_samples:
        raise ValueError(f"max_samples must be >= {minimum_samples}")
    if spatial_block_size <= 0:
        raise ValueError("spatial_block_size must be positive")

    logger.info("Loading real data: S2=%s, JRC=%s", s2_t1_path, jrc_path)
    with rasterio.open(s2_t1_path) as s2_src:
        if s2_src.crs is None:
            raise RealDataError("Sentinel-2 raster has no CRS")
        s2_array = s2_src.read(masked=True).astype(np.float32)
        band_map = _resolve_band_map(s2_src.descriptions, s2_src.count)
        labels = _reproject_label_to_reference(jrc_path, s2_src)
        dataset_valid = s2_src.dataset_mask() > 0
        height, width = s2_src.height, s2_src.width

    raw = np.asarray(s2_array.filled(np.nan), dtype=np.float32)
    indices = _compute_indices(raw, band_map)
    valid = dataset_valid & np.isfinite(raw).all(axis=0) & np.isfinite(labels) & (labels >= 0)
    coordinates = np.argwhere(valid)
    if len(coordinates) < minimum_samples:
        raise RealDataError(
            f"Too few valid co-registered samples: {len(coordinates)} < {minimum_samples}"
        )

    rng = np.random.RandomState(random_state)
    if len(coordinates) > max_samples:
        coordinates = coordinates[rng.choice(len(coordinates), max_samples, replace=False)]

    rows: list[dict] = []
    for row_index, col_index in coordinates:
        feature = {
            "ndwi": float(indices["ndwi"][row_index, col_index]),
            "mndwi": float(indices["mndwi"][row_index, col_index]),
            "ndvi": float(indices["ndvi"][row_index, col_index]),
        }
        for band_name, band_index in band_map.items():
            feature[band_name] = float(raw[band_index, row_index, col_index])
        feature[REAL_TARGET_COL] = int(labels[row_index, col_index] > 50)
        feature["_row"] = int(row_index)
        feature["_col"] = int(col_index)
        feature["_spatial_group"] = f"{row_index // spatial_block_size}:{col_index // spatial_block_size}"
        rows.append(feature)

    frame = pd.DataFrame(rows)
    if len(frame) < minimum_samples:
        raise RealDataError(f"Too few usable real samples after feature extraction: {len(frame)}")
    if frame[REAL_TARGET_COL].nunique() < 2:
        raise RealDataError("Real labels contain only one class; metrics/training would be invalid")

    frame["_split"] = _assign_spatial_splits(frame, val_ratio, test_ratio, random_state)
    split_outputs: list[tuple[pd.DataFrame, pd.Series]] = []
    split_groups: dict[str, set[str]] = {}
    for split_name in ("train", "val", "test"):
        subset = frame.loc[frame["_split"] == split_name].copy()
        if subset.empty:
            raise RealDataError(f"Spatial split '{split_name}' is empty")
        if subset[REAL_TARGET_COL].nunique() < 2:
            raise RealDataError(
                f"Spatial split '{split_name}' contains one class only; use more scenes/AOIs or smaller blocks"
            )
        split_groups[split_name] = set(subset["_spatial_group"])
        split_outputs.append((subset[REAL_FEATURE_COLS], subset[REAL_TARGET_COL]))

    if split_groups["train"] & split_groups["val"] or split_groups["train"] & split_groups["test"] or split_groups["val"] & split_groups["test"]:
        raise AssertionError("Spatial group leakage detected")

    logger.info(
        "Real data loaded on %sx%s grid: train=%s val=%s test=%s water_ratio=%.2f%% groups=%s/%s/%s",
        height,
        width,
        len(split_outputs[0][0]),
        len(split_outputs[1][0]),
        len(split_outputs[2][0]),
        frame[REAL_TARGET_COL].mean() * 100,
        len(split_groups["train"]),
        len(split_groups["val"]),
        len(split_groups["test"]),
    )
    return tuple(split_outputs)  # type: ignore[return-value]


def load_synthetic_data(
    data_dir: Path = DATA_DIR,
    val_size: float = 0.15,
    test_size: float = 0.15,
    random_state: int = 42,
) -> tuple[tuple[pd.DataFrame, pd.Series], ...]:
    del val_size, test_size, random_state  # CSVs are already deterministic splits.
    data_dir = Path(data_dir)
    _ensure_synthetic_csvs(data_dir)
    outputs = []
    for split_name in ("train", "val", "test"):
        path = data_dir / f"{split_name}.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        frame = pd.read_csv(path)
        if SYNTH_TARGET_COL not in frame:
            raise RealDataError(f"{path} is missing target column {SYNTH_TARGET_COL}")
        target = frame.pop(SYNTH_TARGET_COL)
        outputs.append((frame, target))
    return tuple(outputs)  # type: ignore[return-value]


def load_data(
    data_dir: Path = DATA_DIR,
    use_real: bool = False,
    s2_path: Path | None = None,
    jrc_path: Path | None = None,
    max_samples: int = 50_000,
    **real_options,
) -> tuple[tuple[pd.DataFrame, pd.Series], ...]:
    """Load explicitly selected data mode; real mode never falls back."""
    if not use_real:
        return load_synthetic_data(data_dir=Path(data_dir))

    resolved_s2 = Path(s2_path) if s2_path else Path("data/chongqing_demo/raw/s2_t1.tif")
    resolved_jrc = Path(jrc_path) if jrc_path else Path("data/chongqing_demo/raw/jrc_water_occurrence.tif")
    missing = [str(path) for path in (resolved_s2, resolved_jrc) if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "--real was requested, but required files are missing: " + ", ".join(missing)
        )
    return load_real_data(
        resolved_s2,
        resolved_jrc,
        max_samples=max_samples,
        **real_options,
    )
