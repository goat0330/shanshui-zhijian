# Agent E Context Governor

A lightweight OpenCode/OpenChamber Skill that keeps a multi-agent lead Session small.

## It fixes

- repeated reading of unchanged files;
- child Agents dumping logs and diffs into Agent E;
- Agent E reading every CI failure itself;
- loading every future Cycle at startup;
- session growth without budget alarms;
- expensive compaction without structured recovery state;
- cache misses caused by constantly changing prompt prefixes.

## Design

```text
stable Skill rules
        +
.agent/context/BRIEF.md
        +
current compact result
        ↓
Agent E
```

Full details stay in Git, reports, logs, or CI artifacts.

## Install project-local

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -ProjectRoot "D:\path\to\repo"
```

## Install globally

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Global
```

After project-local installation:

```powershell
python .opencode\skills\agent-e-context-governor\scripts\context_governor.py init
python .opencode\skills\agent-e-context-governor\scripts\context_governor.py bootstrap
```

## Native compaction

The script returns `SOFT_LIMIT` or `HARD_LIMIT`; it does not guess the OpenChamber compaction command. Configure that command only after it is verified in the current environment.

## Recommended policy

1. Keep the current Agent E Session.
2. Force child reports through `ingest-report`.
3. Run `guard-read` before every full project-file read.
4. Compact in place at the soft threshold.
5. Rotate Agent E only after Ensemble has a safe lead-transfer API.
