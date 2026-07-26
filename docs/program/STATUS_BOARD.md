# 山水智鉴 — Agent 状态面板

> 更新：2026-07-26
>
> 正式 integration：`integration/g0-g1-contract-freeze` @ `f950850`
>
> 候选集成视图：`feature/agent-e-integration-control`

## 当前状态

| Agent | Work Package | Clean Branch | Head | 已验证 Gate | 状态 |
|---|---|---|---|---|---|
| 工程可靠性_AGENT_B | G0.3-B + Workbench CI | `feature/agent-b-reliability-repair` | `f0cfdaf` | 已纳入 integration；需以当前 CI 重跑为准 | `integrated` |
| 感知算法_AGENT_A | G0.3-A Candidate v0.3 | `feature/agent-a-integration-regression` | `eaa9849` | 已纳入 integration；需以当前 CI 重跑为准 | `integrated` |
| 事件治理_AGENT_C | G1.1-C Event Integrity | `feature/agent-c-event-clean` | `8a37ef7` | 已纳入 integration；包含上游合同依赖 | `integrated` |
| 产品工作台_AGENT_D | D0-D9 Workbench V0 | `feature/agent-d-workbench-clean` | `9ebc893` | 已纳入 integration；前端验收记录待刷新 | `integrated` |
| 项目经理_AGENT_E | MULTISESSION-02 / Ensemble primary | `feature/agent-e-dynamic-session-policy` | `1690b71` | 治理、Session 策略、发布状态；OMO 已从活动配置移除 | `active` |

## 已核验事实

- 原五个 OpenCode/GeoCode Session 曾共用一个 working tree，产生 HEAD 与
  分支名错位；根因已由 reflog 和工作区状态确认。
- 原共享目录保持不变，并建立 recovery branch 与经过 `git bundle verify`
  的恢复包。
- A/B/C/D/E 现在各有独立 worktree；A/B/C/D/E 的治理提交已进入
  `integration/g0-g1-contract-freeze` @ `f950850`。
- C 和 D 的 clean branch 为便于端到端验证，本地包含上游依赖合并；正式
  集成仍必须按 B → A → C → D 顺序执行。

## 当前阻断

1. `integration → develop` 与 `develop → main` 的正式发布动作仍需用户批准。
2. Ensemble 不能自动接管旧 sibling Session；长期岗位需使用固定 Session/Worktree。
3. OMO 与 Ensemble 的运行时共存已发现 Agent 映射冲突，当前采用 Ensemble-only。
4. 外部 CARTO 底图在受限网络下可能不可达，但 Mock 工作台核心 E2E 不受影响。

## 下一 Gate

1. 用户批准后运行统一 Python、前端单测、Build 和 Playwright 回归。
2. 在 Ensemble-only 正式配置中验证 Agent 映射与 `team_message` 唤醒。
3. 建立可复用 Team Dashboard 或等价 Session 管理入口。

## 不再作为当前状态源的旧分支

旧 `agent-a-*`、`agent-b-*`、`agent-c-*` 混合分支和旧 D clone 只保留为
历史来源，不再继续开发，也不得直接合入 integration。具体恢复过程见
`MULTI_SESSION_OPERATIONS.md`。
