# 山水智鉴 — 主路线图

> **版本**: v0.1 (GOV-02)
> **基线**: integration/g0-g1-contract-freeze @ 1fe33b0
> **更新**: 2026-07-26

---

## 阶段总览

```
Phase 0: V0 原型            ✅ 已完成
Phase 1: Contract Freeze     ⏳ 当前阶段 (G0.3)
Phase 2: Event Integrity     🔜 进行中 (G1.1)
Phase 3: Workbench V0        🔜 进行中 (D0)
Phase 4: ML Readiness        🔜 待启动 (ML-00)
Phase 5: Integration E2E     🔜 待启动
Phase 6: Release V0.1        🔜 待启动
```

---

## 第一阶段：Contract Freeze (G0.3)

| 工作包 | Agent | 状态 | 产出 |
|--------|-------|:----:|------|
| GOV-02 多 Agent 治理基线 | E | ✅ 完成 | AGENTS.md, agents/, docs/program/ |
| G0.3-A Candidate 冻结 | A | 🔄 进行中 | candidate.py v0.3, SensorTracking |
| G0.3-B Reliability 冻结 | B | 🔄 进行中 | run_manifest.py, sar_metadata.py |
| G0.3-C Event 完整性 | C | 🔄 进行中 | event.py, review.py, evidence.py |
| D0 Workbench V0 | D | 🔄 进行中 | 前端原型, workbench API |

Gate 完成条件：所有合同 schema 冻结 + 契约测试通过 + 无跨 Agent 越权修改。

---

## 第二阶段：Event Integrity (G1.1)

| 工作包 | Agent | 状态 | 产出 |
|--------|-------|:----:|------|
| G1.1-C Event 幂等与事务 | C | 🔄 进行中 | 重试幂等, transaction 原子 |
| G1.1 Review 乐观锁 | C | 🔜 | Review 并发控制 |
| G1.1 Replay 不重复 | C | 🔜 | Replay 去重 |

---

## 第三阶段：Workbench V0 (D0)

| 工作包 | Agent | 状态 | 产出 |
|--------|-------|:----:|------|
| D0-D9 产品工作台 | D | 🔄 进行中 | 五页壳、MapLibre、Mock API |

---

## 第四阶段：ML Readiness (ML-00)

| 工作包 | Agent | 状态 | 产出 |
|--------|-------|:----:|------|
| Dataset Registry | E | 🔜 | 数据集清单、许可证审计 |
| Split Policy | E | 🔜 | Train/Val/Test 不泄漏 |
| ModelArtifact | E | 🔜 | 规范定义 |
| 规则 Baseline | E | 🔜 | 冻结 |
| 训练 Pipeline | E | 🔜 | 可复现 |

---

## 第五阶段：Integration E2E

参见 [INTEGRATION_PLAN.md](INTEGRATION_PLAN.md)。

---

## 第六阶段：Release V0.1

参见 [RELEASE_GATE.md](RELEASE_GATE.md)。

最新状态见 [STATUS_BOARD.md](STATUS_BOARD.md)。
