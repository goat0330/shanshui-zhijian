# 五个顶层 Session 协同 SOP

## 目标

建立五个可以独立对话、彼此隔离、长期复用的 GeoCode Session：

```text
用户
└── 项目经理_AGENT_E
    ├── 感知算法_AGENT_A
    ├── 工程可靠性_AGENT_B
    ├── 事件治理_AGENT_C
    └── 产品工作台_AGENT_D
```

A/B/C/D/E 都是 GeoCode 中手动创建的**普通顶层 Session**，不是
Ensemble child session。Ensemble 只用于临时并行任务。

## 每个 Session 的固定绑定

| Agent | Worktree | Branch 规则 | 默认模型 |
|---|---|---|---|
| A 感知算法 | `agent-a` | `feature/agent-a-*` | `deepseek/deepseek-v4-flash` |
| B 工程可靠性 | `agent-b` | `feature/agent-b-*` | `deepseek/deepseek-v4-flash` |
| C 事件治理 | `agent-c` | `feature/agent-c-*` | `deepseek/deepseek-v4-flash` |
| D 产品工作台 | `agent-d` | `feature/agent-d-*` | `deepseek/deepseek-v4-flash` |
| E 项目经理 | `agent-e` | `feature/agent-e-*` | `deepseek/deepseek-v4-flash` |

模型必须在 Session 或 `team_spawn(model=...)` 中显式指定，不依赖平台默认模型。

## 启动步骤

1. 从最新 `integration/g0-g1-contract-freeze` 创建或核对五个 worktree。
2. 在每个 worktree 中打开一个普通顶层 GeoCode Session。
3. 粘贴 `agents/SESSION_START_PROMPT.md`，替换角色、目录和分支。
4. 执行四项启动检查：

   ```powershell
   git status --short --branch
   git branch --show-current
   git rev-parse --show-toplevel
   git log -1 --oneline
   ```

5. 将 Session 名称、目录、分支和模型登记到 `agents/sessions.yml`。

## 派单与交接

Agent E 只通过以下内容管理 A/B/C/D：

```text
agents/inbox/<agent>.md
agents/handoff/<agent>_to_E.md
docs/program/STATUS_BOARD.md
Git Commit / PR / CI
```

每次只派发一个 Work Package、一个 Gate 和一个停止条件。执行 Agent 只能在
自己的 feature branch 工作，完成后按 `agents/HANDOFF_TEMPLATE.md` 交接。

## 合并流程

```text
A/B/C/D feature branch
→ Agent E 审查
→ integration（一次一个 Agent）
→ 统一 CI/E2E
→ 用户批准
→ develop
→ 用户批准
→ main
```

Agent E 只能提出 `MERGE_READY`，没有用户批准不得合并 develop/main。

## 动态启停与职责复用

不需要每轮启用 A/B/C/D 全部 Session。E 在 `agents/sessions.yml` 中设置
`enabled` 和当前 Work Package 即可。Agent ID 保持稳定，职责可以变化；例如
A 后续可以承担计算机视觉，但必须重新签发输入、输出、允许目录和验收 Gate。

## Ensemble 边界

Ensemble child session 不作为长期岗位，也不要求用户直接输入。它只用于：

- 临时只读审计；
- 一次性探索；
- 短周期编码任务；
- 独立 Review。

每次 `team_spawn` 必须显式提供 `model`，并优先使用当前真实存在的
`plan`、`explore` 或 `build` agent key。

## 完成标准

- 五个 Session 都能独立对话；
- 五个目录和分支互不相同；
- 模型记录明确；
- E 能通过任务板派单和收取交接；
- 任意一个 Agent 可暂时停用而不破坏其他 Session；
- Git diff、CI 和合并顺序可追踪。

## 回滚

本 SOP 不修改 GeoCode 客户端。若某个 Session 异常，只需关闭该 Session，
保留 worktree 和 branch；不得删除旧工作区、recovery branch 或 bundle。
