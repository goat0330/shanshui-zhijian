"""Generate synthetic water quality dataset for smoke tests (kept for backward compat)."""

import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent
SEED = 42
FEATURE_NAMES = [
    "ndwi", "mndwi", "turbidity_index", "chlorophyll_index",
    "ph", "temperature", "rainfall_7d", "upstream_landuse",
]


def _generate_split(n: int, rng: np.random.Generator) -> pd.DataFrame:
    ndwi = rng.normal(-0.1, 0.3, n).clip(-1, 1)
    mndwi = ndwi + rng.normal(0, 0.1, n)
    turbidity = np.exp(rng.normal(1.5, 0.6, n))
    chlorophyll = np.exp(rng.normal(2.0, 0.5, n))
    ph = rng.normal(7.5, 0.8, n).clip(4, 10)
    temperature = rng.normal(22, 5, n).clip(0, 40)
    rainfall_7d = rng.exponential(30, n).clip(0, 200)
    upstream_landuse = rng.beta(2, 3, n)

    df = pd.DataFrame({
        "ndwi": ndwi, "mndwi": mndwi,
        "turbidity_index": turbidity, "chlorophyll_index": chlorophyll,
        "ph": ph, "temperature": temperature,
        "rainfall_7d": rainfall_7d, "upstream_landuse": upstream_landuse,
    })

    anomaly = (
        (df["ndwi"] < -0.4) | (df["turbidity_index"] > 8.0) |
        (df["chlorophyll_index"] > 15.0) | ((df["ph"] < 5.5) | (df["ph"] > 9.0)) |
        (df["rainfall_7d"] > 120)
    ).astype(int)
    noise = rng.random(n) < 0.05
    df["anomaly_flag"] = (anomaly ^ noise).astype(int)
    return df


def main():
    rng = np.random.default_rng(SEED)
    for name, n in [("train", 2000), ("val", 500), ("test", 500)]:
        df = _generate_split(n, rng)
        df.to_csv(DATA_DIR / f"{name}.csv", index=False)
    print(f"Generated synthetic CSVs in {DATA_DIR}")


if __name__ == "__main__":
    main()
