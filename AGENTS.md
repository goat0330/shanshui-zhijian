# 山水智鉴 — 多 Agent 治理框架

> **版本**: v0.5 (V5-PRODUCT-STRATEGY)
> **最新更新**: 2026-07-27
> **基线分支**: `integration/g0-g1-contract-freeze`
> **控制面**: GeoCode 顶层 Agent E + 持久化 Ensemble Subsessions A/B/C/D

---

## 1. 项目定位

山水智鉴是面向**水域异常感知、证据核验与治理系统集成**的开放中间件，
同时服务产品治理链和比赛评测链。

### 产品治理链

```
Source → Asset → Observation → DetectionCandidate → Evidence
→ Review → AnomalyEvent → Replay → 外部治理系统
```

### 比赛评测链

```
CompetitionInput → InferenceTask → PerceptionResult
→ PredictionRecord → SubmissionPayload → SubmissionEnvelope → Validator
```

两条链共享：输入 Asset、预处理、模型、权重、运行记录、Artifact。
但产品人工审核结果**不得反向修改比赛预测**。

---

## 2. 最终产品形态

双前端入口，同一 React 工程：

| 角色 | 入口 | 功能 |
|------|------|------|
| 河湖异常研判人员 | `/workbench` | 候选→地图定位→影像对比→证据→研判→事件→Replay→Run |
| 管理者/领导/评委 | `/dashboard` | 整体态势、空间分布、时间趋势、研判成效、典型案例 |

**前端一级模块：**
1. 研判工作台
2. 领导驾驶舱
3. 事件中心
4. 运行记录
5. 系统设置

共享机制：
- 研判工作台和领导驾驶舱使用同一套 React 组件、领域对象和 API
- 不采用两套前端工程、不采用微前端、不采用两套独立组件库
- 地图组件（GovernanceMap、LayerRegistry、CandidateLayerAdapter、EventLayerAdapter、MapLegend）共用

---

## 3. 岗位编制

| ID | 正式名称 | 英文代号 | Agent 类型 | 核心职责 |
|----|----------|----------|-----------|----------|
| A | 感知算法_AGENT_A | PERCEPTION_AGENT_A | 持久化 Ensemble child | SAR 遥感感知、Observation、DetectionCandidate、ModelArtifact 推理 |
| B | 工程可靠性_AGENT_B | RELIABILITY_AGENT_B | 持久化 Ensemble child | 元数据、RunManifest、评测链适配、CI、环境可复现 |
| C | 事件治理_AGENT_C | EVENT_AGENT_C | 持久化 Ensemble child | Evidence、Event、Review、Replay、事务与幂等 |
| D | 产品工作台_AGENT_D | WORKBENCH_AGENT_D | 持久化 Ensemble child | React、MapLibre、Workbench API、OpenAPI Client、Dashboard |
| E | 项目经理_AGENT_E | PROGRAM_AGENT_E | **顶层控制面 Session** | 项目路线、Agent 编排、Git 门禁、ML Readiness、产品调研与验收组织 |

详细角色定义见 [`agents/`](agents/) 目录。

Agent ID 是稳定身份，不是永久技能限制。每轮职责由 Work Package 定义。
职责变化必须同步更新允许目录、输入输出合同、验收 Gate 和 Handoff，
不得口头漂移。

### 控制关系

```
用户（最终决策人、Merge Gate Owner、产品最终验收人）
 └── PROGRAM_AGENT_E：唯一顶层控制面 Session
      ├── PERCEPTION_AGENT_A：持久化 Ensemble child Session
      ├── RELIABILITY_AGENT_B：持久化 Ensemble child Session
      ├── EVENT_AGENT_C：持久化 Ensemble child Session
      └── WORKBENCH_AGENT_D：持久化 Ensemble child Session
```

### 用户、E 与独立审查人的职责边界

