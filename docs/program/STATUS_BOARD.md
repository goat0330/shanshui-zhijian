# 山水智鉴 — Agent 状态面板

> 更新：2026-07-26 (Phase 2 — 顶层 Session 启动就绪)
>
> 正式 integration：`integration/g0-g1-contract-freeze` @ `eb2f1a0`
>
> SOP 分支：`feature/codex-top-level-session-sop` @ `ea57f07`

## 当前状态

| Agent | Work Package | Worktree Branch | Head | 状态 |
|---|---|---|---|---|
| 感知算法_AGENT_A | — (待派单) | `feature/agent-a-top-level-session` | `eb2f1a0` | `ready` |
| 工程可靠性_AGENT_B | — (待派单) | `feature/agent-b-top-level-session` | `eb2f1a0` | `ready` |
| 事件治理_AGENT_C | — (待派单) | `feature/agent-c-top-level-session` | `eb2f1a0` | `ready` |
| 产品工作台_AGENT_D | — (待派单) | `feature/agent-d-top-level-session` | `eb2f1a0` | `ready` |
| 项目经理_AGENT_E | 顶层 Session 编排 | `feature/agent-e-dynamic-session-policy` | `1690b71` | `active` |

## 集成记录（Phase 1 — 已关闭）

以下 Gate 已在 Phase 1 完成并入 `integration/g0-g1-contract-freeze`：

| Agent | 历史分支 | 集成状态 |
|---|---|---|
| 工程可靠性_AGENT_B | `feature/agent-b-reliability-repair` @ `f0cfdaf` | `integrated` |
| 感知算法_AGENT_A | `feature/agent-a-integration-regression` @ `eaa9849` | `integrated` |
| 事件治理_AGENT_C | `feature/agent-c-event-clean` @ `8a37ef7` | `integrated` |
| 产品工作台_AGENT_D | `feature/agent-d-workbench-clean` @ `9ebc893` | `integrated` |
| 项目经理_AGENT_E | `feature/agent-e-dynamic-session-policy` @ `1690b71` | `active` |

## 顶层 Session 启动就绪清单

- [x] A/B/C/D/E 五个独立 worktree 已存在
- [x] A/B/C/D 从 `integration/g0-g1-contract-freeze` 创建新分支
- [x] E 保持在 `feature/agent-e-dynamic-session-policy`
- [x] 所有 worktree 工作区干净，无未提交改动
- [x] `agents/sessions.yml` v3 — 全启用 + current_branch + baseline 记录
- [x] `agents/inbox/` — 五个 inbox 文件已创建
- [x] `agents/start-prompts/` — 五个预填充启动提示词已创建
- [x] `docs/program/TOP_LEVEL_SESSION_SOP.md` 已生效

## 启动步骤（接下来）

1. 在 GeoCode 中分别打开五个 worktree 目录各创建一个顶层 Session
2. 使用 `agents/start-prompts/SESSION_START_AGENT_*.md` 初始化身份
3. 执行四项启动检查（git status / branch / rev-parse / log）
4. E 派发第一个 Work Package，A/B/C/D 开始接收

## 已知基线事实

- 原五个 Session 曾共用一个 working tree（已修复）
- 旧 worktree `D:\研究生作业\人工智能实践比赛\8.1开始_山水智鉴比赛` 保留为历史参考
- 旧分支（`agent-a-g0.3-candidate-final` 等）保留在 reflog 和 recovery bundle 中
