# 五个顶层 Session 协同 SOP

> **版本**: v2
> **修正**: GeoCode 项目上下文 ≠ Git worktree。同一项目上下文中的多个 Session
> 共享同一工作目录，无法实现 worktree 隔离。

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

## 核心架构规则（重要）

**五个顶层 Session = 五个独立 GeoCode 项目上下文 + 五个 Git worktree + 五个长期分支**

```
GeoCode 项目上下文 A  →  worktree agent-a  →  feature/agent-a-*
GeoCode 项目上下文 B  →  worktree agent-b  →  feature/agent-b-*
GeoCode 项目上下文 C  →  worktree agent-c  →  feature/agent-c-*
GeoCode 项目上下文 D  →  worktree agent-d  →  feature/agent-d-*
GeoCode 项目上下文 E  →  worktree agent-e  →  feature/agent-e-*
```

**关键约束**: 同一 GeoCode 项目上下文下的多个普通顶层 Session 共享同一
工作目录、Git 工作区和分支上下文，无法实现 worktree 隔离。因此每个 Agent
必须使用**独立的 CLI 窗口或 GeoCode 窗口**，各自打开一个 worktree。

## 每个 Session 的固定绑定

| Agent | Worktree | Project 上下文 | 工作目录 | Branch 规则 | 默认模型 |
|---|---|---|---|---|---|
| A 感知算法 | `agent-a` | 独立窗口 A | `D:\...\agent-a` | `feature/agent-a-*` | `deepseek/deepseek-v4-flash` |
| B 工程可靠性 | `agent-b` | 独立窗口 B | `D:\...\agent-b` | `feature/agent-b-*` | `deepseek/deepseek-v4-flash` |
| C 事件治理 | `agent-c` | 独立窗口 C | `D:\...\agent-c` | `feature/agent-c-*` | `deepseek/deepseek-v4-flash` |
| D 产品工作台 | `agent-d` | 独立窗口 D | `D:\...\agent-d` | `feature/agent-d-*` | `deepseek/deepseek-v4-flash` |
| E 项目经理 | `agent-e` | 独立窗口 E | `D:\...\agent-e` | `feature/agent-e-*` | `deepseek/deepseek-v4-flash` |

> `D:\...\` 指 `D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\`
>
> 模型必须在 Session 或 `team_spawn(model=...)` 中显式指定，不依赖平台默认模型。

## 启动步骤

1. **核对 worktree**: 从最新 `integration/g0-g1-contract-freeze` 创建或核对
   五个 worktree（用 `New-AgentTopLevelWorktrees.ps1` 或手工创建）。
2. **打开五个独立窗口**: 每个窗口以 CLI 或 GeoCode IDE 打开一个 worktree 目录：

   ```powershell
   # 窗口 A
   cd D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\agent-a
   opencode

   # 窗口 B
   cd D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\agent-b
   opencode

   # 以此类推 C/D/E……
   ```

3. **初始化身份**: 每个窗口粘贴对应的启动提示词（见
   `agents/start-prompts/SESSION_START_AGENT_*.md`，已预填角色/目录/分支）。
4. **执行四项启动检查**：

   ```powershell
   git status --short --branch
   git branch --show-current
   git rev-parse --show-toplevel
   git log -1 --oneline
   ```

   确认 `rev-parse` 返回的顶层目录与当前 worktree 匹配，分支名合规。
5. 将 Session 名称、目录、分支和模型登记到 `codex-top-level-session` 项目下的
   `agents/sessions.yml`（由 E 负责维护）。

## 禁止事项

- ❌ 在同一 GeoCode 项目上下文中创建多个普通 Session 冒充五个 Agent
- ❌ 多个 Session 轮流 `git switch` 到不同 Agent 分支（工作区污染）
- ❌ 一个 GeoCode 窗口同时打开 A/B/C/D/E 的目录
- ❌ 修改 `integration/g0-g1-contract-freeze`、`develop` 或 `main`

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
