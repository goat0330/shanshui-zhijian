#!/usr/bin/env python3
"""Safe dispatch preflight; it never sends Team messages or edits runtime state."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

GOVERNOR = ".opencode/skills/agent-e-context-governor/scripts/context_governor.py"
ENSEMBLE = "C:/Users/WangChi/.agents/skills/ensemble-efficiency/scripts/ensemble_efficiency.py"
CONTROL_FILES = ("AGENTS.md", ".agent/project-profile.json", ".opencode/context-governor.json", ".opencode/ensemble-efficiency.json")


def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=str(cwd), text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def git(repo: Path, *args: str) -> str:
    result = run(["git", *args], repo)
    if result.returncode:
        raise RuntimeError(result.stdout.strip() or f"git failed: {' '.join(args)}")
    return result.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate a work package before Team dispatch")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--owner", required=True)
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--base", required=True, help="Required fixed base; use HEAD for fixtures")
    ap.add_argument("--worktree")
    ap.add_argument("--no-external-checks", action="store_true")
    ap.add_argument("--write-manifest", action="store_true")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    result: dict[str, Any] = {"task_id": args.task_id, "owner": args.owner, "repo": str(repo), "base": args.base, "dispatch_allowed": False, "reasons": []}
    try:
        if not repo.is_dir():
            raise RuntimeError(f"repo not found: {repo}")
        if Path(git(repo, "rev-parse", "--show-toplevel")).resolve() != repo:
            raise RuntimeError("repo is not the Git worktree root")
        git(repo, "rev-parse", "--verify", args.base)
        result["branch"] = git(repo, "branch", "--show-current")
        result["head"] = git(repo, "rev-parse", "--short=12", "HEAD")
        result["base_resolved"] = git(repo, "rev-parse", "--short=12", args.base)
        missing = [p for p in CONTROL_FILES if not git(repo, "ls-files", "--error-unmatch", p)]
        if missing:
            raise RuntimeError("control-plane files are not tracked: " + ", ".join(missing))
        dirty_control = [p for p in git(repo, "diff", "--name-only", "--", *CONTROL_FILES).splitlines() if p]
        if dirty_control:
            raise RuntimeError("frozen control-plane files are dirty: " + ", ".join(dirty_control))
        if args.worktree:
            worktree = Path(args.worktree).resolve()
            entries = git(repo, "worktree", "list", "--porcelain")
            if str(worktree).replace("\\", "/") not in entries.replace("\\", "/"):
                raise RuntimeError(f"worktree is not registered: {worktree}")
            result["worktree"] = str(worktree)
        gov = run([sys.executable, "-X", "utf8", GOVERNOR, "--repo", str(repo), "preflight", "--json"], repo)
        result["preflight"] = {"returncode": gov.returncode, "output": gov.stdout[-4000:]}
        if gov.returncode == 2:
            raise RuntimeError("HARD_LIMIT: dispatch is forbidden")
        if gov.returncode == 1:
            raise RuntimeError("SOFT_LIMIT: finish current atomic step before dispatch")
        cmd = [sys.executable, ENSEMBLE, "--repo", str(repo), "--base", args.base, "--owner", args.owner, "--task-id", args.task_id, "--json"]
        if args.no_external_checks:
            cmd.append("--no-external-checks")
        gate = run(cmd, repo)
        result["ensemble"] = {"returncode": gate.returncode, "output": gate.stdout[-8000:]}
        if gate.returncode not in (0, 2):
            raise RuntimeError("Ensemble gate failed before dispatch")
        result["dispatch_allowed"] = gate.returncode == 0
        if gate.returncode == 2:
            result["reasons"].append("Ensemble requires Agent E review before dispatch")
    except Exception as exc:
        result["reasons"].append(str(exc))
    if args.write_manifest:
        path = repo / ".agent/artifacts/dispatch" / f"{args.task_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result["manifest"] = str(path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["dispatch_allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
