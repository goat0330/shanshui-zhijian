# 山水智鉴 — 多 Agent 治理框架

> **版本**: v0.4 (ENSEMBLE-SUBSESSION)
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

## 2. 岗位编制

| ID | 正式名称 | 英文代号 | Agent 类型 | 核心职责 |
|----|----------|----------|-----------|----------|
| A | 感知算法_AGENT_A | PERCEPTION_AGENT_A | 持久化 Ensemble child | SAR 遥感感知、Observation、DetectionCandidate、ModelArtifact 推理 |
| B | 工程可靠性_AGENT_B | RELIABILITY_AGENT_B | 持久化 Ensemble child | 元数据、RunManifest、评测链适配、CI、环境可复现 |
| C | 事件治理_AGENT_C | EVENT_AGENT_C | 持久化 Ensemble child | Evidence、Event、Review、Replay、事务与幂等 |
| D | 产品工作台_AGENT_D | WORKBENCH_AGENT_D | 持久化 Ensemble child | React、MapLibre、Workbench API、OpenAPI Client |
| E | 项目经理_AGENT_E | PROGRAM_AGENT_E | **顶层控制面 Session** | 项目路线、Agent 编排、Git 门禁、ML Readiness |

详细角色定义见 [`agents/`](agents/) 目录。

Agent ID 是稳定身份，不是永久技能限制。每轮职责由 Work Package 定义。
职责变化必须同步更新允许目录、输入输出合同、验收 Gate 和 Handoff，
不得口头漂移。

### 控制关系

```
用户（最终决策人和 Merge Gate Owner）
 └── PROGRAM_AGENT_E：唯一顶层控制面 Session
      ├── PERCEPTION_AGENT_A：持久化 Ensemble child Session
      ├── RELIABILITY_AGENT_B：持久化 Ensemble child Session
      ├── EVENT_AGENT_C：持久化 Ensemble child Session
      └── WORKBENCH_AGENT_D：持久化 Ensemble child Session
```

---

## 3. 分支策略

| 分支 | 用途 | 来源 | 合并目标 |
|------|------|------|----------|
| `main` | 只读发布标签 | `develop` | — |
| `develop` | 日常开发集成分支 | — | `develop` |
| `integration/g0-g1-contract-freeze` | G0-G1 集成门禁基线 | `develop` | `develop` |
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

详细规范见 [`docs/program/BRANCH_STRATEGY.md`](docs/program/BRANCH_STRATEGY.md)。

---

## 4. 合并顺序

| 步骤 | 内容 | 责任 Agent |
|------|------|------------|
| 0 | Governance Bootstrap | E |
| 1 | 工程可靠性 | B → integration |
| 2 | 感知算法 | A → integration |
| 3 | 事件治理 | C → integration |
| 4 | 产品工作台 | D → integration |
| 5 | ML Readiness | E → integration |
| 6 | Unified Integration E2E | E |
| 7 | integration → develop | 用户批准，E 执行或协助 |
| 8 | develop → main → Release Tag | 用户批准，E 执行或协助 |

每个 Agent 必须形成只含本 Work Package 的独立分支，从最新
`integration/g0-g1-contract-freeze` 创建；一次只合入一个 Agent，
每次合入后执行统一测试。Ensemble 自动分支不要求使用 `feature/agent-*` 名称。

Agent E 只有审计、编排和提出 `MERGE_READY` 的权限；没有用户明确批准时，
不得合并 `integration`、`develop` 或 `main`。

---

## 5. Merge Gate

每个 Agent 提交至 `integration/g0-g1-contract-freeze` 前必须通过对应 Gate。

各 Agent Gate 定义见：
- [感知算法 Gate](agents/感知算法_AGENT_A.md) — Candidate v0.3 冻结、Observation→Candidate 完整、ModelArtifact 接口明确
- [工程可靠性 Gate](agents/工程可靠性_AGENT_B.md) — Metadata 可追溯、RunManifest 哈希一致、CI 不吞失败
- [事件治理 Gate](agents/事件治理_AGENT_C.md) — 首次 intake、重试幂等、事务原子、Candidate 不被修改
- [产品工作台 Gate](agents/产品工作台_AGENT_D.md) — Mock/Real 双模式、OpenAPI 类型生成、Playwright
- [项目经理 Gate](agents/项目经理_AGENT_E.md) — Dataset Registry、License Matrix、规则 Baseline 冻结

详细 Gate 定义见 [`docs/program/RELEASE_GATE.md`](docs/program/RELEASE_GATE.md)。

---

## 6. 代码所有权

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

## 7. 任务分发规则

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

## 8. Code Review 规则

每个 Agent 提交执行：
1. Branch 和 Commit 核对
2. 与 `integration/g0-g1-contract-freeze` 的 diff
3. 越权修改检查
4. 共享合同变更
5. 测试语义覆盖
6. 测试是否 skip
7. CI 状态
8. 运行摘要
9. 文档与代码一致性
10. 下游兼容性

Review 结果：
- **PASS**
- **CONDITIONALLY_PASSED**
- **CHANGES_REQUIRED**
- **BLOCKED**

不得因为"测试数量很多"自动 PASS。

---

## 9. GitHub Labels

| 类别 | Labels |
|------|--------|
| Agent | `agent:A` `agent:B` `agent:C` `agent:D` `agent:E` |
| Area | `area:perception` `area:reliability` `area:event` `area:workbench` `area:ml` `area:integration` |
| Status | `status:ready` `status:in-progress` `status:blocked` `status:review` `status:merge-ready` |
| Priority | `priority:P0` `priority:P1` |
| Special | `contract-gap` `breaking-change` |

---

## 10. Milestones

| Milestone | 目标 |
|-----------|------|
| G0.3 Contract Freeze | 领域合同形式化冻结 |
| G1.1 Event Integrity | 事件链完整性通过 |
| D0 Workbench V0 | 产品工作台 V0 |
| ML-00 Readiness | 训练管线就绪 |
| V0.1 Integration Release | 首次集成发布 |

---

## 11. 状态源

最新状态见：
- **驾驶舱**: [`山水智鉴_项目驾驶舱.md`](山水智鉴_项目驾驶舱.md)
- **Status Board**: [`docs/program/STATUS_BOARD.md`](docs/program/STATUS_BOARD.md)
- **决策日志**: [`docs/program/DECISION_LOG.md`](docs/program/DECISION_LOG.md)
- **合同缺口**: [`docs/program/CONTRACT_GAP_REGISTER.md`](docs/program/CONTRACT_GAP_REGISTER.md)

---

*本文档由项目经理_AGENT_E 维护。修改需经 Architecture Review。*
