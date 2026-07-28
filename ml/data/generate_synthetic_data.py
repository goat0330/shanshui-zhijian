"""
Generate synthetic water quality monitoring dataset for ML baseline smoke test.

Produces 3 CSVs in ml/data/:
- train.csv (2000 samples)
- val.csv   (500 samples)
- test.csv  (500 samples)

Features simulate remote sensing water quality indices:
- ndwi: Normalized Difference Water Index
- mndwi: Modified NDWI
- turbidity_index: Simulated turbidity proxy
- chlorophyll_index: Simulated chlorophyll-a proxy
- ph: pH value
- temperature: water surface temperature proxy
- rainfall_7d: 7-day cumulative rainfall proxy
- upstream_landuse: upstream land use intensity (0-1)

Target: anomaly_flag (0 = normal, 1 = anomaly)
"""

import numpy as np
import pandas as pd
from pathlib import Path


DATA_DIR = Path(__file__).parent
SEED = 42
N_FEATURES = 8
FEATURE_NAMES = [
    "ndwi",
    "mndwi",
    "turbidity_index",
    "chlorophyll_index",
    "ph",
    "temperature",
    "rainfall_7d",
    "upstream_landuse",
]


def _generate_split(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Generate a synthetic split with realistic correlations."""

    ndwi = rng.normal(-0.1, 0.3, n).clip(-1, 1)
    mndwi = ndwi + rng.normal(0, 0.1, n)
    turbidity = np.exp(rng.normal(1.5, 0.6, n))
    chlorophyll = np.exp(rng.normal(2.0, 0.5, n))
    ph = rng.normal(7.5, 0.8, n).clip(4, 10)
    temperature = rng.normal(22, 5, n).clip(0, 40)
    rainfall_7d = rng.exponential(30, n).clip(0, 200)
    upstream_landuse = rng.beta(2, 3, n)

    df = pd.DataFrame({
        "ndwi": ndwi,
        "mndwi": mndwi,
        "turbidity_index": turbidity,
        "chlorophyll_index": chlorophyll,
        "ph": ph,
        "temperature": temperature,
        "rainfall_7d": rainfall_7d,
        "upstream_landuse": upstream_landuse,
    })

    anomaly = (
        (df["ndwi"] < -0.4) |
        (df["turbidity_index"] > 8.0) |
        (df["chlorophyll_index"] > 15.0) |
        ((df["ph"] < 5.5) | (df["ph"] > 9.0)) |
        (df["rainfall_7d"] > 120)
    ).astype(int)

    noise = rng.random(n) < 0.05
    anomaly = anomaly ^ noise

    df["anomaly_flag"] = anomaly.astype(int)
    return df


def main():
    rng = np.random.default_rng(SEED)

    train = _generate_split(2000, rng)
    val = _generate_split(500, rng)
    test = _generate_split(500, rng)

    train.to_csv(DATA_DIR / "train.csv", index=False)
    val.to_csv(DATA_DIR / "val.csv", index=False)
    test.to_csv(DATA_DIR / "test.csv", index=False)

    print(f"Generated synthetic dataset:")
    print(f"  train: {len(train)} samples ({train['anomaly_flag'].mean():.1%} anomaly)")
    print(f"  val:   {len(val)} samples ({val['anomaly_flag'].mean():.1%} anomaly)")
    print(f"  test:  {len(test)} samples ({test['anomaly_flag'].mean():.1%} anomaly)")
    print(f"  location: {DATA_DIR}")


if __name__ == "__main__":
    main()
