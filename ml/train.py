"""ML-B1 — Training script.

Usage:
    python -m ml.train --smoke                        # smoke test (PyTorch, kept for compat)
    python -m ml.train                                # synthetic data (RandomForest)
    python -m ml.train --real                         # real GeoTIFF data (RandomForest)
    python -m ml.train --smoke --epochs 5             # smoke with custom epochs
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from ml.artifacts import save_checkpoint
from ml.config import TrainConfig
from ml.metrics import accuracy
from ml.run_manifest import MlRunManifest

CHECKPOINT_PATH = Path(__file__).parent / "data" / "checkpoint.joblib"
METRICS_PATH = Path(__file__).parent / "data" / "train_metrics.json"


# ── PyTorch smoke training (kept for backward compat with Agent B) ────────

class _SimpleModel(nn.Module):
    def __init__(self, input_dim: int = 10, num_classes: int = 2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 16),
            nn.ReLU(),
            nn.Linear(16, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def _generate_dummy_data(n_samples: int = 64, input_dim: int = 10, num_classes: int = 2, seed: int = 42):
    rng = np.random.RandomState(seed)
    x = rng.randn(n_samples, input_dim).astype(np.float32)
    y = rng.randint(0, num_classes, size=n_samples).astype(np.int64)
    return torch.from_numpy(x), torch.from_numpy(y)


def _train_smoke(config: TrainConfig, run_id: str, output_dir: Path) -> Path:
    torch.manual_seed(config.training.seed)
    np.random.seed(config.training.seed)

    x_train, y_train = _generate_dummy_data(n_samples=config.data.batch_size * 2, seed=config.training.seed)
    x_val, y_val = _generate_dummy_data(n_samples=config.data.batch_size, seed=config.training.seed + 1)

    model = _SimpleModel(input_dim=10, num_classes=config.model.num_classes)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=config.training.learning_rate)

    manifest = MlRunManifest(run_id=run_id)
    manifest.record_config(config)
    manifest.record_dataset("train_smoke", str(output_dir / "data"))

    for epoch in range(config.training.max_epochs):
        model.train()
        optimizer.zero_grad()
        logits = model(x_train)
        loss = criterion(logits, y_train)
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_logits = model(x_val)
            val_pred = val_logits.argmax(dim=1).numpy()
            val_acc = accuracy(y_val.numpy(), val_pred)

        manifest.record_metrics({f"train_loss_epoch_{epoch}": float(loss.item()), f"val_acc_epoch_{epoch}": val_acc})

    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "smoke_checkpoint.pt"
    state = {"model_state_dict": model.state_dict(), "config": config.model_dump(), "run_id": run_id, "epoch": config.training.max_epochs}
    save_checkpoint(state, checkpoint_path)
    manifest.record_model_artifact(artifact_id="smoke_model", uri=str(checkpoint_path), size_bytes=checkpoint_path.stat().st_size)
    manifest_path = output_dir / "run_manifest.json"
    manifest.save(manifest_path)
    return checkpoint_path


# ── ML-B1 RandomForest training ──────────────────────────────────────────

def _train_rf(args):
    from ml.data_adapter import load_data
    from ml.model import BaselineModel

    s2_path = Path(args.s2_path) if args.s2_path else None
    jrc_path = Path(args.jrc_path) if args.jrc_path else None

    (train_X, train_y), (val_X, val_y), (test_X, test_y) = load_data(
        use_real=args.real, s2_path=s2_path, jrc_path=jrc_path, max_samples=args.max_samples,
    )

    mode = "REAL" if args.real else "SYNTHETIC"
    print(f"\nData loaded ({mode}):")
    print(f"  Train: {len(train_X)} samples ({train_y.mean():.1%} positive)")
    print(f"  Val:   {len(val_X)} samples ({val_y.mean():.1%} positive)")
    print(f"  Test:  {len(test_X)} samples ({test_y.mean():.1%} positive)")
    print(f"  Features: {list(train_X.columns)}")

    model = BaselineModel(n_estimators=100, max_depth=10, random_state=42)
    model.train(train_X, train_y)

    for split_name, X, y in [("Train", train_X, train_y), ("Val", val_X, val_y), ("Test", test_X, test_y)]:
        metrics = model.evaluate(X, y)
        print(f"\n  [{split_name}]")
        for k, v in metrics.items():
            print(f"    {k}: {v:.4f}" if isinstance(v, float) else f"    {k}: {v}")

    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps({
        "train": model.evaluate(train_X, train_y),
        "val": model.evaluate(val_X, val_y),
        "test": model.evaluate(test_X, test_y),
    }, indent=2))

    model.save(CHECKPOINT_PATH)
    print(f"\nCheckpoint saved: {CHECKPOINT_PATH}")
    print("Training complete.")


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ML-B1 Training")
    parser.add_argument("--smoke", action="store_true", help="Run PyTorch smoke test (Agent B compat)")
    parser.add_argument("--real", action="store_true", help="Use real GeoTIFF data (ML-B1)")
    parser.add_argument("--run-id", default="", help="Run ID (smoke mode)")
    parser.add_argument("--config", default="", help="Config path (smoke mode)")
    parser.add_argument("--output-dir", default="ml/output", help="Output directory (smoke mode)")
    parser.add_argument("--epochs", type=int, default=0, help="Override epochs (smoke mode)")
    parser.add_argument("--s2-path", type=str, default=None, help="S2 GeoTIFF path (real mode)")
    parser.add_argument("--jrc-path", type=str, default=None, help="JRC GeoTIFF path (real mode)")
    parser.add_argument("--max-samples", type=int, default=50000, help="Max training samples (real mode)")
    args = parser.parse_args()

    print("=" * 50)
    if args.smoke:
        print("ML-B1: Smoke Training (PyTorch)")
        print("=" * 50)
        config = TrainConfig.smoke_defaults()
        if args.epochs > 0:
            config.training.max_epochs = args.epochs
        run_id = args.run_id or f"smoke-{int(time.time())}"
        output_dir = Path(args.output_dir)
        ckpt = _train_smoke(config, run_id, output_dir)
        manifest_path = output_dir / "run_manifest.json"
        print(f"Checkpoint: {ckpt}")
        print(f"Manifest: {manifest_path}")
        print(f"Run ID: {run_id}")
        print("SMOKE_OK")
    else:
        print(f"ML-B1: Training ({'REAL' if args.real else 'SYNTHETIC'})")
        print("=" * 50)
        _train_rf(args)


if __name__ == "__main__":
    main()
