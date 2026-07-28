import argparse
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


def _train_smoke(config: TrainConfig, run_id: str, output_dir: Path) -> Path:
    torch.manual_seed(config.training.seed)
    np.random.seed(config.training.seed)

    x_train, y_train = _generate_dummy_data(
        n_samples=config.data.batch_size * 2,
        seed=config.training.seed,
    )
    x_val, y_val = _generate_dummy_data(
        n_samples=config.data.batch_size,
        seed=config.training.seed + 1,
    )

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
    }
    save_checkpoint(state, checkpoint_path)

    manifest.record_model_artifact(
        artifact_id="smoke_model",
        uri=str(checkpoint_path),
        size_bytes=checkpoint_path.stat().st_size,
    )
    manifest_path = output_dir / "run_manifest.json"
    manifest.save(manifest_path)

    return checkpoint_path


def main():
    parser = argparse.ArgumentParser(description="ML Training Pipeline")
    parser.add_argument("--smoke", action="store_true", help="Run smoke test")
    parser.add_argument("--run-id", default="", help="Run ID")
    parser.add_argument("--config", default="", help="Path to config JSON")
    parser.add_argument("--output-dir", default="ml/output", help="Output directory")
    parser.add_argument("--epochs", type=int, default=0, help="Override epochs")
    args = parser.parse_args()

    if args.smoke:
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
        parser.print_help()


if __name__ == "__main__":
    main()
