"""ML-B1 — Evaluation script.

Usage:
    python -m ml.evaluate                          # synthetic data (smoke)
    python -m ml.evaluate --real                   # real data
"""

import json
from pathlib import Path

from ml.data_adapter import load_data
from ml.model import BaselineModel

CHECKPOINT_PATH = Path(__file__).parent / "data" / "checkpoint.joblib"
METRICS_PATH = Path(__file__).parent / "data" / "eval_metrics.json"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ML-B1 Evaluation")
    parser.add_argument("--real", action="store_true", help="Use real GeoTIFF data")
    parser.add_argument("--s2-path", type=str, default=None)
    parser.add_argument("--jrc-path", type=str, default=None)
    args = parser.parse_args()

    mode = "REAL" if args.real else "SYNTHETIC"
    print("=" * 50)
    print(f"ML-B1: Evaluation ({mode})")
    print("=" * 50)

    if not CHECKPOINT_PATH.exists():
        print(f"Checkpoint not found: {CHECKPOINT_PATH}")
        print("Run 'python -m ml.train' first.")
        return

    model = BaselineModel.load(CHECKPOINT_PATH)
    print(f"Model loaded: {CHECKPOINT_PATH}")

    s2_path = Path(args.s2_path) if args.s2_path else None
    jrc_path = Path(args.jrc_path) if args.jrc_path else None

    (train_X, train_y), (val_X, val_y), (test_X, test_y) = load_data(
        use_real=args.real, s2_path=s2_path, jrc_path=jrc_path,
    )

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
