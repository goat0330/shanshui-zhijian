"""
ML Baseline — Evaluation script.

Usage: python -m ml.evaluate

Loads checkpoint from ml/data/checkpoint.joblib and evaluates on test split.
"""

import json
import sys
from pathlib import Path

from ml.data_adapter import load_data, WaterQualityDataset, FEATURE_COLS, TARGET_COL
from ml.model import BaselineModel

CHECKPOINT_PATH = Path(__file__).parent / "data" / "checkpoint.joblib"
METRICS_PATH = Path(__file__).parent / "data" / "eval_metrics.json"


def main():
    print("=" * 50)
    print("ML Baseline: Evaluation")
    print("=" * 50)

    if not CHECKPOINT_PATH.exists():
        print(f"Checkpoint not found: {CHECKPOINT_PATH}")
        print("Run 'python -m ml.train' first.")
        sys.exit(1)

    model = BaselineModel.load(CHECKPOINT_PATH)
    print(f"Model loaded: {CHECKPOINT_PATH}")

    (train_X, train_y), (val_X, val_y), (test_X, test_y) = load_data()

    print("\n--- Full Evaluation ---")
    for split_name, X, y in [("Train", train_X, train_y), ("Val", val_X, val_y), ("Test", test_X, test_y)]:
        metrics = model.evaluate(X, y)
        print(f"\n  [{split_name}]")
        for k, v in metrics.items():
            print(f"    {k}: {v:.4f}" if isinstance(v, float) else f"    {k}: {v}")

    test_metrics = model.evaluate(test_X, test_y)
    METRICS_PATH.write_text(json.dumps(test_metrics, indent=2))
    print(f"\nTest metrics saved: {METRICS_PATH}")
    print("Evaluation complete.")


if __name__ == "__main__":
    main()
