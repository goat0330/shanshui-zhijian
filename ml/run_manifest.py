from datetime import datetime, timezone
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

    def record_config(self, config: Any) -> None:
        if hasattr(config, "model_dump_json"):
            config_str = config.model_dump_json()
        else:
            import json
            config_str = json.dumps(config, default=str)
        self._builder.record_config_hash(
            self._hash_str(config_str)
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
        manifest.producer_version = "ml-train@v0.1.0"
        manifest.run_command = (
            f"python -m ml.train --run-id={self.run_id}"
        )
        manifest.random_seed = 42
        manifest.code_version = "0.1.0"
        manifest.manifest_sha256 = manifest.compute_manifest_hash()
        return manifest

    def save(self, path: str | Path) -> Path:
        manifest = self.finalize()
        return manifest.save(path)

    @staticmethod
    def _hash_str(text: str) -> str:
        import hashlib
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def create_from_manifest(manifest: RunManifest) -> "MlRunManifest":
        wrapped = MlRunManifest(manifest.run_id)
        wrapped._builder._manifest = manifest
        return wrapped
