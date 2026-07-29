---
name: agent-e-context-governor
description: Keep Agent E's context small with preflight, guarded reads, compact reports, and bounded cycle handoffs.
license: MIT
compatibility: opencode
---

# Agent E Context Governor

This is the short execution contract. Full rationale is in
`docs/agent-control/CONTEXT_GOVERNOR_FULL_REFERENCE_2026-07-29.md`.

## Start / resume

From the repository root, always use the absolute repo path and UTF-8 Python:

```text
python -X utf8 .opencode/skills/agent-e-context-governor/scripts/context_governor.py --repo <absolute-repo-root> preflight --json
```

Interpretation:

- `HEALTHY`: dispatch is allowed.
- `SOFT_LIMIT`: finish only the current atomic step; do not dispatch another package.
- `HARD_LIMIT`: stop dispatch, preserve Team, and use the generated handoff.

`preflight` refreshes the Brief, evaluates messages/session MB/input tokens, and
generates `SESSION_HANDOFF.md` at SOFT/HARD. It does not invoke native OpenCode
compaction; the runtime remains responsible for that operation.

## Read guard

Before reading a project file:

```text
python -X utf8 .opencode/skills/agent-e-context-governor/scripts/context_governor.py --repo <absolute-repo-root> guard-read <relative-path> --json
```

- `SKIP_UNCHANGED`: do not reread.
- `ALLOW_EXCERPT`: use `excerpt`.
- `DELEGATE_OWNER`: ask the domain Agent for a compact finding.
- `ALLOW_FULL`: read once, then rely on the registry.
- `DENY_LARGE`: do not paste into chat.

Default startup view is only `.agent/context/BRIEF.md` and the current Cycle.

## Child reports

The Agent writes full logs to `.agent/artifacts/` and a JSON report using
`templates/agent_report.schema.json`. Then run:

```text
python -X utf8 .opencode/skills/agent-e-context-governor/scripts/context_governor.py ingest-report --agent <agent> --task-id <id> --file <report.json>
```

Send E only the compact output and artifact path. Keep the chat-facing summary
under 12 lines.

## Cycle close

At the end of a Cycle:

```text
python -X utf8 .opencode/skills/agent-e-context-governor/scripts/context_governor.py --repo <absolute-repo-root> cycle-close
```

Do not load old transcripts or future Cycle documents automatically.