| 职责 | 用户 | AGENT_E | 独立审查人 |
|------|:----:|:-------:|:----------:|
| 用户角色定义、信息架构、驾驶舱指标、视觉方向、V0 范围 | ✅ 拍板 | — | — |
| 产品最终验收 | ✅ 执行 | — | — |
| integration→develop 批准、develop→main 最终批准 | ✅ 执行 | — | — |
| 产品调研、PRD 整理、用户需求记录、产品任务拆分 | — | ✅ | — |
| 竞品分析、采购需求分析、比赛需求跟踪 | — | ✅ | — |
| Decision Log、Contract Gap、ML Readiness | — | ✅ | — |
| Agent 编排派单、工程审计、Git 门禁 | — | ✅ | — |
| Branch/PR/CI/Worktree 检查、MERGE_READY 判断 | — | ✅ | — |
| RC 材料整理 | — | ✅ | — |
| main 前完整 GitHub Review（代码+分支+CI+文档+许可证） | — | — | ✅ |

---

## 4. 分支策略

| 分支 | 用途 | 来源 | 合并目标 |
|------|------|------|----------|
| `main` | 只读发布标签 | `develop` | — |
| `develop` | 日常开发集成分支 | — | `develop` |
| `integration/g0-g1-contract-freeze` | 集成门禁基线 | `develop` | `develop` |
| `feature/agent-*-*` | 各 Agent 工作分支 | `integration/g0-g1-contract-freeze` | `integration/g0-g1-contract-freeze` |
| `ensemble/.../<member>` | Ensemble 自动 worktree 分支 | `integration/g0-g1-contract-freeze` | `integration/g0-g1-contract-freeze` |
| `archive/legacy-*` | 只读历史存档 | — | — |

禁止：octopus merge、force push develop/main、从旧 Agent 分支创建新分支。

### Session 隔离硬规则

**PROGRAM_AGENT_E** 是唯一顶层控制面 Session。
**A/B/C/D** 是持久化 Ensemble child Sessions，由 `team_spawn` 以
`agent=build`、`worktree=true` 和显式模型创建。

每个可写成员必须绑定唯一 worktree 与唯一分支。禁止两个可写 Session
共用同一工作目录，也禁止成员运行期间切换分支。

实际启动和恢复步骤见
[`docs/program/MULTI_SESSION_OPERATIONS.md`](docs/program/MULTI_SESSION_OPERATIONS.md)。

### Agent E 调度规则

成员完成后保持 `idle`；重新派单前将 `reported_to_lead=0`，再发送 `team_message`。除非用户明确要求，不得 shutdown、cleanup 或重复 spawn。

详细规范见 [`docs/program/BRANCH_STRATEGY.md`](docs/program/BRANCH_STRATEGY.md)。

---

## 5. 推进顺序

```
P1 ｜ B 工程可靠性 — 环境隔离
P2A｜ A 感知算法 — 感知回归与合同冻结 (与 P2D 并行)
P2D｜ D 产品工作台 — 组件与 Mock 原型 (与 P2A 并行)
P3 ｜ C 事件治理 — 持久化事件链
P4 ｜ D 产品工作台 — 真实 API 接入
P5 ｜ INT-01/02 后端集成 + 产品集成
P6 ｜ RC-01 发布候选
```

E 并行工作流（贯穿 P1-P5，不得自动开始正式训练）：
- PM-01｜用户与产品需求
- PM-02｜市场与竞品分析
- PM-03｜采购需求对接
- MLR-01｜ML Readiness（Dataset Registry、License Matrix、Split Policy）

详细路线图见 [`docs/program/MASTER_ROADMAP.md`](docs/program/MASTER_ROADMAP.md)。
详细门禁定义见 [`docs/program/RELEASE_GATE.md`](docs/program/RELEASE_GATE.md)。

---

## 6. 合并权限

> `auto_merge: false` 表示 Ensemble 插件不会在 cleanup 时自动将 Agent 分支合并至 integration。
> E 在 Gate 全部通过后，可通过 GitHub PR（`gh pr merge` 或 Web UI）手动将 Clean PR 合入 integration。
> `integration → develop` 和 `develop → main` 仍须用户确认。

