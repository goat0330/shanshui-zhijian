import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import torch
from ml.artifacts import load_checkpoint
from ml.config import TrainConfig
from ml.metrics import accuracy, precision, recall, f1_score, classification_report, confusion_matrix
from ml.pipeline import _SimpleModel, _generate_dummy_data
from ml.run_manifest import MlRunManifest


def _load_real_test_data(config: TrainConfig):
    import pandas as pd
    test_df = pd.read_csv(config.data.test_path / "dataset.csv")
    feature_cols = [c for c in test_df.columns if c.startswith("feature_")]
    x_test = torch.from_numpy(test_df[feature_cols].values.astype(np.float32))
    y_test = torch.from_numpy(test_df["label"].values.astype(np.int64))
    return x_test, y_test


def evaluate_checkpoint(
    checkpoint_path: str | Path,
    config: TrainConfig,
    run_id: str,
    output_dir: Path,
    use_smoke: bool = False,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    state = load_checkpoint(checkpoint_path)
    input_dim = state.get("input_dim", 10)

    if use_smoke:
        x_test, y_test = _generate_dummy_data(
            n_samples=config.data.batch_size,
            seed=config.training.seed + 2,
        )
    else:
        try:
            x_test, y_test = _load_real_test_data(config)
            input_dim = x_test.shape[1]
        except Exception:
            x_test, y_test = _generate_dummy_data(
                n_samples=config.data.batch_size,
                seed=config.training.seed + 2,
            )

    num_classes = state.get("config", {}).get("model", {}).get("num_classes", 2)
    model = _SimpleModel(input_dim=input_dim, num_classes=num_classes)
    model.load_state_dict(state["model_state_dict"])
    model.eval()

    with torch.no_grad():
        logits = model(x_test)
        preds = logits.argmax(dim=1).numpy()
    y_true = y_test.numpy()

    acc = accuracy(y_true, preds)
    p = precision(y_true, preds)
    r = recall(y_true, preds)
    f1 = f1_score(y_true, preds)
    cm = confusion_matrix(y_true, preds, num_classes=num_classes)
    report = classification_report(y_true, preds)

    metrics: dict[str, float] = {
        "accuracy": acc,
        "precision": p,
        "recall": r,
        "f1_score": f1,
    }

    manifest = MlRunManifest(run_id=run_id)
    manifest.record_config(config)
    manifest.record_model_artifact(
        artifact_id="evaluated_checkpoint",
        uri=str(Path(checkpoint_path).resolve()),
        sha256="",
    )
    manifest.record_metrics(metrics)

    manifest_path = output_dir / "eval_manifest.json"
    run_manifest = manifest.finalize()
    run_manifest.tool_config["evaluation"] = {
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
        "num_test_samples": int(len(y_true)),
    }
    run_manifest.to_json()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(run_manifest.to_json(), encoding="utf-8")

    return {
        "run_id": run_id,
        "metrics": metrics,
        "confusion_matrix": cm.tolist(),
        "num_test_samples": int(len(y_true)),
        "manifest": str(manifest_path),
        "classification_report": report,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ML Evaluation Pipeline")
    parser.add_argument("--checkpoint", required=True, help="Path to checkpoint .pt")
    parser.add_argument("--run-id", default="", help="Run ID")
    parser.add_argument("--output-dir", default="ml/eval_output", help="Output directory")
    parser.add_argument("--smoke", action="store_true", help="Use synthetic data")
    parser.add_argument("--config", default="", help="Path to config JSON")
    args = parser.parse_args()

    if args.config:
        config = TrainConfig.from_json(args.config)
    else:
        config = TrainConfig.smoke_defaults()

    import time
    run_id = args.run_id or f"eval-{int(time.time())}"
    output_dir = Path(args.output_dir)
    result = evaluate_checkpoint(
        checkpoint_path=args.checkpoint,
        config=config,
        run_id=run_id,
        output_dir=output_dir,
        use_smoke=args.smoke,
    )

    print(f"Run ID      : {result['run_id']}")
    print(f"Accuracy    : {result['metrics']['accuracy']:.4f}")
    print(f"Precision   : {result['metrics']['precision']:.4f}")
    print(f"Recall      : {result['metrics']['recall']:.4f}")
    print(f"F1 Score    : {result['metrics']['f1_score']:.4f}")
    print(f"Samples     : {result['num_test_samples']}")
    print(f"Manifest    : {result['manifest']}")
    print("EVAL_OK")


if __name__ == "__main__":
    main()
