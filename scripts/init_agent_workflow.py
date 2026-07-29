#!/usr/bin/env python3
"""Generate project-specific control-plane configs from one profile."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROUTE_NAMES = {
    "perception": "perception",
    "engineering": "engineering",
    "event_governance": "event-governance",
    "product": "product",
    "control_plane": "control-plane",
}
REQUIRED = ("project_name", "base_branch", "owners", "paths", "stable_files", "checks")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(profile: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED if key not in profile]
    if missing:
        raise ValueError(f"missing profile fields: {', '.join(missing)}")
    for key in ROUTE_NAMES:
        if key not in profile["owners"]:
            raise ValueError(f"missing owner: {key}")
        if key not in profile["paths"]:
            raise ValueError(f"missing paths: {key}")
        if key not in profile["checks"]:
            raise ValueError(f"missing checks: {key}")
    for domain, checks in profile["checks"].items():
        for check in checks:
            if not isinstance(check, dict) or not check.get("name") or not isinstance(check.get("command"), list):
                raise ValueError(f"invalid command-object check in {domain}")


def context_config(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": 1,
        "state_dir": profile.get("state_dir", ".agent/context"),
        "reports_dir": profile.get("reports_dir", ".agent/reports"),
        "artifacts_dir": profile.get("artifacts_dir", ".agent/artifacts"),
        "stable_files": profile["stable_files"],
        "limits": {
            "soft_messages": 80, "hard_messages": 120,
            "soft_session_mb": 15, "hard_session_mb": 25,
            "soft_input_tokens": 2_000_000, "hard_input_tokens": 3_500_000,
            "max_full_file_bytes": 200_000, "max_excerpt_lines": 100,
            "max_report_input_lines": 80, "max_report_output_lines": 12,
            "max_result_items": 5, "max_blocker_items": 3,
            "max_bootstrap_lines": 80,
        },
        "domain_paths": {
            "agent-" + key.replace("event_governance", "c").replace("perception", "a").replace("engineering", "b").replace("product", "d").replace("control_plane", "e"): value
            for key, value in profile["paths"].items()
        },
        "compaction": {"enabled": False, "command": []},
    }


def ensemble_config(profile: dict[str, Any]) -> dict[str, Any]:
    routes = []
    for key in ROUTE_NAMES:
        routes.append({
            "name": ROUTE_NAMES[key],
            "owner": profile["owners"][key],
            "paths": profile["paths"][key],
            "checks": profile["checks"][key],
        })
    routes.append({"name": "default", "owner": profile["owners"]["control_plane"], "paths": ["**"], "checks": []})
    return {
        "version": 1,
        "base_branch": profile["base_branch"],
        "routes": routes,
        "minimum_checks": {},
        "escalate": [
            {"name": "agent-runtime", "paths": [".opencode/**", ".agent/**", "**/opencode.json", "**/opencode.jsonc", "**/AGENTS.md"], "reason": "Agent runtime or startup configuration changed"},
            {"name": "public-contract", "paths": ["core/schemas/contracts/**", "contracts/**", "**/schema/**", "**/schemas/**", "**/openapi.*"], "reason": "Public contract or shared schema changed"},
        ],
        "limits": {"max_files_without_escalation": 25, "max_changed_lines_without_escalation": 800, "max_routes_without_escalation": 1, "success_excerpt_lines": 5, "failure_excerpt_lines": 36, "command_timeout_sec": 300},
    }


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--profile", default=".agent/project-profile.json")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    profile_path = (repo / args.profile).resolve() if not Path(args.profile).is_absolute() else Path(args.profile).resolve()
    profile = read_json(profile_path)
    validate(profile)
    generated = {"context": context_config(profile), "ensemble": ensemble_config(profile)}
    if args.write:
        write(repo / ".opencode/context-governor.json", generated["context"])
        write(repo / ".opencode/ensemble-efficiency.json", generated["ensemble"])
    encoded = json.dumps(generated, ensure_ascii=False, sort_keys=True).encode("utf-8")
    print(json.dumps({"project": profile["project_name"], "write": args.write, "config_sha256": hashlib.sha256(encoded).hexdigest(), "routes": [r["name"] for r in generated["ensemble"]["routes"]]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
