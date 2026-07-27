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
     → 独立架构审查人完整 GitHub Review
     → develop → main
```

### E 并行工作流（贯穿 P1—P5）

以下工作与 P1—P4 并行推进，但不得自动开始正式训练：

| WP-ID | 名称 | 内容 | 状态 |
|:------|------|------|:----:|
| PM-01 | 用户与产品需求 | 用户角色、研判流程、驾驶舱指标、比赛演示路径、Decision Log | 🔜 |
| PM-02 | 市场与竞品 | 遥感监测平台、水域治理平台、GIS 研判工作台、同类比赛获奖项目、竞品矩阵 | 🔜 |
| PM-03 | 采购需求 | 政府采购项目、采购内容、预算、验收指标、最终交付物、私有化需求 | 🔜 |
| MLR-01 | ML Readiness | Dataset Registry、License Matrix、Split Policy、Evaluation Protocol、规则 Baseline | 🔜 |

---

## P1｜环境隔离

| 项目 | 内容 |
|------|------|
| Agent | B 工程可靠性 |
| WP | REL-02 环境隔离 |
| 产出 | conftest.py、preflight.ps1、pyproject.toml、CI preflight |
| 状态 | `AGENT_SELF_REPORTED / PENDING_E_VERIFICATION` — B 自报 `cfd16dd`，128 passed，尚待路径修正 + Clean PR + CI 验证 |
| Gate | B-REL-02 Gate（preflight、PROJ隔离、pytest collection、CI、路径正确、无越权） |
| 返工条件 | 文件路径未在仓库根目录下、CI preflight 未通过、越权修改 A/C/D |

### 产品效果

P1 完成后：
- **研判人员** 还不能操作（B 任务是后端环境，不涉及前端）
- **领导** 还不能查看
- **开发人员** 可以：执行 `pwsh -File scripts/preflight.ps1` 预检环境 / CI 自动验证 / pytest 在干净环境可复现
- **比赛演示** 无新增
- **还不能做的**：PROJ/GDAL 用户级环境变量仍存在（需手动清理）；B 的完整可靠性链（RunManifest、Competition Adapter）尚未就绪

---

## P2A｜感知回归与合同冻结

| 项目 | 内容 |
|------|------|
| Agent | A 感知算法 |
| WP | RS-03 |
| 启动条件 | P1 合入后 |
| 目标 | Observation→Candidate→DeliveryEnvelope 稳定性冻结 |
| 产出 | ID/Track ID 规则、双时相/多时相回归测试、合同缺口记录 |
| Engine Gate | 双时相回归通过、确定性验证、同一输入→相同输出、无越权修改 |
| 返工条件 | ID 不稳定、确定性失败、合同冻结有遗漏、越权修改 B/C/D |
| 下游 | C 的 EVT-02 依赖 A 合同稳定 |

### 产品效果

P2A 完成后：
- **研判人员** 还不能直接操作（依赖 D 前端）
- **领导** 还不能查看
- **Agent C** 可以：start consuming stable Candidate contracts
- **Agent D** 可以：start building Candidate components against frozen schema
- **比赛演示** 无新增
- **还不能做的**：真实候选不依赖手动触发 / 前端展示

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
| Product Gates | D0 信息架构、D1 组件视觉、D2 Mock 原型（标注 MOCK/DEMO） |
| 返工条件 | Mock 数据直接硬编码在组件内 / Mock 地图不同于共享地图 / D2 页面未标注 MOCK |
| 注意 | 不依赖 C 后端，不写另一套地图组件，不宣称真实治理成效 |

### 产品效果

P2D 完成后：

**研判人员可以：**
- 查看 Mock Candidate 列表
- 点 Candidate → 地图定位 → 查看 Mock Evidence
- 提交 Mock Review
- 在 Loading/Empty/Error/Success 四种状态下操作

**领导/评委可以：**
- 查看 Mock 态势总览（候选数、事件数、AOI 覆盖等）
- 查看候选空间分布（地图标注）
- 查看研判漏斗（机器发现→人工研判→确认/驳回/待补证）
- 查看典型案例（历史影像→当前影像→变化掩膜→Candidate→Evidence→Review→Event）
- 切换 `/dashboard` 和 `/workbench` 入口

**比赛演示新增：**
- 领导驾驶舱 Mock 可演示完整比赛场景
- 典型案例可回放

**还不能做的：**
- 查看真实 Event 列表（依赖 C 后端）
- 查看真实 Run 记录（依赖 C 后端 + 真实数据）
- 驾驶舱指标来自真实统计（依赖 C+D3）
- `/dashboard` 页面标注 **MOCK / DEMO**，不得宣称真实治理成效
- 真实准确率（无标签）不得展示

---

## P3｜持久化事件链

| 项目 | 内容 |
|------|------|
| Agent | C 事件治理 |
| WP | EVT-02 |
| 启动条件 | P2A Candidate 合同稳定 |
| 产出 | Candidate Intake、EvidenceBundle、Review、Event Version、Replay、SQLite 持久化、应用门面 |
| Gate | 幂等、事务原子、Event 多版本、Replay 去重、Candidate 只读消费 |
| 返工条件 | Intake 不幂等、事务不原子、并发冲突静默覆盖、Candidate 被修改 |

### 产品效果

P3 完成后：
- **研判人员** 还不能直接操作（需 P4 D 前端接入）
- **领导** 还不能查看
- **Agent D** 可以：开始接入 RealApiProvider（WB-01B）
- **开发人员** 可以：通过 C 的服务门面调用真实事件链
- **还不能做的**：前端可见 / 比赛演示中的真实数据

---

## P4｜真实 API 接入

| 项目 | 内容 |
|------|------|
| Agent | D 产品工作台 |
| WP | WB-01B |
| 启动条件 | P3 C 后端完成 |
| 范围 | MockProvider → RealApiProvider 切换 |
| 产出 | OpenAPI Client、真实数据联动 |
| Product Gate | D3 真实 API（真实数据与 Mock 行为一致、驾驶舱指标来自真实数据） |
| 返工条件 | 切换 Real 组件需重写 / 真实数据与 Mock 行为不一致 / 异常状态缺失 |

前端组件不重写，只更换数据来源。

### 产品效果

P4 完成后：

**研判人员可以：**
- 查看真实 Candidate 列表
- 点真实 Candidate → 地图定位 → 真实 Evidence
- 提交真实 Review → 触发 Event 流转
- 查看 Replay 回顾

**领导/评委可以：**
- 查看真实态势（来自真实 Candidate + Event）
- 查看真实空间分布
- 查看真实研判成效
- 驾驶舱 MOCK/DEMO 标注移除
- 典型案例用真实数据展示

**比赛演示新增：**
-完整的 Candidate→Review→Event→Dashboard 数据闭环

**还不能做的：**
- 模型训练和推断 Pipeline（MLR-01 完成前）
- 比赛正式提交（RunManifest + Competition Adapter 完整）

---

## P5｜集成

| 步骤 | 内容 | 涉及 Agent |
|:----:|------|:----------:|
| INT-01 | A+B+C 后端主链验证 | A/B/C |
| INT-02 | A+B+C+D 全链 E2E | A/B/C/D |

### 产品效果

P5 完成后：
- **研判人员** 可以完成从 Candidate 到 Event 的完整闭环
- **领导** 可以看到完整态势和成效
- **比赛演示** 可以展示完整治理链路
- **还不能做的**：正式发布（需 P6 RC-01 审查）

---

## P6｜发布候选

```
→ 项目经理_AGENT_E 工程审查
→ 用户产品验收
→ 独立架构审查人完整 GitHub Review
→ develop → main
```

---

## 训练决策

遵循以下规则：

| 条件 | 行动 |
|------|------|
| B RunManifest + 实验血缘稳定（B-FINAL Gate 通过） | ✅ 可开始 |
| A 模型输入输出 + Candidate + 规则 baseline 稳定（RS-03 Gate 通过） | ✅ 可开始 |
| E Dataset Registry + License Matrix + Split Policy 完成（MLR-01 完成） | ✅ 可开始 |
| 三者全部满足 | 启动 SAR 公开数据预训练 |

优先顺序：Sen1Floods11 → Modified Sen1Floods11 → MMFlood → 光学水体分割 Spike → 视频漂浮物 Baseline

训练不需要等待 C/D 全部完成。

---

## Milestones

| Milestone | 目标 | 状态 |
|-----------|------|:----:|
| P1 环境隔离 | 测试可复现 | 🔄 AGENT_SELF_REPORTED |
| P2A 合同冻结 | Candidate/Observation 稳定 | 🔜 |
| P2D Mock 原型 | 工作台+驾驶舱可操作 | 🔜 |
| P3 事件链 | 持久化事件闭环 | 🔜 |
| P4 真实 API | Mock→Real 切换 | 🔜 |
| P5 集成 | E2E 全链 | 🔜 |
| P6 RC-01 | 首次发布候选 | 🔜 |

最新状态见 [STATUS_BOARD.md](STATUS_BOARD.md)。
