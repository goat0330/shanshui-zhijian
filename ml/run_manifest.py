"""Small ML-specific facade over the frozen RunManifest contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from core.schemas.contracts.run_manifest import RunManifest, RunManifestBuilder, RunStatus


class MlRunManifest:
    def __init__(self, run_id: str, seed: int = 42, run_command: str | None = None):
        self.run_id = run_id
        self.seed = seed
        self.run_command = run_command or f"python -m ml.train --run-id={run_id}"
        self._builder = RunManifestBuilder()
        self._builder.record_start(run_id=run_id)
        self._metrics: dict[str, float] = {}

    def record_config(self, config: Any) -> None:
        if hasattr(config, "model_dump_json"):
            config_text = config.model_dump_json()
        else:
            config_text = json.dumps(config, default=str, sort_keys=True)
        self._builder.record_config_hash(self._hash_str(config_text))

    def record_dataset(self, name: str, path: str | Path, sha256: str = "") -> None:
        self._builder.record_input_asset(
            asset_id=name,
            uri=str(path),
            sha256=sha256,
            metadata_source="ml_pipeline",
        )

    def record_model_artifact(
        self,
        artifact_id: str,
        uri: str | Path,
        sha256: str = "",
        size_bytes: int = 0,
        media_type: str = "application/octet-stream",
    ) -> None:
        self._builder.record_output_artifact(
            artifact_id=artifact_id,
            uri=str(uri),
            sha256=sha256,
            size_bytes=size_bytes,
            media_type=media_type,
        )

    def record_metrics(self, metrics: dict[str, float]) -> None:
        self._metrics.update(metrics)

    def finalize(self, status: RunStatus = RunStatus.SUCCEEDED) -> RunManifest:
        manifest = self._builder.finalize(status)
        manifest.tool_config["metrics"] = self._metrics
        manifest.tool_config["seed"] = self.seed
        manifest.producer_version = "ml-train@v0.1.1"
        manifest.run_command = self.run_command
        manifest.random_seed = self.seed
        manifest.code_version = "0.1.1"
        manifest.manifest_sha256 = manifest.compute_manifest_hash()
        return manifest

    def save(self, path: str | Path) -> Path:
        return self.finalize().save(path)

    @staticmethod
    def _hash_str(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def create_from_manifest(manifest: RunManifest) -> "MlRunManifest":
        wrapped = MlRunManifest(manifest.run_id, seed=manifest.random_seed or 42)
        wrapped._builder._manifest = manifest
        return wrapped
