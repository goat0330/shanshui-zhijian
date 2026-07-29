"""Deterministic smoke and RandomForest training entry point."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        self.net = nn.Sequential(nn.Linear(input_dim, 16), nn.ReLU(), nn.Linear(16, num_classes))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def _generate_dummy_data(n_samples=64, input_dim=10, num_classes=2, seed=42):
    rng = np.random.RandomState(seed)
    x = rng.randn(n_samples, input_dim).astype(np.float32)
    y = rng.randint(0, num_classes, size=n_samples).astype(np.int64)
    return torch.from_numpy(x), torch.from_numpy(y)


def _train_smoke(config: TrainConfig, run_id: str, output_dir: Path) -> Path:
    _set_deterministic(config.training.seed)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    train_x, train_y = _generate_dummy_data(config.data.batch_size * 2, seed=config.training.seed)
    val_x, val_y = _generate_dummy_data(config.data.batch_size, seed=config.training.seed + 1)
    model = _SimpleModel(input_dim=10, num_classes=config.model.num_classes)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=config.training.learning_rate)
    manifest = MlRunManifest(
        run_id,
        seed=config.training.seed,
        run_command=f"python -m ml.train --smoke --seed {config.training.seed} --run-id {run_id}",
    )
    manifest.record_config(config)
    manifest.record_dataset("train_smoke", output_dir / "data")

    for epoch in range(config.training.max_epochs):
        model.train()
        optimizer.zero_grad()
        logits = model(train_x)
        loss = criterion(logits, train_y)
        loss.backward()
        optimizer.step()
        model.eval()
        with torch.no_grad():
            prediction = model(val_x).argmax(dim=1).numpy()
        manifest.record_metrics({
            f"train_loss_epoch_{epoch}": float(loss.item()),
            f"val_acc_epoch_{epoch}": accuracy(val_y.numpy(), prediction),
        })

    checkpoint_path = output_dir / "smoke_checkpoint.pt"
    save_checkpoint({
        "model_state_dict": model.state_dict(),
        "config": config.model_dump(),
        "run_id": run_id,
        "epoch": config.training.max_epochs,
        "seed": config.training.seed,
    }, checkpoint_path)
    digest = _sha256(checkpoint_path)
    manifest.record_model_artifact(
        "smoke_model",
        checkpoint_path,
        sha256=digest,
        size_bytes=checkpoint_path.stat().st_size,
        media_type="application/x-pytorch",
    )
    run_manifest = manifest.finalize()
    run_manifest.tool_config.update({
        "checkpoint_sha256": digest,
        "checkpoint_size_bytes": checkpoint_path.stat().st_size,
        "reproducible": True,
    })
    run_manifest.manifest_sha256 = run_manifest.compute_manifest_hash()
    run_manifest.save(output_dir / "run_manifest.json")
    return checkpoint_path


def _train_rf(
    seed: int = 42,
    real: bool = False,
    s2_path: str | None = None,
    jrc_path: str | None = None,
    max_samples: int = 50_000,
    output_dir: Path | None = None,
    run_id: str | None = None,
) -> str:
    from ml.data_adapter import load_data
    from ml.model import BaselineModel

    mode = "real" if real else "synthetic"
    run_id = run_id or f"rf-{mode}-{int(time.time())}"
    output = Path(output_dir) if output_dir else CHECKPOINT_PATH.parent
    output.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output / ("checkpoint.joblib" if output_dir else CHECKPOINT_PATH.name)
    metrics_path = output / "train_metrics.json"
    split_path = output / "split_manifest.json"

    datasets = load_data(
        use_real=real,
        s2_path=Path(s2_path) if s2_path else None,
        jrc_path=Path(jrc_path) if jrc_path else None,
        max_samples=max_samples,
        random_state=seed,
    )
    (train_x, train_y), (val_x, val_y), (test_x, test_y) = datasets
    model = BaselineModel(n_estimators=100, max_depth=10, random_state=seed)
    model.train(train_x, train_y)
    metrics = {
        "train": model.evaluate(train_x, train_y),
        "val": model.evaluate(val_x, val_y),
        "test": model.evaluate(test_x, test_y),
    }
    model.save(checkpoint_path)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    split_manifest = {
        "run_id": run_id,
        "mode": mode,
        "seed": seed,
        "split_method": "spatial_blocks" if real else "pre_generated_csv",
        "counts": {"train": len(train_x), "val": len(val_x), "test": len(test_x)},
        "features": list(train_x.columns),
        "leakage_policy": "No spatial block may occur in more than one split" if real else "Synthetic fixed fixtures",
        "label_semantics": "JRC occurrence > 50 weak stable-water label" if real else "Synthetic anomaly fixture",
    }
    split_path.write_text(json.dumps(split_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest = MlRunManifest(
        run_id,
        seed=seed,
        run_command=f"python -m ml.train {'--real ' if real else ''}--seed {seed}",
    )
    manifest.record_config({
        "mode": mode,
        "seed": seed,
        "n_estimators": model.n_estimators,
        "max_depth": model.max_depth,
        "max_samples": max_samples,
        "features": list(train_x.columns),
    })
    if real:
        manifest.record_dataset("sentinel2_t1", s2_path or "data/chongqing_demo/raw/s2_t1.tif")
        manifest.record_dataset("jrc_stable_water_weak_label", jrc_path or "data/chongqing_demo/raw/jrc_water_occurrence.tif")
    else:
        manifest.record_dataset("synthetic_train", Path(__file__).parent / "data" / "train.csv")
    manifest.record_metrics({
        f"{split}_{metric}": float(value)
        for split, values in metrics.items()
        for metric, value in values.items()
        if isinstance(value, (int, float))
    })
    manifest.record_model_artifact(
        "water_rf_model",
        checkpoint_path,
        sha256=_sha256(checkpoint_path),
        size_bytes=checkpoint_path.stat().st_size,
        media_type="application/x-joblib",
    )
    manifest.record_model_artifact(
        "metrics",
        metrics_path,
        sha256=_sha256(metrics_path),
        size_bytes=metrics_path.stat().st_size,
        media_type="application/json",
    )
    manifest.record_model_artifact(
        "split_manifest",
        split_path,
        sha256=_sha256(split_path),
        size_bytes=split_path.stat().st_size,
        media_type="application/json",
    )
    manifest.save(output / "run_manifest.json")

    # Keep legacy locations working only when the legacy output mode is used.
    if output_dir is None:
        METRICS_PATH.write_text(metrics_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Data mode: {mode.upper()}")
    print(f"Train/Val/Test: {len(train_x)}/{len(val_x)}/{len(test_x)}")
    print(f"Checkpoint: {checkpoint_path}")
    print(f"RunManifest: {output / 'run_manifest.json'}")
    return str(checkpoint_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="ML Training")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--config", default="")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--epochs", type=int, default=0)
    parser.add_argument("--s2-path", type=str, default=None)
    parser.add_argument("--jrc-path", type=str, default=None)
    parser.add_argument("--max-samples", type=int, default=50_000)
    args = parser.parse_args()
    if args.seed < 0:
        parser.error("--seed must be non-negative")

    if args.smoke:
        config = TrainConfig.smoke_defaults()
        config.training.seed = args.seed
        if args.epochs > 0:
            config.training.max_epochs = args.epochs
        run_id = args.run_id or f"smoke-{int(time.time())}"
        checkpoint = _train_smoke(config, run_id, Path(args.output_dir or "ml/output"))
        print(f"Checkpoint: {checkpoint}")
        print("SMOKE_OK")
        return

    checkpoint = _train_rf(
        seed=args.seed,
        real=args.real,
        s2_path=args.s2_path,
        jrc_path=args.jrc_path,
        max_samples=args.max_samples,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        run_id=args.run_id or None,
    )
    print(f"Checkpoint: {checkpoint}")
    print("Training complete.")


if __name__ == "__main__":
    main()
