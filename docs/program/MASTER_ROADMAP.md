# 山水智鉴 — 主路线图

> **版本**: v0.2 (V5-PRODUCT-STRATEGY)
> **基线**: integration/g0-g1-contract-freeze
> **更新**: 2026-07-27

---

## 产品目标

**研判工作台 + 领导驾驶舱 双前端形态**

| 角色 | 入口 | 功能 |
|------|------|------|
| 河湖异常研判人员 | `/workbench` | 候选→地图定位→影像对比→证据→研判→事件→Replay→Run |
| 管理者/领导/评委 | `/dashboard` | 整体态势、空间分布、时间趋势、研判成效、典型案例 |

两个入口共享同一套 React 组件、领域对象和 API，采用同一 `frontend/` 工程。

---

## 推进顺序

```
P1 ｜ 工程可靠性_AGENT_B
     REL-02 环境隔离 → integration

P2A ｜ 感知算法_AGENT_A (与 P2D 并行)
      RS-03 感知回归与合同冻结

P2D ｜ 产品工作台_AGENT_D (与 P2A 并行)
      WB-01A 组件、Provider、工作台与驾驶舱 Mock
      (范围升级: /workbench + /dashboard)

P3 ｜ 事件治理_AGENT_C (P2A 合同稳定后)
     EVT-02 持久化事件链纵切

P4 ｜ 产品工作台_AGENT_D
     WB-01B 真实 API 接入

P5 ｜ 工程集成 INT-01 + 产品集成 INT-02
     A+B+C 后端主链 + A+B+C+D 全链

P6 ｜ Release Candidate RC-01
     → E 工程审查 → 用户产品验收
     → 完整 GitHub Review
     → develop → main
```

---

## P1｜环境隔离

| 项目 | 内容 |
|------|------|
| Agent | B 工程可靠性 |
| WP | REL-02 环境隔离 |
| 产出 | conftest.py、preflight.ps1、pyproject.toml、CI preflight |
| 状态 | `cfd16dd` 待路径修正后合入 |
| Gate | 128 passed, 0 failed, 2 skipped |

---

## P2A｜感知回归与合同冻结

| 项目 | 内容 |
|------|------|
| Agent | A 感知算法 |
| WP | RS-03 |
| 启动条件 | P1 合入后 |
| 目标 | Observation→Candidate→DeliveryEnvelope 稳定性冻结 |
| 产出 | ID/Track ID 规则、双时相/多时相回归测试、合同缺口记录 |
| Engine Gate | 双时相回归通过、确定性验证、无越权修改 |
| 下游 | C 的 EVT-02 依赖 A 合同稳定 |

---

## P2D｜组件与 Mock 原型

| 项目 | 内容 |
|------|------|
| Agent | D 产品工作台 |
| WP | WB-01A |
| 启动条件 | P1 合入后 |
| 范围 | `/workbench` + `/dashboard` |
| 产出 | Design Tokens、Shared UI、MapLibre 组件、Candidate/Evidence/Review/Dashboard 组件、Mock Provider |
| Engine Gate | Mock/Real 解耦、Vitest、Playwright |
| Product Gates | D0 信息架构、D1 组件视觉、D2 Mock 原型 |
| 注意 | 不依赖 C 后端，不写另一套地图组件 |

---

## P3｜持久化事件链

| 项目 | 内容 |
|------|------|
| Agent | C 事件治理 |
| WP | EVT-02 |
| 启动条件 | P2A Candidate 合同稳定 |
| 产出 | Candidate Intake、EvidenceBundle、Review、Event Version、Replay、SQLite 持久化、应用门面 |
| Gate | 幂等、事务原子、Event 多版本、Replay 去重 |

---

## P4｜真实 API 接入

| 项目 | 内容 |
|------|------|
| Agent | D 产品工作台 |
| WP | WB-01B |
| 启动条件 | P3 C 后端完成 |
| 范围 | MockProvider → RealApiProvider 切换 |
| 产出 | OpenAPI Client、真实数据联动 |
| Product Gate | D3 真实 API |

前端组件不重写，只更换数据来源。

---

## P5｜集成

| 步骤 | 内容 | 涉及 Agent |
|:----:|------|:----------:|
| INT-01 | A+B+C 后端主链验证 | A/B/C |
| INT-02 | A+B+C+D 全链 E2E | A/B/C/D |

---

## P6｜发布候选

```
→ 项目经理_AGENT_E 工程审查
→ 用户产品验收
→ 最终 GitHub Review（完整代码 + Git + CI + 文档）
→ develop → main
```

---

## 训练决策

遵循以下规则：

| 条件 | 行动 |
|------|------|
| B RunManifest + 实验血缘稳定 | ✅ 可开始 |
| A 模型输入输出 + Candidate + 规则 baseline 稳定 | ✅ 可开始 |
| E Dataset Registry + License Matrix + Split Policy 完成 | ✅ 可开始 |
| 三者全部满足 | 启动 SAR 公开数据预训练 |

优先顺序：Sen1Floods11 → Modified Sen1Floods11 → MMFlood → 光学水体分割 Spike → 视频漂浮物 Baseline

训练不需要等待 C/D 全部完成。

---

## Milestones

| Milestone | 目标 | 状态 |
|-----------|------|:----:|
| P1 环境隔离 | 测试可复现 | 🔄 |
| P2A 合同冻结 | Candidate/Observation 稳定 | 🔜 |
| P2D Mock 原型 | 工作台+驾驶舱可操作 | 🔜 |
| P3 事件链 | 持久化事件闭环 | 🔜 |
| P4 真实 API | Mock→Real 切换 | 🔜 |
| P5 集成 | E2E 全链 | 🔜 |
| P6 RC-01 | 首次发布候选 | 🔜 |

最新状态见 [STATUS_BOARD.md](STATUS_BOARD.md)。