| 操作 | 权限 | 备注 |
|------|------|------|
| Clean PR → integration | E 已获常规授权，Gate 通过后可执行 | Product Gate 涉及 D 时，须先取得用户验收 |
| integration → develop | 用户确认 | E 输出 MERGE_READY_TO_DEVELOP，用户批准后执行 |
| develop → main | 用户最终确认 | E 完成 RC 审计 + 用户产品验收 + 独立审查人 MERGE_READY_TO_MAIN |

最终发布到 main 前，必须经过三层审查：
1. **E 工程审查** — Branch/PR/CI/Worktree/测试/文档
2. **用户产品验收** — 全功能操作验收
3. **独立架构审查人** — 完整 GitHub Review（代码、架构边界、测试可信度、文档、许可证）

---

## 7. 代码所有权

| 目录 | 责任 Agent |
|------|-----------|
| `core/schemas/contracts/candidate.py` | A |
| `core/schemas/contracts/perception.py` | A |
| `core/schemas/contracts/event.py` | C |
| `core/schemas/contracts/evidence.py` | C |
| `core/schemas/contracts/review.py` | C |
| `core/schemas/contracts/replay.py` | C |
| `core/schemas/contracts/run_manifest.py` | B |
| `core/schemas/contracts/sar_metadata.py` | B |
| `core/schemas/contracts/submission_envelope.py` | B |
| `competition/` | B |
| `tools/` | A |
| `services/` | C |
| `apps/workbench_api/` | D |
| `frontend/` | D |
| `docs/product/` | D 负责，E 审批 |
| `tests/` | 按测试内容对应 Agent |

所有权映射见 [`.github/agent-owners.yml`](.github/agent-owners.yml)。

---

## 8. 任务分发规则

每个 Agent Task 必须包含：
- Agent 正式名称
- Work Package ID
- 基线 Commit
- 业务目标
- 允许修改目录
- 禁止修改目录
- 输入合同
- 输出合同
- 必须测试
- Gate
- Stop Condition
- 交付格式
- 下游 Agent

一次只分配一个核心目标 + 一个 Gate + 一个停止条件。
不得同时派发架构重构、新功能、训练、前端等多个无边界任务。

---

## 9. Code Review 规则

每个 Agent 提交执行：
1. Branch 和 Commit 核对
2. 与 `integration/g0-g1-contract-freeze` 的 diff
3. 越权修改检查
4. 共享合同变更
5. 测试语义覆盖
6. 测试是否 skip
7. CI 状态
8. 运行摘要
9. Agent 自报状态标记为 PENDING_E_VERIFICATION（须 E 验证后才改为 VERIFIED）
10. 文档与代码一致性
11. 下游兼容性

Review 结果：
- **PASS**
- **CONDITIONALLY_PASSED**
- **CHANGES_REQUIRED**
- **BLOCKED**

不得因为"测试数量很多"自动 PASS。

---

## 10. 返工机制

每个 Agent 提交后执行：

```
Agent 自检 + Agent 自报（PENDING_E_VERIFICATION）
→ 项目经理_AGENT_E 工程 Review + 验证 → VERIFIED
→ 用户产品验收（如适用）
→ integration
```

未通过时：

| 裁决 | 含义 |
|------|------|
| `RETURN_TO_AGENT_A` | A 的问题由 A 返工 |
| `RETURN_TO_AGENT_B` | B 的问题由 B 返工 |
| `RETURN_TO_AGENT_C` | C 的问题由 C 返工 |
| `RETURN_TO_AGENT_D` | D 的问题由 D 返工 |
| `RETURN_TO_AGENT_E` | 治理问题由 E 返工 |

规则：
- E 不能替其他 Agent 修改其所有权代码
- 跨合同冲突由 E 组织联合修复，但文件所有者负责提交
- 产品验收失败 = `RETURN_TO_AGENT_D` + 用户重新指定产品方向

---

## 11. 产品验收点

