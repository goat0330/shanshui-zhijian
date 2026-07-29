# 山水智鉴 Agent 启动规则

本文件是 OpenCode/Agent E 的启动层，只保留必须执行的规则。完整治理说明见
[`docs/agent-control/AGENTS_FULL_REFERENCE_2026-07-29.md`](docs/agent-control/AGENTS_FULL_REFERENCE_2026-07-29.md)。

## 1. 控制面边界

- E 负责任务拆分、状态、门禁和集成；A/B/C/D 负责各自 Work Package。
- Team、Actor、Task、Branch、Worktree 是持久状态；聊天 Session 是可替换执行 Epoch。
- 不手动编辑 `ensemble.db`，不手动修改 `lead_session_id` 或 `reported_to_lead`。
- 不在 E 中粘贴完整日志、完整 Diff、完整 Agent 历史；大输出写入 `.agent/artifacts/`。

## 2. 启动顺序

在派发任何工作包前，从仓库根目录运行：

```text
python -X utf8 .opencode/skills/agent-e-context-governor/scripts/context_governor.py --repo <absolute-repo-root> preflight --json
```

- `HEALTHY`：允许派发。
- `SOFT_LIMIT`：只完成当前原子步骤，不派发下一个工作包。
- `HARD_LIMIT`：停止派发，保留 Team，执行 handoff/compact。

只读取 `.agent/context/BRIEF.md` 和当前 Cycle；稳定文件先 `guard-read`，未变化不得重读。

## 3. 工作包分发

每个工作包必须包含：目标、Owner、允许目录、禁止目录、输入/输出、Gate、停止条件和交付格式。

- A：`ml/**`、感知与 Candidate。
- B：`competition/**`、CI、Manifest、可复现工程。
- C：`core/event_governance/**`、Evidence、Review、Event、Replay。
- D：`frontend/**`、Workbench API、Dashboard。
- E：`.agent/**`、`.opencode/**`、控制面和跨域集成。

独立工作包并行派发；合并顺序由依赖关系决定，不得因 B 未完成而延迟 A/C/D。

## 4. Git 与 Ensemble 门禁

测试必须显式指定比较基线：

- fixture/routing-only：`--base HEAD`；
- 正式工作包：固定 integration commit；
- 禁止让工具猜测 base；
- frozen config 在当前 Cycle 内不得修改。

Agent 完成后按顺序执行：

```text
agent_report.json
→ context-governor ingest-report
→ ensemble-efficiency --base <fixed-base> --json
```

- `PASS`：结束，不重复通用审查。
- `RETURN_TO_OWNER`：只把失败摘要返回原 Owner。
- `ESCALATE_E`：E 只读取升级涉及的文件。

## 5. 报告与 Cycle 关闭

Agent 发给 E 的摘要不超过 12 行；完整日志只返回路径。

Cycle 关闭时：

1. 合并完整工作包并运行 Cycle Gate；
2. 更新 `CURRENT_STATE.md`、`CURRENT_CYCLE.md`、`DECISIONS.md`；
3. 运行 `cycle-close` 生成不超过 150 行的 handoff；
4. 不追加过程日志，不提前读取下一 Cycle；
5. `integration→develop` 和 `develop→main` 必须等待用户批准。

## 6. 事实源

- 当前状态：`.agent/context/CURRENT_STATE.md`
- 当前 Cycle：`.agent/context/CURRENT_CYCLE.md`
- 决策：`.agent/context/DECISIONS.md`
- 交接：`.agent/context/SESSION_HANDOFF.md`
- 路由：`.opencode/ensemble-efficiency.json`
- 详细架构和历史规则：`docs/agent-control/`、`docs/program/`、`docs/07_实施管理/`
