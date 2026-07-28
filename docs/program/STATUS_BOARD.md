# 山水智鉴 — Agent 状态面板

> 更新：2026-07-28
>
> 正式 integration：`integration/g0-g1-contract-freeze` @ `9a1e910`（未改动）
>
> OpenChamber Ensemble 团队：`shanshui-zhijian-openchamber`（持久化 `persistent=true`）

## 历史 Clean Branch（GeoCode 阶段）

| Agent | Work Package | Clean Branch | Head | 已验证 Gate | 状态 |
|---|---|---|---|---|---|
| 工程可靠性_AGENT_B | G0.3-B + Workbench CI | `feature/agent-b-reliability-repair` | `e8bb744` | Python 183 passed, 1 skipped；Ruff correctness；远程 CI passed | `MERGE_READY` |
| 感知算法_AGENT_A | G0.3-A Candidate v0.3 | `feature/agent-a-candidate-clean` | `bc81e45` | 依赖对齐后 108 passed；远程 CI passed | `MERGE_READY` |
| 事件治理_AGENT_C | G1.1-C Event Integrity | `feature/agent-c-event-clean` | `91e7b9c` | C 域 72 passed；依赖对齐后 141 passed；远程 CI passed | `MERGE_READY` |
| 产品工作台_AGENT_D | D0-D9 Workbench V0 | `feature/agent-d-workbench-clean` | `d48204c` | Vitest 43/43；Build；Playwright 24/24；远程 Python CI passed | `MERGE_READY` |
| 项目经理_AGENT_E | MULTISESSION-01 | `feature/agent-e-integration-control` | `9a1e910` | 治理、候选集成、隔离 OpenCode 控制面；远程 CI passed | `MERGE_READY` |

## OpenChamber Ensemble 团队（2026-07-28 重建）

| Agent | OpenChamber ID | Worktree Path | Branch | HEAD | 职责 |
|---|---|---|---|---|---|
| 感知算法_AGENT_A | `perception-agent-a` | `C:\Users\WangChi\.local\share\opencode\worktree\a000c91ad0a8e7738f536ede25fad1c661f98fe8\ensemble-geocode-ensemble-mvp-test-shanshui-zhijian-openchamber-6x5sey-perception-agent-a` | `opencode/ensemble-geocode-ensemble-mvp-test-shanshui-zhijian-openchamber-6x5sey-perception-agent-a` | `06214d61` | SAR 遥感感知、Observation、DetectionCandidate、ModelArtifact 推理 |
| 工程可靠性_AGENT_B | `engineering-agent-b` | `C:\Users\WangChi\.local\share\opencode\worktree\a000c91ad0a8e7738f536ede25fad1c661f98fe8\ensemble-geocode-ensemble-mvp-test-shanshui-zhijian-openchamber-6x5sey-engineering-agent-b` | `opencode/ensemble-geocode-ensemble-mvp-test-shanshui-zhijian-openchamber-6x5sey-engineering-agent-b` | `06214d61` | 元数据、RunManifest、评测链适配、CI、环境可复现 |
| 事件治理_AGENT_C | `event-agent-c` | `C:\Users\WangChi\.local\share\opencode\worktree\a000c91ad0a8e7738f536ede25fad1c661f98fe8\ensemble-geocode-ensemble-mvp-test-shanshui-zhijian-openchamber-6x5sey-event-agent-c` | `opencode/ensemble-geocode-ensemble-mvp-test-shanshui-zhijian-openchamber-6x5sey-event-agent-c` | `06214d61` | Evidence、Event、Review、Replay、事务与幂等 |
| 产品工作台_AGENT_D | `product-agent-d` | `C:\Users\WangChi\.local\share\opencode\worktree\a000c91ad0a8e7738f536ede25fad1c661f98fe8\ensemble-geocode-ensemble-mvp-test-shanshui-zhijian-openchamber-6x5sey-product-agent-d` | `opencode/ensemble-geocode-ensemble-mvp-test-shanshui-zhijian-openchamber-6x5sey-product-agent-d` | `06214d61` | React、MapLibre、Workbench API、OpenAPI Client、Dashboard |
| 项目经理_AGENT_E | —（控制面） | `D:\研究生作业\人工智能实践比赛\山水智鉴_Git工作区\integration` | `integration/g0-g1-contract-freeze` | `9a1e910` | 项目路线、Agent 编排、Git 门禁、ML Readiness |

## 已核验事实

- 原五个 OpenCode/GeoCode Session 曾共用一个 working tree，产生 HEAD 与分支名错位；根因已由 reflog 和工作区状态确认。
- 原共享目录保持不变，并建立 recovery branch 与经过 `git bundle verify` 的恢复包。
- A/B/C/D 的旧 clean branch 保留为历史来源，不再继续开发。
- **2026-07-28**：OpenChamber 持久化团队 `shanshui-zhijian-openchamber` 重建完成。
  - 四个成员均已 spawn（`agent=build`, `worktree=true`, `model=deepseek/deepseek-v4-flash`）
  - 每个成员 worktree 唯一、branch 唯一、HEAD 一致
  - 测试消息 `E-OPENCHAMBER-{A,B,C,D}-20260728` 全部收发成功
  - 未修改业务代码、未提交、未 merge、未修改受保护分支
- Ensemble 自动创建 worktree 的基线 commit 为 `06214d61`（Git 仓库 root `master`），不等同于 `integration/g0-g1-contract-freeze` 的 `9a1e910`。正式任务前需确认基线策略。

## 当前阻断

1. 正式 integration 合并等待用户批准。
2. OpenChamber Ensemble 重启后恢复（`team_reconcile` + `team_reactivate`）待验证。

## 下一 Gate

1. 重启 OpenChamber 后验证 `team_reconcile` 恢复能力。
2. 用户决定是否授权 B → A → C → D 逐项合入 integration。

## 不再作为当前状态源的旧分支

旧 `agent-a-*`、`agent-b-*`、`agent-c-*` 混合分支和旧 D clone 只保留为
历史来源，不再继续开发，也不得直接合入 integration。具体恢复过程见
`MULTI_SESSION_OPERATIONS.md`。
