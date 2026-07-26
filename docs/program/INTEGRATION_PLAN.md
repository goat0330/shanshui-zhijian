# 山水智鉴 — 集成计划

> **V0.1 集成计划** — 从分散 Agent 分支到统一基线的完整路线。

---

## 核心原则

1. 现有混合分支**不得直接合并**到 integration
2. 每个 Agent 必须重新形成 **clean branch**（仅含该 Agent 领域文件）
3. 每条 clean branch 从**最新 `integration/g0-g1-contract-freeze`** 创建
4. **一次只合入一个 Agent**，合入后执行统一测试
5. **不使用 octopus merge**
6. **不 force push** develop/main

---

## 集成步骤

### 第 0 步：Governance Bootstrap（已完成，待用户批准正式合入）

| 内容 | 详情 |
|------|------|
| 分支 | `feature/agent-e-integration-control` |
| 基线 | `integration/g0-g1-contract-freeze` @ df7b3e7 |
| 交付 | AGENTS.md, agents/, docs/program/, .github/ |
| Gate | 治理文件验证 + YAML 可解析 + 文档一致性 |
| 目标 | → `integration/g0-g1-contract-freeze` |

### 第 1 步：工程可靠性_AGENT_B

| 内容 | 详情 |
|------|------|
| 分支 | `feature/agent-b-reliability-repair` @ `e8bb744` |
| 基线 | `integration/g0-g1-contract-freeze` (最新) |
| 范围 | 仅 `competition/`, `core/schemas/contracts/run_manifest.py`, `core/schemas/contracts/sar_metadata.py`, `core/schemas/contracts/submission_envelope.py`, `.github/workflows/` |
| Gate | Metadata 可追踪、RunManifest 哈希一致、CI 不吞失败、无 A/C/D 文件 |
| 验证 | `test_b0_sar_metadata.py`, `test_b1_run_manifest.py`, `test_competition_chain.py` |

### 第 2 步：感知算法_AGENT_A

| 内容 | 详情 |
|------|------|
| 分支 | `feature/agent-a-candidate-clean` @ `a2a3c41` |
| 基线 | `integration/g0-g1-contract-freeze` (最新) |
| 范围 | 仅 `tools/`, `core/schemas/contracts/candidate.py`, `core/schemas/contracts/perception.py`, `core/protocols/` |
| Gate | Candidate v0.3 冻结、双时相回归不变、多时相测试通过、无 B/C/D 文件 |
| 验证 | `test_rs01a_tool.py`, `test_rs01b1_quality.py`, `test_rs01b2_multitemporal.py`, `test_rs01b3_persistence.py` |

### 第 3 步：事件治理_AGENT_C

| 内容 | 详情 |
|------|------|
| 分支 | `feature/agent-c-event-clean` @ `6ca477d` |
| 基线 | `integration/g0-g1-contract-freeze` (最新) |
| 范围 | 仅 `services/`, `core/schemas/contracts/event.py`, `core/schemas/contracts/evidence.py`, `core/schemas/contracts/review.py`, `core/schemas/contracts/replay.py`, `core/compatibility/` |
| Gate | 幂等、事务原子、Replay 不重复、Candidate 不被修改、无 A/B/D 文件 |
| 验证 | `test_event_chain_e2e.py`, `test_g03_candidate_contract.py` |

### 第 4 步：产品工作台_AGENT_D

| 内容 | 详情 |
|------|------|
| 分支 | `feature/agent-d-workbench-clean` @ `d58078d` |
| 基线 | `integration/g0-g1-contract-freeze` (最新) |
| 范围 | 仅 `frontend/`, `apps/workbench_api/`, `docs/product/` |
| Gate | Mock/Real 双模式、OpenAPI 类型生成、Playwright 通过、不修改领域合同 |
| 验证 | `vitest` 套件、`playwright` E2E |

### 第 5 步：项目经理_AGENT_E ML Readiness

| 内容 | 详情 |
|------|------|
| 分支 | `feature/agent-e-ml-readiness` |
| 基线 | `integration/g0-g1-contract-freeze` (最新) |
| 范围 | `ml/`, `docs/ml/` |
| Gate | Dataset Registry、License Matrix、规则 Baseline 冻结、不修改 A/B/C/D 代码 |
| 验证 | DatasetAdapter 测试、训练 Pipeline 冒烟 |

### 第 6 步：Unified Integration E2E

- 在所有 clean branch 按序合入后，执行全量测试
- 验证跨 Agent 数据流
- 修复回归问题

### 第 7 步：integration → develop

- 将 `integration/g0-g1-contract-freeze` 合并到 `develop`
- 发布 Release Candidate
- 必须获得用户明确批准

### 第 8 步：真实 AOI Gate + 完整 CI + 演示验收 → main → tag v0.1.0

- 真实 AOI 数据验证
- 完整 CI 流水线
- 产品演示验收
- 合并到 `main`
- 打标签 `v0.1.0`
- 必须获得用户明确批准

---

## 禁止事项

- ❌ 直接从旧 Agent 分支创建新分支
- ❌ 从 `main` 创建开发分支
- ❌ Force push develop/main
- ❌ 重写 develop 历史
- ❌ 在本轮合并前 cherry-pick A/B/C/D 的功能代码
- ❌ 把 10 条现有 Agent 分支一次性合入 integration
- ❌ octopus merge

---

## 执行顺序

```
E (governance) → B (reliability) → A (perception) → C (event) → D (workbench) → E (ml)
→ Integration E2E → develop → main + tag
```
