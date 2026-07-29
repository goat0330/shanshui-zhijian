"""Deterministic real-mode seed for Playwright/CI.

This module writes to the same SQLite file used by the Workbench API. It is
never invoked automatically by production code.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from .db import PROJECT_ROOT, get_workbench_db_path


def _write_run_manifest() -> Path:
    output_dir = PROJECT_ROOT / "ml" / "output-e2e"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / "e2e_model.joblib"
    artifact.write_bytes(b"cycle311-e2e-model-placeholder\n")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()

    manifest = {
        "run_id": "run-e2e-001",
        "task_id": "task-e2e-001",
        "task_spec_ref": "ml-water-change-v1@0.1.0",
        "status": "succeeded",
        "started_at": "2026-06-15T02:00:00Z",
        "finished_at": "2026-06-15T02:05:00Z",
        "git_commit": "cycle311-e2e",
        "git_branch": "integration/g0-g1-contract-freeze",
        "git_dirty": "false",
        "config_hash": hashlib.sha256(b"cycle311-e2e-config").hexdigest(),
        "input_assets": [
            {
                "asset_id": "S2-T1-E2E",
                "uri": "fixtures/s2_t1.tif",
                "sha256": "",
                "metadata_source": "cycle311-e2e-seed",
            },
            {
                "asset_id": "S2-T2-E2E",
                "uri": "fixtures/s2_t2.tif",
                "sha256": "",
                "metadata_source": "cycle311-e2e-seed",
            },
        ],
        "output_artifacts": [
            {
                "artifact_id": "e2e-model",
                "media_type": "application/octet-stream",
                "uri": str(artifact),
                "sha256": digest,
                "size_bytes": artifact.stat().st_size,
            }
        ],
        "tool_config": {"mode": "real-e2e", "seed": 42},
    }
    manifest_path = output_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def main() -> None:
    db_path = Path(get_workbench_db_path())
    if os.environ.get("E2E_RESET_DB", "1") == "1" and db_path.exists():
        db_path.unlink()

    output_dir = PROJECT_ROOT / "ml" / "output-e2e"
    if os.environ.get("E2E_RESET_DB", "1") == "1" and output_dir.exists():
        shutil.rmtree(output_dir)

    # Import after reset so no cached connection points at the old file.
    from .candidate_store import seed_demo_candidates
    from .real_service import reset_session, submit_review

    reset_session()
    inserted = seed_demo_candidates(count=36, replace=False)
    submit_review("CAND-0036", {
        "action": "confirm",
        "comment": "Cycle 3.1.1 real-mode E2E seed event",
        "actor_ref": "ci-seed",
        "base_version": 1,
    })
    manifest_path = _write_run_manifest()
    print(f"Seeded {inserted} candidates into {db_path}")
    print(f"Seeded event for CAND-0036")
    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()
