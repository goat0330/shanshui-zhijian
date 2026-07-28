"""
Data Adapter — loads training data from real GeoTIFF rasters (ML-B1).

Supports two modes:
- REAL: reads Sentinel-2 GeoTIFFs, computes indices, samples pixels
- SYNTHETIC (fallback): reads CSV splits for smoke testing

Feature columns from real data: ndwi, mndwi, ndvi, blue, green, red, nir, swir1, swir2
Target column: water_flag (1=water, 0=land, from JRC occurrence > 50)
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

# REAL data features (computed from Sentinel-2 bands)
REAL_FEATURE_COLS = [
    "ndwi", "mndwi", "ndvi",
    "blue", "green", "red", "nir", "swir1", "swir2",
]
REAL_TARGET_COL = "water_flag"

# Synthetic data features (backward compat)
SYNTH_FEATURE_COLS = [
    "ndwi", "mndwi", "turbidity_index", "chlorophyll_index",
    "ph", "temperature", "rainfall_7d", "upstream_landuse",
]
SYNTH_TARGET_COL = "anomaly_flag"

logger = logging.getLogger(__name__)


def _ensure_synthetic_csvs(data_dir: Path):
    """Generate synthetic CSVs if missing (smoke test fallback)."""
    if not (data_dir / "train.csv").exists():
        from ml.data.generate_synthetic_data import main as gen
        gen()


def _compute_indices(array: np.ndarray, band_map: dict[str, int]) -> dict[str, np.ndarray]:
    green = array[band_map["green"]]
    nir = array[band_map["nir"]]
    red = array[band_map["red"]]
    swir1 = array[band_map["swir1"]]

    def safe_ratio(a, b):
        denom = a + b
        denom = np.where(np.abs(denom) < 1e-10, 1e-10, denom)
        return (a - b) / denom

    return {
        "ndwi": safe_ratio(green, nir),
        "mndwi": safe_ratio(green, swir1),
        "ndvi": safe_ratio(nir, red),
    }


def load_real_data(
    s2_t1_path: Path,
    jrc_path: Path,
    max_samples: int = 50000,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_state: int = 42,
) -> tuple[tuple[pd.DataFrame, pd.Series], ...]:
    """Load training data from real Sentinel-2 GeoTIFF and JRC labels.

    Returns:
        ((train_X, train_y), (val_X, val_y), (test_X, test_y))
    """
    import rasterio

    logger.info(f"Loading real data: S2={s2_t1_path}, JRC={jrc_path}")

    with rasterio.open(s2_t1_path) as src:
        s2_array = src.read().astype(np.float32)
        height, width = src.height, src.width

    with rasterio.open(jrc_path) as src_jrc:
        jrc_array = src_jrc.read(1).astype(np.float32)
        if jrc_array.shape != (height, width):
            from scipy.ndimage import zoom
            scale_y = height / jrc_array.shape[0]
            scale_x = width / jrc_array.shape[1]
            jrc_array = zoom(jrc_array, (scale_y, scale_x), order=0)

    band_map = {"green": 1, "red": 2, "nir": 3, "swir1": 4, "swir2": 5}
    if s2_array.shape[0] == 6:
        band_map = {"blue": 0, "green": 1, "red": 2, "nir": 3, "swir1": 4, "swir2": 5}

    indices = _compute_indices(s2_array, band_map)

    valid = (
        np.isfinite(s2_array).all(axis=0)
        & np.isfinite(jrc_array)
        & (jrc_array >= 0)
    )

    rows = []
    rng = np.random.RandomState(random_state)
    sample_coords = np.argwhere(valid)
    if len(sample_coords) > max_samples:
        idx = rng.choice(len(sample_coords), max_samples, replace=False)
        sample_coords = sample_coords[idx]

    for y, x in sample_coords:
        row = {
            "ndwi": indices["ndwi"][y, x],
            "mndwi": indices["mndwi"][y, x],
            "ndvi": indices["ndvi"][y, x],
        }
        for band_name, band_idx in band_map.items():
            row[band_name] = float(s2_array[band_idx, y, x])
        row["water_flag"] = int(jrc_array[y, x] > 50)
        rows.append(row)

    df = pd.DataFrame(rows)

    if len(df) < 10:
        logger.warning(f"Too few valid samples ({len(df)}), using synthetic fallback")
        return load_synthetic_data()

    from sklearn.model_selection import train_test_split
    X = df[REAL_FEATURE_COLS]
    y = df[REAL_TARGET_COL]

    X_temp, test_X, y_temp, test_y = train_test_split(
        X, y, test_size=test_ratio, random_state=random_state, stratify=y,
    )
    val_adj = val_ratio / (1 - test_ratio)
    train_X, val_X, train_y, val_y = train_test_split(
        X_temp, y_temp, test_size=val_adj, random_state=random_state, stratify=y_temp,
    )

    logger.info(
        f"Real data loaded: train={len(train_X)}, val={len(val_X)}, test={len(test_X)}, "
        f"water_ratio={y.mean():.2%}"
    )
    return (train_X, train_y), (val_X, val_y), (test_X, test_y)


def load_synthetic_data(
    data_dir: Path = DATA_DIR,
    val_size: float = 0.15,
    test_size: float = 0.15,
    random_state: int = 42,
) -> tuple[tuple[pd.DataFrame, pd.Series], ...]:
    """Load synthetic CSV splits (fallback for smoke tests)."""
    _ensure_synthetic_csvs(data_dir)

    train_X = pd.read_csv(data_dir / "train.csv")
    train_y = train_X.pop("anomaly_flag")
    val_X = pd.read_csv(data_dir / "val.csv")
    val_y = val_X.pop("anomaly_flag")
    test_X = pd.read_csv(data_dir / "test.csv")
    test_y = test_X.pop("anomaly_flag")

    return (train_X, train_y), (val_X, val_y), (test_X, test_y)


def load_data(
    data_dir: Path = DATA_DIR,
    use_real: bool = False,
    s2_path: Path | None = None,
    jrc_path: Path | None = None,
    max_samples: int = 50000,
) -> tuple[tuple[pd.DataFrame, pd.Series], ...]:
    """Auto-detect and load data. Prefers real data if use_real=True and paths exist."""
    if use_real:
        s2 = s2_path or Path("data/chongqing_demo/raw/s2_t1.tif")
        jrc = jrc_path or Path("data/chongqing_demo/raw/jrc_water_occurrence.tif")
        if s2.exists() and jrc.exists():
            return load_real_data(s2, jrc, max_samples=max_samples)
        logger.warning("Real data paths not found, falling back to synthetic")

    return load_synthetic_data(data_dir=data_dir)
