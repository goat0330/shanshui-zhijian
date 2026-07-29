---
name: agent-e-context-governor
description: Keep Agent E as a thin control plane by preventing repeated full-file reads, redirecting large outputs to files, enforcing compact child-agent reports, maintaining a deterministic current-state brief, monitoring context budgets, and triggering native compaction before the OpenChamber session becomes expensive. Use whenever Agent E starts or resumes work, reads project files, receives child-agent results, prepares another work package, or observes growing input-token and cache-miss costs.
license: MIT
compatibility: opencode
metadata:
  workflow: ensemble
  priority: context-efficiency
---

# Agent E Context Governor

This skill prevents Agent E from becoming the project's full-history container.

It complements `ensemble-efficiency`:

- `agent-e-context-governor`: controls what Agent E reads and retains.
- `ensemble-efficiency`: controls ownership, affected checks, review routing, and compact handoff.

## Durable model

Keep these durable:

- Team identity and roles
- Worktrees and branches
- Git state
- Structured current state and decisions

Do not keep these indefinitely in Agent E chat:

- complete child-session history
- full successful logs
- full PR patches
- unchanged governance files
- previous-cycle plans
- repeated repository summaries

Agent E is a thin control plane, not a repository reader, CI-log processor, or memory database.

## Mandatory command order

At Agent E start or resume:

```bash
python .opencode/skills/agent-e-context-governor/scripts/context_governor.py init
python .opencode/skills/agent-e-context-governor/scripts/context_governor.py bootstrap
python .opencode/skills/agent-e-context-governor/scripts/context_governor.py budget
```

Use the combined preflight command before dispatching a new work package. On
Windows, pass the absolute repository root and force UTF-8 so CJK paths are
not lost between the shell and Python:

```bash
python -X utf8 .opencode/skills/agent-e-context-governor/scripts/context_governor.py --repo <absolute-repo-root> preflight --messages <n> --session-mb <n> --input-tokens <n> --json
```

`SOFT_LIMIT` finishes only the current atomic step and writes a bounded
handoff. `HARD_LIMIT` stops new work-package dispatch. This command generates
the handoff but does not pretend to invoke OpenCode native compaction.

Before reading a project file:

```bash
python .opencode/skills/agent-e-context-governor/scripts/context_governor.py guard-read <path>
```

Obey the result:

- `SKIP_UNCHANGED`: do not reread.
- `ALLOW_EXCERPT`: use `excerpt`, not a full read.
- `ALLOW_FULL`: full read is allowed once for this content hash.
- `DELEGATE_OWNER`: ask the domain owner for a compact finding.
- `DENY_LARGE`: do not paste the file into chat.

For precise lookup:

```bash
python .opencode/skills/agent-e-context-governor/scripts/context_governor.py excerpt <path> --query "<symbol-or-error>"
```

When a child Agent completes:

```bash
python .opencode/skills/agent-e-context-governor/scripts/context_governor.py ingest-report \
  --agent agent-a --task-id C31-A --file <agent-report.json>
```

Agent E receives only the compact output. Full evidence remains under `.agent/reports/` and `.agent/artifacts/`.

Before another work package or after a large tool result:

```bash
python .opencode/skills/agent-e-context-governor/scripts/context_governor.py budget
```

At Cycle completion:

```bash
python .opencode/skills/agent-e-context-governor/scripts/context_governor.py cycle-close
```

## Reading policy

Read once per content hash:

- `AGENTS.md`
- `agents/sessions.yml`
- stable SOPs
- Skill documentation
- architecture decisions

Load only the current Cycle. Never load all future Cycle files at startup.

Default discovery order:

1. `git status --short`
2. `git log -1 --oneline`
3. `git diff --stat`
4. `git diff --name-only`
5. compact Agent report
6. targeted `rg` or `excerpt`
7. a specific changed file only when required

Do not default to full `git diff`, recursive repository reads, full CI logs, complete child-agent conversations, full PR patches, all handoffs, or all future Cycle Markdown.

## Child-agent reporting contract

Child Agents return JSON matching `templates/agent_report.schema.json`.

Maximum chat-facing content:

- 12 compact output lines
- 5 result bullets
- 3 blocker bullets
- no successful logs
- no full diff
- no chain-of-thought
- no repeated work-package text

## Context budget

Defaults:

- soft: 80 messages, 15 MB session data, or 2,000,000 cumulative input tokens
- hard: 120 messages, 25 MB session data, or 3,500,000 cumulative input tokens
- full file: 200 KB maximum
- excerpt: 100 lines maximum
- compact child report: 12 lines maximum

At `SOFT_LIMIT`:

1. finish the current atomic operation;
2. stop accepting long reports;
3. update `CURRENT_STATE.md`;
4. compact the current Agent E Session;
5. resume from `bootstrap`.

At `HARD_LIMIT`:

1. stop assigning new work;
2. run `cycle-close`;
3. compact immediately;
4. do not rotate Agent E unless a safe lead-transfer API exists;
5. if compaction is unavailable, freeze and request operator action.

Because current Ensemble takeover requires database edits, Session rotation is not the default recovery method.

## Prompt-cache policy

- keep Skill and system rules stable;
- keep section order deterministic;
- overwrite `CURRENT_STATE.md` instead of appending history;
- put dynamic Git and Cycle data after stable rules;
- avoid timestamps unless state changed;
- use hashes and changed paths rather than full content.

This reduces avoidable cache misses but cannot guarantee provider-side cache hits.

## Integration with Ensemble Efficiency

Before Agent E reads a PR or asks for general review:

```bash
python .opencode/skills/ensemble-efficiency/scripts/ensemble_efficiency.py \
  --owner <agent> --task-id <task-id>
```

Then:

- `PASS`: Agent E does not reread code.
- `RETURN_TO_OWNER`: send only failed excerpts to the same owner.
- `ESCALATE_E`: Agent E reads only flagged files after `guard-read`.
- `NO_CHANGES`: no report or review cycle.

Dispatch independent work packages in parallel. Dependency order controls merge order, not dispatch order.

## State files

The script creates:

```text
.agent/context/CURRENT_STATE.md
.agent/context/CURRENT_CYCLE.md
.agent/context/DECISIONS.md
.agent/context/BRIEF.md
.agent/context/read_registry.json
.agent/context/ledger.json
.agent/context/SESSION_HANDOFF.md
.agent/reports/
.agent/artifacts/
```

## Limits

This Skill does not:

- alter DeepSeek/OpenCode provider cache behavior;
- erase history already stored by OpenChamber;
- safely transfer Ensemble lead ownership;
- modify `ensemble.db`;
- guarantee native compaction is available.

It prevents recurrence and makes compaction cheap and reliable. Runtime-level lead transfer remains a separate plugin concern.
