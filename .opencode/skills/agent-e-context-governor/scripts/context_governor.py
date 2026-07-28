#!/usr/bin/env python3
"""Low-token context guard for Agent E. Standard library only."""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

DEFAULT = {
    "version": 1,
    "state_dir": ".agent/context",
    "reports_dir": ".agent/reports",
    "artifacts_dir": ".agent/artifacts",
    "stable_files": [
        "AGENTS.md", "agents/sessions.yml", "STATUS_BOARD.md",
        ".opencode/ensemble-efficiency.json", ".opencode/context-governor.json"
    ],
    "limits": {
        "soft_messages": 80, "hard_messages": 120,
        "soft_session_mb": 15, "hard_session_mb": 25,
        "soft_input_tokens": 2_000_000, "hard_input_tokens": 3_500_000,
        "max_full_file_bytes": 200_000, "max_excerpt_lines": 100,
        "max_report_input_lines": 80, "max_report_output_lines": 12,
        "max_result_items": 5, "max_blocker_items": 3,
        "max_bootstrap_lines": 80,
    },
    "domain_paths": {},
    "compaction": {"enabled": False, "command": []},
}


class GovError(RuntimeError):
    pass


def proc(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=str(cwd), stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True,
                          encoding="utf-8", errors="replace", check=False)


def root_of(start: Path) -> Path:
    cp = proc(["git", "rev-parse", "--show-toplevel"], start)
    if cp.returncode:
        raise GovError("Current directory is not inside a Git worktree")
    return Path(cp.stdout.strip()).resolve()


def git(root: Path, *args: str) -> str:
    return proc(["git", *args], root).stdout.strip()


def merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(a))
    for k, v in b.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def config(root: Path) -> dict[str, Any]:
    p = root / ".opencode/context-governor.json"
    if not p.exists():
        return DEFAULT
    try:
        return merge(DEFAULT, json.loads(p.read_text(encoding="utf-8")))
    except Exception as exc:
        raise GovError(f"Invalid config {p}: {exc}") from exc


def pmap(root: Path, cfg: dict[str, Any]) -> dict[str, Path]:
    state = root / cfg["state_dir"]
    return {
        "state": state,
        "reports": root / cfg["reports_dir"],
        "artifacts": root / cfg["artifacts_dir"],
        "registry": state / "read_registry.json",
        "ledger": state / "ledger.json",
        "brief": state / "BRIEF.md",
        "current_state": state / "CURRENT_STATE.md",
        "current_cycle": state / "CURRENT_CYCLE.md",
        "decisions": state / "DECISIONS.md",
        "handoff": state / "SESSION_HANDOFF.md",
    }


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def init(root: Path, cfg: dict[str, Any]) -> dict[str, Path]:
    ps = pmap(root, cfg)
    for key in ("state", "reports", "artifacts"):
        ps[key].mkdir(parents=True, exist_ok=True)
    tdir = Path(__file__).resolve().parent.parent / "templates"
    templates = {
        "current_state": "CURRENT_STATE.md",
        "current_cycle": "CURRENT_CYCLE.md",
        "decisions": "DECISIONS.md",
        "handoff": "SESSION_HANDOFF.md",
    }
    for key, name in templates.items():
        if not ps[key].exists():
            src = tdir / name
            shutil.copyfile(src, ps[key]) if src.exists() else ps[key].write_text(f"# {name}\n", encoding="utf-8")
    if not ps["registry"].exists():
        write_json(ps["registry"], {"version": 1, "files": {}})
    if not ps["ledger"].exists():
        write_json(ps["ledger"], {
            "version": 1, "created_at": now(), "full_reads": 0,
            "full_read_bytes": 0, "excerpt_reads": 0, "excerpt_lines": 0,
            "reports_ingested": 0, "report_input_lines": 0,
            "messages": None, "session_mb": None, "input_tokens": None,
            "last_action": "init"
        })
    return ps


def rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve(root: Path, raw: str) -> Path:
    p = Path(raw)
    return p.resolve() if p.is_absolute() else (root / p).resolve()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pat) for pat in patterns)


def owner(path: str, cfg: dict[str, Any]) -> str | None:
    for name, patterns in cfg.get("domain_paths", {}).items():
        if matches(path, patterns):
            return name
    return None


