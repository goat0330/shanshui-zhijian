# 山水智鉴 — Agent 状态面板

> 更新：2026-07-28
>
> 正式 integration：`integration/g0-g1-contract-freeze` @ `2841bd0`（含 3c55d5f + 607fa5d + CANDIDATE_V0_3）
>
> OpenChamber Ensemble 团队：`shanshui-zhijian-openchamber`（持久化 `persistent=true`）
> 模型统一：`opencode-go/deepseek-v4-flash/max`
> 用户无法直接与子 Agent 对话，由 E 中转。

## 当前 Cycle PR

| PR | Agent | 工作包 | Branch | 状态 |
|:--:|:-----:|--------|--------|:----:|
| #22 | A | ML-SMOKE-00 训练冒烟管线（需改名+修复） | `pr/agent-a-ml-baseline` | CHANGES_REQUIRED — 保留现存实现，A 继续 |
| #24 | B | ML 环境 + RunManifest + Smoke CI | `pr/agent-b-ml-environment` | ✅ 等待 A/D/Gate 后合入 |
| #25 | C | RC-03 桥接 + ingest API + dashboard | `pr/agent-c-event-governance` | ✅ 等待 A/D/Gate 后合入 |
| #23 | D | Dashboard 产品方案（B2 布局，需修正+实现骨架） | `pr/agent-d-product-plan` | 产品方向通过 — D 按 B2 继续 |

## 各 Agent 当前工作

| Agent | 工作包 | 当前任务 | 状态 |
|:-----:|--------|---------|:----:|
| A | ML-SMOKE-00 | 修复 PR #22：改名、删除 CSV、修复 data_adapter、标记 synthetic | working |
| B | ML 环境 | 补充可选依赖 + ML Smoke CI + RunManifest + branch 检查脚本 | working |
| C | RC-03 | Evidence/Review/Event/Replay 桥接 + DashboardSnapshot 聚合 | working |
| D | Dashboard B2 | 修正文档 + 实现 React 骨架 + 单端点 snapshot | working |
| E | 控制面 | Git 门禁 + 合同冲突处理 + 最终集成 | working |

## 合入顺序

B → A → C → D（A/D 就绪后快速 Gate 检查，四个全部合入后再跑完整测试+E2E）

## 不再作为当前状态源的旧分支

旧 `agent-a-*`、`agent-b-*`、`agent-c-*` 混合分支、`feature/agent-d-workbench-v0` 已删除。
`integration-base` 作为纯净基线分支远程保留。
