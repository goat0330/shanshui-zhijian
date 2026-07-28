"""
ML Baseline — Training script.

Usage: python -m ml.train

Produces checkpoint at: ml/data/checkpoint.joblib
"""

import json
import sys
from pathlib import Path

from ml.data_adapter import load_data
from ml.model import BaselineModel

CHECKPOINT_PATH = Path(__file__).parent / "data" / "checkpoint.joblib"
METRICS_PATH = Path(__file__).parent / "data" / "train_metrics.json"


def main():
    print("=" * 50)
    print("ML Baseline: Training")
    print("=" * 50)

    (train_X, train_y), (val_X, val_y), (test_X, test_y) = load_data()

    print(f"\nData loaded:")
    print(f"  Train: {len(train_X)} samples ({train_y.mean():.1%} anomaly)")
    print(f"  Val:   {len(val_X)} samples ({val_y.mean():.1%} anomaly)")
    print(f"  Test:  {len(test_X)} samples ({test_y.mean():.1%} anomaly)")
    print(f"  Features: {list(train_X.columns)}")

    model = BaselineModel(n_estimators=100, max_depth=10, random_state=42)
    model.train(train_X, train_y)

    train_metrics = model.evaluate(train_X, train_y)
    val_metrics = model.evaluate(val_X, val_y)
    test_metrics = model.evaluate(test_X, test_y)

    print(f"\n--- Train Metrics ---")
    for k, v in train_metrics.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    print(f"\n--- Validation Metrics ---")
    for k, v in val_metrics.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    print(f"\n--- Test Metrics ---")
    for k, v in test_metrics.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    metrics = {
        "train": train_metrics,
        "val": val_metrics,
        "test": test_metrics,
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))

    model.save(CHECKPOINT_PATH)
    print(f"\nCheckpoint saved: {CHECKPOINT_PATH}")
    print("Training complete.")


if __name__ == "__main__":
    main()
