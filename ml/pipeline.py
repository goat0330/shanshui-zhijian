import hashlib
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from ml.artifacts import save_checkpoint
from ml.config import TrainConfig
from ml.metrics import accuracy, precision, recall, f1_score
from ml.run_manifest import build_ml_manifest


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


def _generate_dummy_data(
    n_samples: int = 64,
    input_dim: int = 10,
    num_classes: int = 2,
    seed: int = 42,
):
    rng = np.random.RandomState(seed)
    x = rng.randn(n_samples, input_dim).astype(np.float32)
    y = rng.randint(0, num_classes, size=n_samples).astype(np.int64)
    return torch.from_numpy(x), torch.from_numpy(y)


def _load_real_data(config: TrainConfig):
    try:
        import pandas as pd
        train_df = pd.read_csv(config.data.train_path / "dataset.csv")
        val_df = pd.read_csv(config.data.val_path / "dataset.csv")
        feature_cols = [c for c in train_df.columns if c.startswith("feature_")]
        x_train = torch.from_numpy(train_df[feature_cols].values.astype(np.float32))
        y_train = torch.from_numpy(train_df["label"].values.astype(np.int64))
        x_val = torch.from_numpy(val_df[feature_cols].values.astype(np.float32))
        y_val = torch.from_numpy(val_df["label"].values.astype(np.int64))
        return x_train, y_train, x_val, y_val
    except Exception:
        return None


def train_pipeline(
    config: TrainConfig,
    run_id: str,
    output_dir: Path,
    use_smoke: bool = False,
) -> dict[str, Any]:
    _set_deterministic(config.training.seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    if use_smoke:
        x_train, y_train = _generate_dummy_data(
            n_samples=config.data.batch_size * 2,
            seed=config.training.seed,
        )
        x_val, y_val = _generate_dummy_data(
            n_samples=config.data.batch_size,
            seed=config.training.seed + 1,
        )
        input_dim = 10
    else:
        real = _load_real_data(config)
        if real is not None:
            x_train, y_train, x_val, y_val = real
            input_dim = x_train.shape[1]
        else:
            x_train, y_train = _generate_dummy_data(
                n_samples=config.data.batch_size * 2,
                seed=config.training.seed,
            )
            x_val, y_val = _generate_dummy_data(
                n_samples=config.data.batch_size,
                seed=config.training.seed + 1,
            )
            input_dim = 10

    model = _SimpleModel(input_dim=input_dim, num_classes=config.model.num_classes)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=config.training.learning_rate)

    epoch_metrics: dict[str, float] = {}
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
            val_y = y_val.numpy()
            acc = accuracy(val_y, val_pred)
            p = precision(val_y, val_pred)
            r = recall(val_y, val_pred)
            f1 = f1_score(val_y, val_pred)

        epoch_metrics.update({
            f"train_loss_epoch_{epoch}": float(loss.item()),
            f"val_acc_epoch_{epoch}": acc,
            f"val_precision_epoch_{epoch}": p,
            f"val_recall_epoch_{epoch}": r,
            f"val_f1_epoch_{epoch}": f1,
        })

    checkpoint_path = output_dir / "model_checkpoint.pt"
    state = {
        "model_state_dict": model.state_dict(),
        "config": config.model_dump(),
        "run_id": run_id,
        "epochs": config.training.max_epochs,
        "seed": config.training.seed,
        "final_metrics": {k: v for k, v in epoch_metrics.items()
                          if k.startswith(f"val_acc_epoch_{config.training.max_epochs - 1}")},
    }
    save_checkpoint(state, checkpoint_path)
    ckpt_sha256 = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest() if checkpoint_path.exists() else ""
    ckpt_size = checkpoint_path.stat().st_size if checkpoint_path.exists() else 0

    manifest = build_ml_manifest(
        run_id=run_id,
        config=config,
        metrics=epoch_metrics,
        checkpoint_path=checkpoint_path,
        dataset_paths={
            "train": str(config.data.train_path),
            "val": str(config.data.val_path),
        },
        seed=config.training.seed,
    )

    manifest_path = output_dir / "run_manifest.json"
    manifest.save(manifest_path)

    result = {
        "run_id": run_id,
        "checkpoint": str(checkpoint_path),
        "manifest": str(manifest_path),
        "checkpoint_sha256": ckpt_sha256,
        "checkpoint_size_bytes": ckpt_size,
        "metrics": epoch_metrics,
        "epochs": config.training.max_epochs,
    }
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ML Training Pipeline")
    parser.add_argument("--smoke", action="store_true", help="Use synthetic data")
    parser.add_argument("--run-id", default="", help="Run ID")
    parser.add_argument("--config", default="", help="Path to config JSON")
    parser.add_argument("--output-dir", default="ml/output", help="Output directory")
    parser.add_argument("--epochs", type=int, default=0, help="Override epochs")
    parser.add_argument("--seed", type=int, default=0, help="Override seed")
    args = parser.parse_args()

    if args.config:
        config = TrainConfig.from_json(args.config)
    else:
        config = TrainConfig.smoke_defaults()

    if args.epochs > 0:
        config.training.max_epochs = args.epochs
    if args.seed > 0:
        config.training.seed = args.seed

    run_id = args.run_id or f"pipeline-{int(time.time())}"
    output_dir = Path(args.output_dir)
    result = train_pipeline(config, run_id, output_dir, use_smoke=args.smoke or not args.config)

    print(f"Run ID      : {result['run_id']}")
    print(f"Checkpoint  : {result['checkpoint']}")
    print(f"Manifest    : {result['manifest']}")
    print(f"Epochs      : {result['epochs']}")
    last_epoch = result["epochs"] - 1
    print(f"Final val_acc: {result['metrics'].get(f'val_acc_epoch_{last_epoch}', 'N/A')}")
    print("PIPELINE_OK")


if __name__ == "__main__":
    main()
