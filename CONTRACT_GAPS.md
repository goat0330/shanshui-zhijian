# RS-03 合同缺口记录 (Contract Gap Record)

> 冻结版本: rs-contract.v0.3
> 检查日期: 2026-07-27

## 已覆盖的合同

| 合同 | 状态 | 测试文件 |
|------|------|----------|
| `Observation` | ✅ v0.3 冻结 | `test_rs03_baseline.py`, `test_rs03_contract_freeze.py` |
| `PerceptionResult` | ✅ v0.3 冻结 | `test_rs03_baseline.py`, `test_rs03_contract_freeze.py` |
| `DetectionCandidate` | ✅ v0.3 新增 | `test_rs03_contract_freeze.py` |
| `EvidenceRef` | ✅ v0.3 新增 | `test_rs03_contract_freeze.py` |
| `PredictionRecord` | ✅ v0.3 冻结 | `test_rs03_contract_freeze.py` |
| `TaskSpec` | ✅ v0.3 冻结 | `test_rs03_contract_freeze.py` |
| `InferenceTask` | ✅ v0.3 冻结 | `test_rs03_contract_freeze.py` |
| `RunContext` | ✅ v0.3 冻结 | `test_rs03_contract_freeze.py` |
| ID/Track ID 稳定性 | ✅ 新增测试 | `test_rs03_id_stability.py` |
| 双时相回归 | ✅ 新增测试 | `test_rs03_regression.py` |
| 多时相回归 | ✅ 新增测试 | `test_rs03_regression.py` |
| 确定性回归 | ✅ 新增测试 | `test_rs03_regression.py` |
| 工具模式检测 | ✅ 回归验证 | `test_rs03_regression.py` |

## 已知缺口

### 缺口 1: `Observation` → `DetectionCandidate` 聚合引擎缺失

**问题**: `DetectionCandidate` 的 schema 已冻结，但**没有聚合引擎**将多个 `Observation`
实例聚合为 `DetectionCandidate`。当前 `SarTemporalChangeTool` 的 `run()` 直接产生
`PerceptionResult`（包含 `Observation`），但 Candidate 聚合是手动构造的。

**影响**: 产品链中 Obs→Candidate 的聚合缺乏可测试的中间件。

**建议修复**: 实现 `ObservationAggregator` 接口，接受 `list[Observation]` → `DetectionCandidate`。

---

### 缺口 2: `track_id` 赋值逻辑未实现

**问题**: `Observation.track_id` 字段已在 v0.3 中定义为可选字段，但当前所有工具
（`SarTemporalChangeTool`）**不产生 track_id**。track_id 长期为 None。

**影响**: 跨时相追踪不可用。当有 3 期以上数据时，无法通过 track_id 关联同一地物的
不同时相观测。

**建议修复**: 
1. 短期: 在 `SarTemporalChangeTool` 中，对同一 `candidate_type` 且空间重叠的 Obs 赋予相同 track_id
2. 长期: 实现 `Tracker` 模块按 IoU 或质心距离匹配多期 Obs

---

### 缺口 3: `DetectionCandidate.quality_summary` 无标准 schema

**问题**: `quality_summary: dict | None` 是无约束的自由字典。不同工具可能写入不同键，
缺少标准化。

**影响**: 下游消费者无法依赖 quality_summary 的字段结构。

**建议修复**: 定义 `CandidateQualitySummary(BaseModel)` 含 `mean_score`、`n_observations`、
`area_consistency` 等标准化字段，替换自由 dict。

---

### 缺口 4: `EvidenceRef.provenance` 无标准 schema

**问题**: 同缺口 3，`provenance: dict | None` 无约束。

**影响**: 证据来源的追踪不可靠。

**建议修复**: 定义 `Provenance(BaseModel)` 含 `tool_name`、`tool_version`、`run_id`、`parameters`。

---

### 缺口 5: 无批量验证工具

**问题**: `SubmissionValidator` 只验证 `SubmissionBundle` 结构，**不验证**：
- Observation 的 geometry 是否在 bbox 内
- Candidate 的 observation_refs 是否指向真实 Obs
- PerceptionResult 的 artifact_refs 是否可解析

**影响**: 运行时错误只能通过集成测试发现。

**建议修复**: 实现 `CrossReferenceValidator`，遍历 `PerceptionResult` 的
observations → artifact_refs → candidates，验证引用完整性。

---

### 缺口 6: 时间字段无统一格式

**问题**: `Observation.temporal` 和 `DetectionCandidate.temporal_extent` 都是自由 dict，
`created_at` 是 `str | None`，无格式约束（ISO 8601 / Unix timestamp / 其他）。

**影响**: 时间解析需要额外约定。

**建议修复**: 使用 `datetime` 或 `pydantic.AwareDatetime`，或在文档中明确 ISO 8601 格式。

---

### 缺口 7: `coordinate_space` 在 Candidate 中缺失

**问题**: `Observation` 有 `coordinate_space`，但 `DetectionCandidate` 没有。

**影响**: Candidate 的 geometry 无法确认是 geographic 还是 pixel。

**建议修复**: 给 `DetectionCandidate` 添加 `coordinate_space` 字段 (v0.4)。

---

### 缺口 8: 无确定性种子控制测试

**问题**: 测试工具（如 `_make_vh`）使用固定随机种子，但工具内部调用 `numpy` 随机操作
且未固定全局 `numpy.random.seed`。

**影响**: 跨 Python 版本或平台可能产生微小差异。

**建议修复**: 在回归测试中显式调用 `np.random.seed(42)` 固定全局种子。

---

## 未覆盖的合同

以下旧版合同（`detection_result.py`、`event.py`、`evidence.py`、`work_order.py`、`alert.py`）
不在 v0.3 检查范围内，未分析。

## 缺口优先级

| 优先级 | 缺口 | 建议版本 |
|--------|------|----------|
| P0 | 缺口 1: 聚合引擎缺失 | v0.4 |
| P0 | 缺口 2: track_id 赋值 | v0.4 |
| P1 | 缺口 5: 批量验证工具 | v0.4 |
| P2 | 缺口 3: quality_summary schema | v0.5 |
| P2 | 缺口 4: provenance schema | v0.5 |
| P3 | 缺口 6: 时间格式统一 | v0.5 |
| P3 | 缺口 7: coordinate_space 在 Candidate | v0.5 |
| P3 | 缺口 8: 种子控制 | v0.4 |
