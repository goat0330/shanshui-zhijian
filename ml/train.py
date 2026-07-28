"""ML-SMOKE-00 / ML-B1 — Training script.

Usage:
    python -m ml.train                             # synthetic data (smoke)
    python -m ml.train --real                      # real GeoTIFF data
"""

import json
from pathlib import Path

from ml.data_adapter import load_data
from ml.model import BaselineModel

CHECKPOINT_PATH = Path(__file__).parent / "data" / "checkpoint.joblib"
METRICS_PATH = Path(__file__).parent / "data" / "train_metrics.json"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ML-SMOKE-00 / ML-B1 Training")
    parser.add_argument("--real", action="store_true", help="Use real GeoTIFF data")
    parser.add_argument("--s2-path", type=str, default=None, help="Path to S2 GeoTIFF")
    parser.add_argument("--jrc-path", type=str, default=None, help="Path to JRC GeoTIFF")
    parser.add_argument("--max-samples", type=int, default=50000, help="Max training samples")
    parser.add_argument("--epochs", type=int, default=0, help="Ignored (RF has no epochs)")
    args = parser.parse_args()

    mode = "REAL" if args.real else "SYNTHETIC"
    print("=" * 50)
    print(f"ML-B1: Training ({mode})")
    print("=" * 50)

    s2_path = Path(args.s2_path) if args.s2_path else None
    jrc_path = Path(args.jrc_path) if args.jrc_path else None

    (train_X, train_y), (val_X, val_y), (test_X, test_y) = load_data(
        use_real=args.real,
        s2_path=s2_path,
        jrc_path=jrc_path,
        max_samples=args.max_samples,
    )

    print(f"\nData loaded ({mode}):")
    print(f"  Train: {len(train_X)} samples ({train_y.mean():.1%} positive)")
    print(f"  Val:   {len(val_X)} samples ({val_y.mean():.1%} positive)")
    print(f"  Test:  {len(test_X)} samples ({test_y.mean():.1%} positive)")
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

    metrics = {"train": train_metrics, "val": val_metrics, "test": test_metrics}
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))

    model.save(CHECKPOINT_PATH)
    print(f"\nCheckpoint saved: {CHECKPOINT_PATH}")
    print("Training complete.")


if __name__ == "__main__":
    main()