def add_ledger(ps: dict[str, Path], **increments: int) -> dict[str, Any]:
    data = read_json(ps["ledger"], {})
    for k, v in increments.items():
        data[k] = int(data.get(k) or 0) + int(v)
    data["updated_at"] = now()
    write_json(ps["ledger"], data)
    return data


def guard(root: Path, cfg: dict[str, Any], raw: str, force: bool) -> dict[str, Any]:
    ps = pmap(root, cfg)
    target = resolve(root, raw)
    if not target.is_file():
        raise GovError(f"File not found: {target}")
    rp, size, sha = rel(root, target), target.stat().st_size, digest(target)
    reg = read_json(ps["registry"], {"version": 1, "files": {}})
    prev = reg["files"].get(rp)
    maxb = int(cfg["limits"]["max_full_file_bytes"])
    own = owner(rp, cfg)
    stable = matches(rp, cfg.get("stable_files", []))

    if prev and prev.get("sha256") == sha and stable and not force:
        decision, reason = "SKIP_UNCHANGED", "Stable file hash is unchanged"
    elif size > maxb * 4 and own not in (None, "agent-e") and not force:
        decision, reason = "DELEGATE_OWNER", f"Large domain file; ask {own} for a compact finding"
    elif size > maxb and not force:
        decision, reason = "ALLOW_EXCERPT", f"File exceeds full-read limit ({size} > {maxb})"
    elif size > maxb * 4 and force:
        decision, reason = "DENY_LARGE", "Forced full read denied; use excerpt or owner report"
    else:
        decision, reason = "ALLOW_FULL", "Within limit or changed since last read"

    if decision == "ALLOW_FULL":
        reg["files"][rp] = {"sha256": sha, "bytes": size, "last_full_read_at": now()}
        write_json(ps["registry"], reg)
        add_ledger(ps, full_reads=1, full_read_bytes=size)
    return {"decision": decision, "path": rp, "bytes": size, "sha256": sha,
            "owner": own, "reason": reason}


def excerpt(root: Path, cfg: dict[str, Any], raw: str, query: str,
            context: int, max_lines: int) -> str:
    ps = pmap(root, cfg)
    target = resolve(root, raw)
    if not target.is_file():
        raise GovError(f"File not found: {target}")
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    try:
        pat = re.compile(query, re.I)
    except re.error:
        pat = re.compile(re.escape(query), re.I)
    chosen: set[int] = set()
    for i, line in enumerate(lines):
        if pat.search(line):
            chosen.update(range(max(0, i-context), min(len(lines), i+context+1)))
        if len(chosen) >= max_lines:
            break
    out, last = [], -2
    for i in sorted(chosen)[:max_lines]:
        if i > last + 1:
            out.append("...")
        out.append(f"{i+1}: {lines[i]}")
        last = i
    add_ledger(ps, excerpt_reads=1, excerpt_lines=len(out))
    return "\n".join(out) if out else "NO_MATCH"


def compact_report(data: dict[str, Any], agent: str, task: str, limit: int) -> str:
    tests = data.get("tests", [])
    p = sum(t.get("status") == "PASS" for t in tests)
    f = sum(t.get("status") == "FAIL" for t in tests)
    s = sum(t.get("status") == "SKIP" for t in tests)
    lines = [
        f"STATUS: {data.get('status', 'UNKNOWN')}",
        f"OWNER/TASK: {agent} / {task}",
        f"BRANCH/HEAD: {data.get('branch', '')} / {data.get('head', '')}",
        f"PR: {data.get('pr') or 'none'}",
        f"TESTS: {p} pass, {f} fail, {s} skip",
    ]
    lines += [f"RESULT: {x}" for x in data.get("result", [])[:5]]
    lines += [f"BLOCKER: {x}" for x in data.get("blockers", [])[:3]]
    return "\n".join(lines[:limit])


