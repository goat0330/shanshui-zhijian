"""Shared Workbench SQLite location.

Real mode uses one explicit file-backed database so API requests, seed utilities,
and governance services see the same state. Tests may override WORKBENCH_DB_PATH.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_workbench_db_path() -> str:
    raw = os.environ.get("WORKBENCH_DB_PATH")
    path = Path(raw).expanduser() if raw else PROJECT_ROOT / ".runtime" / "workbench.db"
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)
