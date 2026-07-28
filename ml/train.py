import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from ml.artifacts import save_checkpoint, load_checkpoint
from ml.config import TrainConfig
from ml.metrics import accuracy
from ml.run_manifest import MlRunManifest

CHECKPOINT_PATH = Path(__file__).parent / "data" / "checkpoint.joblib"
PYTORCH_CKPT_DIR = Path(__file__).parent / "data" / "pytorch_checkpoints"
METRICS_PATH = Path(__file__).parent / "data" / "train_metrics.json"


def _set_deterministic(seed: int) -> None:
    torch.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        torch.use_deterministic_algorithms(True)
    except RuntimeError:
        pass


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
    _set_deterministic(config.training.seed)

    x_train, y_train = _generate_dummy_data(
        n_samples=config.data.batch_size * 2, seed=config.training.seed)
    x_val, y_val = _generate_dummy_data(
        n_samples=config.data.batch_size, seed=config.training.seed + 1)

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

        manifest.record_metrics({
            f"train_loss_epoch_{epoch}": float(loss.item()),
            f"val_acc_epoch_{epoch}": val_acc,
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "smoke_checkpoint.pt"
    state = {
        "model_state_dict": model.state_dict(),
        "config": config.model_dump(),
        "run_id": run_id,
        "epoch": config.training.max_epochs,
        "seed": config.training.seed,
    }
    save_checkpoint(state, checkpoint_path)

    import hashlib
    ckpt_sha256 = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    ckpt_size = checkpoint_path.stat().st_size

    manifest.record_model_artifact(
        artifact_id="smoke_model", uri=str(checkpoint_path),
        sha256=ckpt_sha256, size_bytes=ckpt_size)
    run_manifest = manifest.finalize()
    run_manifest.tool_config["checkpoint_sha256"] = ckpt_sha256
    run_manifest.tool_config["checkpoint_size_bytes"] = ckpt_size
    run_manifest.tool_config["seed"] = config.training.seed
    run_manifest.tool_config["reproducible"] = True
    run_manifest.manifest_sha256 = run_manifest.compute_manifest_hash()
    manifest_path = output_dir / "run_manifest.json"
    run_manifest.save(manifest_path)

    return checkpoint_path


def _train_rf(seed: int = 42, real: bool = False, s2_path: str | None = None,
              jrc_path: str | None = None, max_samples: int = 50000):
    from ml.data_adapter import load_data
    from ml.model import BaselineModel

    s2 = Path(s2_path) if s2_path else None
    jrc = Path(jrc_path) if jrc_path else None

    (train_X, train_y), (val_X, val_y), (test_X, test_y) = load_data(
        use_real=real, s2_path=s2, jrc_path=jrc, max_samples=max_samples)

    mode = "REAL" if real else "SYNTHETIC"
    print(f"\nData loaded ({mode}):")
    print(f"  Train: {len(train_X)} samples ({train_y.mean():.1%} positive)")
    print(f"  Val:   {len(val_X)} samples ({val_y.mean():.1%} positive)")
    print(f"  Test:  {len(test_X)} samples ({test_y.mean():.1%} positive)")
    print(f"  Features: {list(train_X.columns)}")

    model = BaselineModel(n_estimators=100, max_depth=10, random_state=seed)
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
    return str(CHECKPOINT_PATH)


def main():
    parser = argparse.ArgumentParser(description="ML Training")
    parser.add_argument("--smoke", action="store_true", help="PyTorch smoke test")
    parser.add_argument("--real", action="store_true", help="Use real GeoTIFF data")
    parser.add_argument("--seed", type=int, default=0, help="Random seed")
    parser.add_argument("--run-id", default="", help="Run ID")
    parser.add_argument("--config", default="", help="Config path (smoke mode)")
    parser.add_argument("--output-dir", default="ml/output", help="Output directory (smoke mode)")
    parser.add_argument("--epochs", type=int, default=0, help="Override epochs (smoke mode)")
    parser.add_argument("--s2-path", type=str, default=None, help="S2 GeoTIFF path (real mode)")
    parser.add_argument("--jrc-path", type=str, default=None, help="JRC GeoTIFF path (real mode)")
    parser.add_argument("--max-samples", type=int, default=50000, help="Max training samples")
    args = parser.parse_args()

    seed = args.seed if args.seed > 0 else 42

    print("=" * 50)
    if args.smoke:
        print("ML: Smoke Training (PyTorch)")
        print("=" * 50)
        config = TrainConfig.smoke_defaults()
        if args.epochs > 0:
            config.training.max_epochs = args.epochs
        if args.seed > 0:
            config.training.seed = args.seed
        run_id = args.run_id or f"smoke-{int(time.time())}"
        output_dir = Path(args.output_dir)
        ckpt_path = _train_smoke(config, run_id, output_dir)
        manifest_path = output_dir / "run_manifest.json"
        with open(manifest_path) as f:
            md = json.load(f)
        print(f"Checkpoint : {ckpt_path}")
        print(f"Manifest   : {manifest_path}")
        print(f"Run ID     : {run_id}")
        print(f"Seed       : {config.training.seed}")
        print("SMOKE_OK")
    else:
        mode = "REAL" if args.real else "SYNTHETIC"
        print(f"ML: Training ({mode})")
        print("=" * 50)
        ckpt_path = _train_rf(
            seed=seed, real=args.real, s2_path=args.s2_path,
            jrc_path=args.jrc_path, max_samples=args.max_samples,
        )
        print(f"\nCheckpoint: {ckpt_path}")
        print("Training complete.")


if __name__ == "__main__":
    main()
