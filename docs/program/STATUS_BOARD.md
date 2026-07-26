# 山水智鉴 — Agent 状态面板

> 更新：2026-07-26（v0.1.0 发布后）
>
> 正式发布：`v0.1.0` @ `f950850`（已推送 tag）
>
> develop：`f950850`（integration 已快进合并）
>
> main：PR #14 待合并（受保护分支，需通过 PR）

## 当前状态

| Agent | Work Package | 最终 Clean Branch | 最终 Head | 最终 Gate | 状态 |
|---|---|---|---|---|---|
| **B** 工程可靠性_AGENT_B | G0.3-B + Workbench CI | `feature/agent-b-reliability-repair` | `f0cfdaf` | CI passed | ✅ 已合入 integration |
| **A** 感知算法_AGENT_A | G0.3-A Candidate v0.3 | `feature/agent-a-integration-regression` | `eaa9849` | CI passed | ✅ 已合入 integration |
| **C** 事件治理_AGENT_C | G1.1-C Event Integrity | `feature/agent-c-event-clean` | `8a37ef7` | CI passed | ✅ 已合入 integration |
| **D** 产品工作台_AGENT_D | D0-D9 Workbench V0 | `feature/agent-d-workbench-clean` | `9ebc893` | CI passed | ✅ 已合入 integration |
| **E** 项目经理_AGENT_E | MULTISESSION-02 | `feature/agent-e-dynamic-session-policy` | `576c248` | CI passed | ✅ 已合入 integration |

## 已核验事实

- 五 Agent 按 B → A → C → D → E 顺序全部合入 `integration/g0-g1-contract-freeze`。
- 远程 CI 全部通过：Python 369 passed + 2 skipped，Vitest 43/43，Playwright 24/24，前端 Build 通过。
- 用户批准后，integration 已快进合并至 develop（f950850）。
- main 受保护，PR #14 已创建等待合并。
- `v0.1.0` 标签已推送。
- 原共享目录保持不变，recovery branch 与 bundle 仍保留。

## 当前阻断

1. **main 保护**：develop → main 需通过 PR #14 合并。
2. **PROJ 本地环境冲突**：本地 `venv` 中 rasterio 与 PostGIS PROJ 版本不匹配，不影响 CI。
3. Ensemble 试验待 v0.1.0 发布稳定后进行。

## 下一 Gate

1. 合并 PR #14（develop → main）。
2. 启动 Ensemble 隔离试验（新 OpenCode 环境 + `opencode-ensemble@0.15.2`）。
3. 开始 V0.2 开发任务分配。

## 已归档分支

旧 `agent-a-*`、`agent-b-*`、`agent-c-*` 混合分支、旧 D clone 以及旧
`feature/agent-e-integration-control` 保留为历史来源，不再继续开发。
具体恢复过程见 `MULTI_SESSION_OPERATIONS.md`。
