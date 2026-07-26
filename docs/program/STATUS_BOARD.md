# 山水智鉴 — Agent 状态面板

> 更新：2026-07-26
>
> 正式 integration：`integration/g0-g1-contract-freeze` @ `df7b3e7`（未改动）
>
> 候选集成视图：`feature/agent-e-integration-control`

## 当前状态

| Agent | Work Package | Clean Branch | Head | 已验证 Gate | 状态 |
|---|---|---|---|---|---|
| 工程可靠性_AGENT_B | G0.3-B + Workbench CI | `feature/agent-b-reliability-repair` | `e8bb744` | Python 183 passed, 1 skipped；Ruff correctness；前端 CI 已定义 | `MERGE_READY` |
| 感知算法_AGENT_A | G0.3-A Candidate v0.3 | `feature/agent-a-candidate-clean` | `a2a3c41` | 合同与快速验证 44 passed；多时相代表性 E2E passed | `MERGE_READY` |
| 事件治理_AGENT_C | G1.1-C Event Integrity | `feature/agent-c-event-clean` | `6ca477d` | C 域 72 passed；候选集成 Python 294 passed, 1 skipped | `MERGE_READY` |
| 产品工作台_AGENT_D | D0-D9 Workbench V0 | `feature/agent-d-workbench-clean` | `d58078d` | Vitest 43/43；Build；Playwright 24/24 | `MERGE_READY` |
| 项目经理_AGENT_E | MULTISESSION-01 | `feature/agent-e-integration-control` | 当前提交 | 治理、候选集成、隔离控制面 | 进行中 |

## 已核验事实

- 原五个 OpenCode/GeoCode Session 曾共用一个 working tree，产生 HEAD 与
  分支名错位；根因已由 reflog 和工作区状态确认。
- 原共享目录保持不变，并建立 recovery branch 与经过 `git bundle verify`
  的恢复包。
- A/B/C/D/E 现在各有独立 worktree；正式 integration 尚未合入任何 clean
  branch。
- C 和 D 的 clean branch 为便于端到端验证，本地包含上游依赖合并；正式
  集成仍必须按 B → A → C → D 顺序执行。

## 当前阻断

1. GitHub 远程尚未接收本轮 clean branches。
2. 正式 integration 合并等待用户批准。
3. Ensemble 只能用于新建的隔离团队，不能自动接管五个旧 sibling Session。
4. 外部 CARTO 底图在受限网络下可能不可达，但 Mock 工作台核心 E2E 不受影响。

## 下一 Gate

1. 完成 E 的治理提交和隔离 OpenCode 控制面试运行。
2. 推送五条 feature branch。
3. 用户审查本报告并决定是否授权 B → A → C → D 逐项合入 integration。
4. 每次正式合入后重新运行 Python、前端单测、Build 和 Playwright。

## 不再作为当前状态源的旧分支

旧 `agent-a-*`、`agent-b-*`、`agent-c-*` 混合分支和旧 D clone 只保留为
历史来源，不再继续开发，也不得直接合入 integration。具体恢复过程见
`MULTI_SESSION_OPERATIONS.md`。
