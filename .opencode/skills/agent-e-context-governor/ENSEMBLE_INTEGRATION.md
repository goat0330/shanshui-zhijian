# Integration with ensemble-efficiency

Use both Skills in this order.

At the start of every work package, run the combined context preflight with an
explicit repository root. For routing-only fixtures use `--base HEAD`; for a
real work package use the fixed integration commit. Never let the tool infer a
base from a dirty workspace with untracked files.

```text
python -X utf8 .opencode/skills/agent-e-context-governor/scripts/context_governor.py --repo <absolute-repo-root> preflight --json
python C:/Users/WangChi/.agents/skills/ensemble-efficiency/scripts/ensemble_efficiency.py --repo <absolute-repo-root> --base <fixed-base> --owner <owner> --task-id <id> --json
```

## Before Agent E reads or reviews

```text
context-governor guard-read
→ ensemble-efficiency
→ read only escalated files
```

## Child Agent completion

```text
child Agent writes agent_report.json
→ context-governor ingest-report
→ ensemble-efficiency runs affected checks
→ Agent E receives compact report + deterministic decision
```

Append this to every A/B/C/D work package:

```text
Do not send full logs, full diff, or implementation narrative to Agent E.
Write a JSON report using:
.opencode/skills/agent-e-context-governor/templates/agent_report.schema.json

Then run:
python .opencode/skills/agent-e-context-governor/scripts/context_governor.py ingest-report --agent <agent> --task-id <id> --file <report.json>

Send Agent E only the compact command output and stored report path.
Before requesting review, run ensemble-efficiency.
```

Independent work packages are dispatched in parallel. Dependency order controls merge order, not dispatch order.