def ingest(root: Path, cfg: dict[str, Any], raw: str, agent: str,
           task: str, cycle: str | None) -> str:
    ps = pmap(root, cfg)
    src = resolve(root, raw)
    if not src.is_file():
        raise GovError(f"Report file not found: {src}")
    text = src.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GovError("Agent report must be JSON; use the supplied schema") from exc
    required = ["status", "branch", "head", "tests", "result", "blockers"]
    missing = [k for k in required if k not in data]
    if missing:
        raise GovError("Missing report fields: " + ", ".join(missing))
    lim = cfg["limits"]
    data["result"] = data.get("result", [])[:int(lim["max_result_items"])]
    data["blockers"] = data.get("blockers", [])[:int(lim["max_blocker_items"])]
    cycle_id = cycle or os.environ.get("CURRENT_CYCLE", "current")
    outdir = ps["reports"] / cycle_id
    outdir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", f"{agent}-{task}").strip("-")
    stored = outdir / f"{stem}.json"
    data.update({"stored_at": now(), "source_file": rel(root, src)})
    write_json(stored, data)
    compact = compact_report(data, agent, task, int(lim["max_report_output_lines"]))
    (outdir / f"{stem}.md").write_text(compact + f"\nREPORT: {rel(root, stored)}\n", encoding="utf-8")
    add_ledger(ps, reports_ingested=1, report_input_lines=len(text.splitlines()))
    return compact + f"\nREPORT: {rel(root, stored)}"


def trunc(text: str, limit: int) -> str:
    lines = text.splitlines()
    return text if len(lines) <= limit else "\n".join(lines[:limit] + [f"... truncated {len(lines)-limit} lines"])


def snapshot(root: Path) -> dict[str, str]:
    return {
        "branch": git(root, "branch", "--show-current"),
        "head": git(root, "rev-parse", "--short=12", "HEAD"),
        "status": git(root, "status", "--short"),
        "last": git(root, "log", "-1", "--oneline"),
    }


def bootstrap(root: Path, cfg: dict[str, Any]) -> str:
    ps = pmap(root, cfg)
    snap = snapshot(root)
    state = ps["current_state"].read_text(encoding="utf-8", errors="replace")
    cycle = ps["current_cycle"].read_text(encoding="utf-8", errors="replace")
    decisions = ps["decisions"].read_text(encoding="utf-8", errors="replace")
    brief = "\n".join([
        "# Agent E Brief", "", "## Git",
        f"- branch: {snap['branch'] or 'detached'}", f"- head: {snap['head']}",
        f"- last: {snap['last']}", f"- dirty: {'yes' if snap['status'] else 'no'}",
        "", "## Current state", trunc(state, 28),
        "", "## Current cycle", trunc(cycle, 28),
        "", "## Durable decisions", trunc(decisions, 14),
    ])
    brief = trunc(brief, int(cfg["limits"]["max_bootstrap_lines"]))
    ps["brief"].write_text(brief.strip() + "\n", encoding="utf-8")
    led = read_json(ps["ledger"], {})
    led.update({"last_action": "bootstrap", "last_bootstrap_at": now()})
    write_json(ps["ledger"], led)
    return brief


def budget(cfg: dict[str, Any], led: dict[str, Any]) -> dict[str, Any]:
    lim = cfg["limits"]
    hard, soft = [], []
    metrics = [
        ("messages", "hard_messages", "soft_messages"),
        ("session_mb", "hard_session_mb", "soft_session_mb"),
        ("input_tokens", "hard_input_tokens", "soft_input_tokens"),
    ]
    for key, hk, sk in metrics:
        value = led.get(key)
        if value is None:
            continue
        if value >= lim[hk]: hard.append(f"{key}={value}")
        elif value >= lim[sk]: soft.append(f"{key}={value}")
    if hard:
        return {"status": "HARD_LIMIT", "action": "STOP_NEW_WORK; CYCLE_CLOSE; COMPACT_NOW; DO_NOT_ROTATE_UNSAFELY", "reasons": hard, "ledger": led}
    if soft:
        return {"status": "SOFT_LIMIT", "action": "FINISH_ATOMIC_STEP; UPDATE_STATE; COMPACT_CURRENT_SESSION", "reasons": soft, "ledger": led}
    return {"status": "HEALTHY", "action": "CONTINUE_WITH_GUARDS", "reasons": [], "ledger": led}


