"""
Dataset Adapter — loads water quality monitoring data from ml/data/ CSVs.

Hardcoded path: ml/data/
Columns: ndwi, mndwi, turbidity_index, chlorophyll_index, ph, temperature,
         rainfall_7d, upstream_landuse, anomaly_flag
"""

from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split

DATA_DIR = Path(__file__).parent / "data"
FEATURE_COLS = [
    "ndwi",
    "mndwi",
    "turbidity_index",
    "chlorophyll_index",
    "ph",
    "temperature",
    "rainfall_7d",
    "upstream_landuse",
]
TARGET_COL = "anomaly_flag"


class WaterQualityDataset:
    """Load synthetic water quality CSV splits from ml/data/."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = Path(data_dir)

    def load_split(self, split: str = "train") -> tuple[pd.DataFrame, pd.Series]:
        path = self.data_dir / f"{split}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Split not found: {path}")
        df = pd.read_csv(path)
        X = df[FEATURE_COLS]
        y = df[TARGET_COL]
        return X, y

    def load_all(self) -> tuple[pd.DataFrame, pd.Series]:
        train_X, train_y = self.load_split("train")
        val_X, val_y = self.load_split("val")
        test_X, test_y = self.load_split("test")
        X = pd.concat([train_X, val_X, test_X], ignore_index=True)
        y = pd.concat([train_y, val_y, test_y], ignore_index=True)
        return X, y


def load_data(
    data_dir: Path = DATA_DIR,
    val_size: float = 0.15,
    test_size: float = 0.15,
    random_state: int = 42,
):
    """Load and split data. Falls back to train/val/test CSVs if they exist."""
    ds = WaterQualityDataset(data_dir)

    if (data_dir / "train.csv").exists():
        train_X, train_y = ds.load_split("train")
        val_X, val_y = ds.load_split("val")
        test_X, test_y = ds.load_split("test")
        return (train_X, train_y), (val_X, val_y), (test_X, test_y)

    X, y = ds.load_all()
    X_temp, test_X, y_temp, test_y = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )
    val_adj = val_size / (1 - test_size)
    train_X, val_X, train_y, val_y = train_test_split(
        X_temp, y_temp, test_size=val_adj, random_state=random_state, stratify=y_temp
    )
    return (train_X, train_y), (val_X, val_y), (test_X, test_y)
