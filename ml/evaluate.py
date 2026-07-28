import argparse
import json
from pathlib import Path

from ml.data_adapter import load_data
from ml.model import BaselineModel

CHECKPOINT_PATH = Path(__file__).parent / "data" / "checkpoint.joblib"
METRICS_PATH = Path(__file__).parent / "data" / "eval_metrics.json"


def run_evaluation(
    model_path: str | Path | None = None,
    real: bool = False,
    s2_path: str | None = None,
    jrc_path: str | None = None,
    max_samples: int = 50000,
) -> dict:
    cp = Path(model_path) if model_path else CHECKPOINT_PATH
    if not cp.exists():
        raise FileNotFoundError(f"Checkpoint not found: {cp}")

    model = BaselineModel.load(cp)
    s2 = Path(s2_path) if s2_path else None
    jrc = Path(jrc_path) if jrc_path else None

    (train_X, train_y), (val_X, val_y), (test_X, test_y) = load_data(
        use_real=real, s2_path=s2, jrc_path=jrc, max_samples=max_samples)

    results = {}
    for split_name, X, y in [("train", train_X, train_y), ("val", val_X, val_y), ("test", test_X, test_y)]:
        results[split_name] = model.evaluate(X, y)

    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(results, indent=2))
    return results


def main():
    parser = argparse.ArgumentParser(description="ML Evaluation")
    parser.add_argument("--real", action="store_true", help="Use real GeoTIFF data")
    parser.add_argument("--checkpoint", type=str, default=None, help="Path to checkpoint")
    parser.add_argument("--s2-path", type=str, default=None)
    parser.add_argument("--jrc-path", type=str, default=None)
    args = parser.parse_args()

    mode = "REAL" if args.real else "SYNTHETIC"
    print("=" * 50)
    print(f"ML: Evaluation ({mode})")
    print("=" * 50)

    try:
        results = run_evaluation(
            model_path=args.checkpoint, real=args.real,
            s2_path=args.s2_path, jrc_path=args.jrc_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    for split_name, metrics in results.items():
        print(f"\n  [{split_name}]")
        for k, v in metrics.items():
            print(f"    {k}: {v:.4f}" if isinstance(v, float) else f"    {k}: {v}")

    print(f"\nMetrics saved: {METRICS_PATH}")
    print("Evaluation complete.")


if __name__ == "__main__":
    main()