def close_cycle(root: Path, cfg: dict[str, Any]) -> str:
    ps = pmap(root, cfg)
    snap = snapshot(root)
    handoff = "\n".join([
        "# Session Handoff", "",
        f"- branch: {snap['branch'] or 'detached'}", f"- head: {snap['head']}",
        f"- dirty: {'yes' if snap['status'] else 'no'}", "",
        "## Current state", trunc(ps["current_state"].read_text(encoding="utf-8", errors="replace"), 45),
        "", "## Current cycle", trunc(ps["current_cycle"].read_text(encoding="utf-8", errors="replace"), 35),
        "", "## Resume",
        "1. Keep the same Team and member Sessions.",
        "2. Run init, bootstrap, and budget.",
        "3. Read only .agent/context/BRIEF.md by default.",
    ])
    handoff = trunc(handoff, 100)
    ps["handoff"].write_text(handoff.strip() + "\n", encoding="utf-8")
    return handoff


def main() -> int:
    ap = argparse.ArgumentParser(description="Agent E context governor")
    ap.add_argument("--repo", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("bootstrap")
    g = sub.add_parser("guard-read"); g.add_argument("path"); g.add_argument("--force", action="store_true"); g.add_argument("--json", action="store_true")
    e = sub.add_parser("excerpt"); e.add_argument("path"); e.add_argument("--query", required=True); e.add_argument("--context", type=int, default=3); e.add_argument("--max-lines", type=int)
    i = sub.add_parser("ingest-report"); i.add_argument("--file", required=True); i.add_argument("--agent", required=True); i.add_argument("--task-id", required=True); i.add_argument("--cycle")
    b = sub.add_parser("budget"); b.add_argument("--messages", type=int); b.add_argument("--session-mb", type=float); b.add_argument("--input-tokens", type=int); b.add_argument("--json", action="store_true")
    sub.add_parser("cycle-close")
    sub.add_parser("status")
    args = ap.parse_args()
    try:
        root = root_of(Path(args.repo).resolve())
        cfg = config(root)
        ps = init(root, cfg)
        if args.cmd == "init":
            print(f"INITIALIZED: {rel(root, ps['state'])}")
        elif args.cmd == "bootstrap":
            print(bootstrap(root, cfg))
        elif args.cmd == "guard-read":
            result = guard(root, cfg, args.path, args.force)
            if args.json: print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"{result['decision']}: {result['path']}")
                print(f"REASON: {result['reason']}")
                if result.get("owner"): print(f"OWNER: {result['owner']}")
        elif args.cmd == "excerpt":
            ml = args.max_lines or int(cfg["limits"]["max_excerpt_lines"])
            print(excerpt(root, cfg, args.path, args.query, args.context, ml))
        elif args.cmd == "ingest-report":
            print(ingest(root, cfg, args.file, args.agent, args.task_id, args.cycle))
        elif args.cmd == "budget":
            led = read_json(ps["ledger"], {})
            if args.messages is not None: led["messages"] = args.messages
            if args.session_mb is not None: led["session_mb"] = args.session_mb
            if args.input_tokens is not None: led["input_tokens"] = args.input_tokens
            led.update({"last_action": "budget", "updated_at": now()})
            write_json(ps["ledger"], led)
            result = budget(cfg, led)
            if args.json: print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"CONTEXT: {result['status']}")
                print(f"ACTION: {result['action']}")
                if result["reasons"]: print("REASONS: " + ", ".join(result["reasons"]))
                print(f"LOCAL_USAGE: full_reads={led.get('full_reads',0)}, full_read_mb={round((led.get('full_read_bytes',0) or 0)/1048576,3)}, excerpt_reads={led.get('excerpt_reads',0)}, reports={led.get('reports_ingested',0)}")
            return 2 if result["status"] == "HARD_LIMIT" else 1 if result["status"] == "SOFT_LIMIT" else 0
        elif args.cmd == "cycle-close":
            print(close_cycle(root, cfg))
        elif args.cmd == "status":
            snap, result = snapshot(root), budget(cfg, read_json(ps["ledger"], {}))
            print(f"BRANCH/HEAD: {snap['branch']} / {snap['head']}")
            print(f"DIRTY: {'yes' if snap['status'] else 'no'}")
            print(f"CONTEXT: {result['status']}")
            print(f"BRIEF: {rel(root, ps['brief'])}")
        return 0
    except GovError as exc:
        print(f"context-governor: {exc}", file=sys.stderr); return 3
    except Exception as exc:
        print(f"context-governor unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr); return 3


if __name__ == "__main__":
    raise SystemExit(main())
