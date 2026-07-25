# 山水智鉴 — Agent 状态面板

> **更新**: 2026-07-26
> **基线**: integration/g0-g1-contract-freeze @ 1fe33b0
> **审查**:
>   - `develop` @ 1fe33b0
>   - `main` @ d00a94b

---

## 五 Agent 状态表

| Agent | Work Package | Branch | Commit | PR | CI | Ownership | Gate | Blocker |
|-------|-------------|--------|--------|:--:|:--:|:---------:|:----:|:-------:|
| **E** | GOV-02 治理基线 | `feature/agent-e-program-governance` | *(当前)* | - | - | ✅ 允许 | GOV-02 | 等待创建 PR |
| **B** | G0.3 Reliability | `origin/feature/agent-b-g0.3-reliability-final` | `c32e753` | - | - | ⚠️ 含 `.github/workflows/ci.yml` | G0.3-B | 未合并 |
| **A** | G0.3 Candidate | `origin/feature/agent-a-g0.3-candidate-final` | `0a3c6d1` | - | - | ⚠️ 含 `services/` `tests/` 文件 | G0.3-A | 未合并 |
| **C** | G1.1 Event | `origin/feature/agent-c-g1.1-event-integrity` | `bc0a830` | - | - | ✅ 仅事件域文件 | G1.1-C | 未合并 |
| **D** | D0 Workbench | `feature/agent-d-workbench-v0` | `bdfc121` (本地) | - | - | ✅ 仅 frontend+workbench_api | D0 | 未推送 |

---

## 远程 Agent 分支清单

### 感知算法_AGENT_A 分支

| Branch | Head | Ahead | Behind | 文件数 | 跨目录风险 |
|--------|:----:|:-----:|:------:|:------:|:----------:|
| `agent-a-g0-lineage` | cd1fc66 | 1 | 1 | _(衍生基线)_ | 低 |
| `agent-a-g0.1-lineage` | 9dd30c3 | 7 | 7 | _(中间版本)_ | 中 |
| **`agent-a-g0.3-candidate-final`** | **0a3c6d1** | **7** | **7** | **23** | **⚠️ 含 services/, tools/ 等跨域文件** |
| `agent-a-perception-candidate` | cff8508 | 15 | 15 | 36 | ⚠️ 含 aoi-data-prep/ 等 |

### 工程可靠性_AGENT_B 分支

| Branch | Head | Ahead | Behind | 文件数 | 跨目录风险 |
|--------|:----:|:-----:|:------:|:------:|:----------:|
| `agent-b-data-competition` | 8f5c816 | 3 | 3 | 14 | 低 |
| `agent-b-g0-reliability` | 2cd380e | 1 | 1 | _(衍生)_ | 低 |
| **`agent-b-g0.3-reliability-final`** | **c32e753** | **2** | **2** | **13** | **⚠️ 含 CI/YML 文件** |

### 事件治理_AGENT_C 分支

| Branch | Head | Ahead | Behind | 文件数 | 跨目录风险 |
|--------|:----:|:-----:|:------:|:------:|:----------:|
| `agent-c-event-review` | c0ea835 | 1 | 1 | 13 | ✅ 仅事件域 |
| **`agent-c-g1.1-event-integrity`** | **bc0a830** | **3** | **3** | **19** | **⚠️ 含 tools/ 文件 (多时相)** |

### 产品工作台_AGENT_D 分支

| Branch | Head | Ahead | Behind | 文件数 | 跨目录风险 |
|--------|:----:|:-----:|:------:|:------:|:----------:|
| `agent-d-workbench-v0` (本地) | bdfc121 | 1 | 0 | ~100+ | ✅ 仅 frontend+workbench_api |

### 其他分支

| Branch | Head | Ahead | Behind | 说明 |
|--------|:----:|:-----:|:------:|------|
| `aoi-data-prep` | ee5152b | 10 | 10 | ⚠️ 含感知+评测混合文件 |

---

## 跨 Agent 文件冲突检测

| 文件 | 冲突 Agent | 当前 Owner | 建议处理 |
|------|:----------:|:----------:|----------|
| `core/schemas/contracts/candidate.py` | A, C (agent-c-event-review), A (perception) | A | A 为主，C 只读消费 |
| `core/schemas/contracts/event.py` | C, A (g0.3-candidate-final) | C | C 为主，A 中的 event.py 应为误写入 |
| `tools/multi_temporal_background.py` | A (perception), C (g1.1-event) | A | A 为主，C 的改动应合并到 A |
| `tools/persistence_background.py` | A (perception), A (g0.3), C (g1.1) | A | A 为主 |
| `tools/sar_temporal_change_tool.py` | A (perception), A (g0.3), C (g1.1) | A | A 为主 |
| `tests/test_rs01b3_persistence.py` | A, C | A | A 为主 |

---

## 已废弃 / 建议归档的分支

| 分支 | 被取代者 | 原因 |
|------|----------|------|
| `agent-a-g0-lineage` | `g0.3-candidate-final` | 中间版本 |
| `agent-a-g0.1-lineage` | `g0.3-candidate-final` | 中间版本 |
| `agent-a-perception-candidate` | `g0.3-candidate-final` | 混合分支 |
| `agent-b-data-competition` | `g0.3-reliability-final` | 中间版本 |
| `agent-b-g0-reliability` | `g0.3-reliability-final` | 中间版本 |
| `agent-c-event-review` | `g1.1-event-integrity` | 早期版本 |
| `backend-services` | (merged to develop) | 已合并 |
| `core-schemas` | (merged to develop) | 已合并 |
| `frontend` | (merged to develop) | 已合并 |
| `rs-pipeline` | (merged to develop) | 已合并 |
| `smart-city` | (merged to develop) | 已合并 |
| `tests` | (merged to develop) | 已合并 |
| `iaic-integration` | (merged to develop) | 已合并 |

---

## 建议保留的源 Commit

| Commit | 分支 | 理由 |
|--------|------|------|
| `1fe33b0` | develop | 当前 develop 基线 |
| `0a3c6d1` | agent-a-g0.3-candidate-final | Agent A 最新候选冻结 |
| `c32e753` | agent-b-g0.3-reliability-final | Agent B 最新可靠性 |
| `bc0a830` | agent-c-g1.1-event-integrity | Agent C 最新事件完整性 |
| `bdfc121` | agent-d-workbench-v0 | Agent D 工作台完成 |