| Gate | 内容 | 验收人 |
|:----:|------|--------|
| D0 | 信息架构：页面结构、路由、组件树、用户流程 | 用户 |
| D1 | 组件视觉：Design Tokens、Card、地图、图表 | 用户 |
| D2 | Mock 原型：工作台+驾驶舱可操作（标注 MOCK/DEMO） | 用户 |
| D3 | 真实 API 集成 | 用户 |

D2 特别注意：
- `/dashboard` 使用 Mock 数据完整展示预定业务指标和典型案例
- 页面明确标注 **MOCK / DEMO**
- 不得宣称为真实治理成效、真实准确率或真实业务统计

详细条件见 [`docs/program/RELEASE_GATE.md`](docs/program/RELEASE_GATE.md)。

---

## 12. GitHub Labels

| 类别 | Labels |
|------|--------|
| Agent | `agent:A` `agent:B` `agent:C` `agent:D` `agent:E` |
| Area | `area:perception` `area:reliability` `area:event` `area:workbench` `area:dashboard` `area:ml` `area:integration` |
| Status | `status:ready` `status:in-progress` `status:blocked` `status:review` `status:merge-ready` `status:product-review` |
| Priority | `priority:P0` `priority:P1` |
| Special | `contract-gap` `breaking-change` `product-gate` `return-to-agent` |

---

## 13. Milestones

| Milestone | 目标 | 状态 |
|-----------|------|:----:|
| P1 环境隔离 | 测试可复现 | 🔄 |
| P2A 合同冻结 | Candidate/Observation 稳定 | 🔜 |
| P2D Mock 原型 | 工作台+驾驶舱可操作 | 🔜 |
| P3 事件链 | 持久化事件闭环 | 🔜 |
| P4 真实 API | Mock→Real 切换 | 🔜 |
| P5 集成 | E2E 全链 | 🔜 |
| P6 RC-01 | 首次发布候选 | 🔜 |

---

## 14. E 六段式汇报模板

每轮必须按以下格式汇报：

1. **本轮产品效果** — 研判人员能做什么、领导能看到什么、比赛新增什么、还不能做什么
2. **五 Agent 状态** — A/B/C/D/E 本轮目标、实际完成、工程 Review、产品 Review、是否返工
3. **Git 状态** — 每个 Agent 的 Branch/Base/Head/PR/Files/CI/Ahead-Behind/Worktree Clean
4. **P0/P1/P2 问题** — 按优先级和责任 Agent 列出
5. **下一轮计划** — 每个任务说明：为什么现在做、完成效果、责任 Agent、依赖、工程 Gate、产品 Gate、返工条件
6. **Merge 与 Training 决策** — 仅用下面 12 个状态之一

决策状态词汇：

- `MERGE_READY_TO_INTEGRATION`
- `NOT_READY_TO_INTEGRATION`
- `MERGE_READY_TO_DEVELOP`
- `NOT_READY_TO_DEVELOP`
- `MERGE_READY_TO_MAIN`
- `NOT_READY_TO_MAIN`
- `PUBLIC_PRETRAINING_READY`
- `PUBLIC_PRETRAINING_NOT_READY`

---

## 15. 状态源

最新状态见：
- **驾驶舱**: [`山水智鉴_项目驾驶舱.md`](山水智鉴_项目驾驶舱.md)
- **Status Board**: [`docs/program/STATUS_BOARD.md`](docs/program/STATUS_BOARD.md)
- **决策日志**: [`docs/program/DECISION_LOG.md`](docs/program/DECISION_LOG.md)
- **合同缺口**: [`docs/program/CONTRACT_GAP_REGISTER.md`](docs/program/CONTRACT_GAP_REGISTER.md)
- **路线图**: [`docs/program/MASTER_ROADMAP.md`](docs/program/MASTER_ROADMAP.md)
- **门禁定义**: [`docs/program/RELEASE_GATE.md`](docs/program/RELEASE_GATE.md)

---

*本文档由项目经理_AGENT_E 维护。修改需经 Architecture Review。*
