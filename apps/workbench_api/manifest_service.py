import json
import logging
from pathlib import Path
from typing import Optional

from .main import RunDetail, ArtifactRef, ArtifactDetail

logger = logging.getLogger(__name__)

MANIFEST_GLOB_PATTERNS = [
    "ml/output*/run_manifest.json",
    "ml/data/**/run_manifest.json",
    "ml/**/run_manifest.json",
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _find_all_manifests() -> list[Path]:
    manifests = []
    for pattern in MANIFEST_GLOB_PATTERNS:
        for p in PROJECT_ROOT.glob(pattern):
            if p.exists():
                manifests.append(p)
    return sorted(set(manifests))


def _parse_manifest(path: Path) -> Optional[RunDetail]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to parse manifest %s: %s", path, e)
        return None

    input_assets = [
        f"{a.get('asset_id', '')}@{a.get('metadata_source', '')}"
        for a in data.get("input_assets", [])
    ]
    metadata_sources = list(set(
        a.get("metadata_source", "") for a in data.get("input_assets", [])
    ))

    output_artifacts = [
        ArtifactRef(
            artifact_id=a.get("artifact_id", ""),
            asset_type=a.get("media_type", "application/octet-stream"),
            file_path=a.get("uri", ""),
            sha256=a.get("sha256", ""),
            size_bytes=a.get("size_bytes", 0),
        )
        for a in data.get("output_artifacts", [])
    ]

    git_dirty_str = data.get("git_dirty", "unknown")
    git_dirty = git_dirty_str == "true" if git_dirty_str != "unknown" else False

    return RunDetail(
        run_id=data.get("run_id", ""),
        task_id=data.get("task_id", ""),
        task_spec_ref=data.get("task_spec_ref", ""),
        git_commit=data.get("git_commit", ""),
        git_branch=data.get("git_branch", ""),
        git_dirty=git_dirty,
        started_at=data.get("started_at", ""),
        finished_at=data.get("finished_at", None),
        execution_status=data.get("status", "pending"),
        input_assets=input_assets,
        metadata_sources=metadata_sources,
        config_hash=data.get("config_hash", ""),
        output_artifacts=output_artifacts,
    )


def _build_artifact_index() -> dict[str, ArtifactDetail]:
    index: dict[str, ArtifactDetail] = {}
    for manifest_path in _find_all_manifests():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        run_id = data.get("run_id", "")
        for a in data.get("output_artifacts", []):
            aid = a.get("artifact_id", "")
            if not aid:
                continue
            index[aid] = ArtifactDetail(
                artifact_id=aid,
                run_id=run_id,
                asset_type=a.get("media_type", "application/octet-stream"),
                file_path=a.get("uri", ""),
                sha256=a.get("sha256", ""),
                size_bytes=a.get("size_bytes", 0),
                metadata=data.get("tool_config", {}),
            )
    return index


def get_runs(execution_status: Optional[str] = None) -> list[RunDetail]:
    runs = []
    for path in _find_all_manifests():
        run = _parse_manifest(path)
        if run:
            if execution_status and run.execution_status != execution_status:
                continue
            runs.append(run)
    return runs


def get_run(run_id: str) -> Optional[RunDetail]:
    for path in _find_all_manifests():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("run_id") == run_id:
                return _parse_manifest(path)
        except Exception:
            continue
    return None


def get_artifact(artifact_id: str) -> Optional[ArtifactDetail]:
    index = _build_artifact_index()
    return index.get(artifact_id)
