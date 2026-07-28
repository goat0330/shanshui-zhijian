import hashlib
import json
from pathlib import Path
from typing import Any

from core.schemas.contracts.run_manifest import (
    RunManifest,
    RunManifestBuilder,
    RunStatus,
)


class MlRunManifest:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self._builder = RunManifestBuilder()
        self._builder.record_start(run_id=run_id)
        self._metrics: dict[str, float] = {}
        self._full_config: dict | None = None

    def record_config(self, config: Any) -> None:
        if hasattr(config, "model_dump"):
            raw = config.model_dump(mode="json")
        elif hasattr(config, "model_dump_json"):
            raw = json.loads(config.model_dump_json())
        else:
            raw = dict(config) if isinstance(config, dict) else {"raw": str(config)}
        self._full_config = raw
        self._builder.record_config_hash(
            hashlib.sha256(
                json.dumps(raw, sort_keys=True).encode("utf-8")
            ).hexdigest()
        )

    def record_dataset(self, name: str, path: str | Path, sha256: str = "") -> None:
        self._builder.record_input_asset(
            asset_id=name,
            uri=str(path),
            sha256=sha256 or "",
            metadata_source="ml_pipeline",
        )

    def record_model_artifact(
        self, artifact_id: str, uri: str | Path,
        sha256: str = "", size_bytes: int = 0,
    ) -> None:
        self._builder.record_output_artifact(
            artifact_id=artifact_id,
            uri=str(uri),
            sha256=sha256,
            size_bytes=size_bytes,
            media_type="application/octet-stream",
        )

    def record_metrics(self, metrics: dict[str, float]) -> None:
        self._metrics.update(metrics)

    def finalize(self, status: RunStatus = RunStatus.SUCCEEDED) -> RunManifest:
        manifest = self._builder.finalize(status)
        manifest.tool_config["metrics"] = self._metrics
        if self._full_config:
            manifest.tool_config["training_config"] = self._full_config
        manifest.producer_version = "ml-train@v0.1.0"
        manifest.run_command = f"python -m ml.train --run-id={self.run_id}"
        manifest.code_version = "0.1.0"
        manifest.manifest_sha256 = manifest.compute_manifest_hash()
        return manifest

    def save(self, path: str | Path) -> Path:
        manifest = self.finalize()
        return manifest.save(path)


def build_ml_manifest(
    run_id: str,
    config: Any = None,
    metrics: dict[str, float] | None = None,
    checkpoint_path: str | Path | None = None,
    dataset_paths: dict[str, str] | None = None,
    seed: int | None = None,
    status: RunStatus = RunStatus.SUCCEEDED,
) -> RunManifest:
    manifest = MlRunManifest(run_id=run_id)
    if config is not None:
        manifest.record_config(config)

    if metrics:
        manifest.record_metrics(metrics)

    if dataset_paths:
        for name, path in dataset_paths.items():
            manifest.record_dataset(name, path)

    if checkpoint_path:
        p = Path(checkpoint_path)
        sha = ""
        size = 0
        if p.exists():
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            size = p.stat().st_size
        manifest.record_model_artifact(
            artifact_id="model_checkpoint",
            uri=str(p),
            sha256=sha,
            size_bytes=size,
        )

    run_manifest = manifest.finalize(status)
    run_manifest.random_seed = seed
    run_manifest.manifest_sha256 = run_manifest.compute_manifest_hash()
    return run_manifest
