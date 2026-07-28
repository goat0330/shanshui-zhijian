# 山水智鉴 — 合同缺口登记册

> 记录当前领域合同（Schema）与目标架构之间的差距。
> 每项缺口需标注责任 Agent、影响范围和处置计划。

---

## 当前合同状态

| 合同 | 文件 | 当前版本 | 状态 | 所有者 |
|------|------|:--------:|:----:|:------:|
| AssetRef | `core/schemas/contracts/asset.py` | v0.2 | ✅ 冻结 | A |
| InferenceTask | `core/schemas/contracts/task.py` | v0.2 | ✅ 冻结 | A |
| PerceptionResult | `core/schemas/contracts/perception.py` | v0.2 | ⚠️ 待审 | A |
| Observation | `core/schemas/contracts/perception.py` | v0.2 | ⚠️ 待审 | A |
| DetectionCandidate | `core/schemas/contracts/candidate.py` | v0.3 | 🔄 冻结中 | A |
| SarMetadata | `core/schemas/contracts/sar_metadata.py` | v0.2 | 🔄 冻结中 | B |
| RunManifest | `core/schemas/contracts/run_manifest.py` | v0.2 | 🔄 冻结中 | B |
| SubmissionEnvelope | `core/schemas/contracts/submission_envelope.py` | v0.2 | 🔄 冻结中 | B |
| Evidence | `core/schemas/contracts/evidence.py` | v0.2 | 🔄 冻结中 | C |
| Event | `core/schemas/contracts/event.py` | v0.2 | 🔄 冻结中 | C |
| Review | `core/schemas/contracts/review.py` | v0.2 | 🔄 冻结中 | C |
| Replay | `core/schemas/contracts/replay.py` | v0.2 | 🔄 冻结中 | C |
| ModelArtifact | 待创建 | — | ❌ 未开始 | E |

---

## 合同缺口清单

### CG-001: ModelArtifact 未定义

- **描述**: 无正式 ModelArtifact Schema，ML 推理接入不可靠
- **影响**: Agent A 无法正式接入模型产物
- **所有者**: E → A
- **优先级**: P1
- **处置**: ML Readiness 工作包中定义

### CG-002: CandidateDeliveryEnvelope 未冻结

- **描述**: Candidate 到下游的交付封装尚未正式定义
- **影响**: Agent A 到 Agent C 的接口不完整
- **所有者**: A
- **优先级**: P1
- **处置**: G0.3-A 工作包中完成

### CG-003: EvidenceBundle 未正式定义

- **描述**: 证据包（多证据关联）Schema 缺失
- **影响**: 复杂事件的证据组织
- **所有者**: C
- **优先级**: P1
- **处置**: G1.1 Event 工作中补充

### CG-004: 跨合同版本兼容策略未写

- **描述**: 合同版本升级时，旧版本的支持策略未形式化
- **影响**: 接口升级可能破坏下游
- **所有者**: E
- **优先级**: P2
- **处置**: G0.3 完成后补充

### CG-005: QualityReport Schema 未冻结

- **描述**: 质量报告格式未正式纳入合同
- **影响**: 质量门禁结果不可跨组件消费
- **所有者**: A
- **优先级**: P2
- **处置**: G0.3-A 工作包中完成

---

## V0 兼容对象

| V0 对象 | 当前用途 | 退役条件 |
|---------|----------|----------|
| `DetectionResult` | 兼容映射为 Agent A 输出 | Agent C 正式采纳 Candidate |
| `AlertRecord` (DB) | 演示用告警记录 | 替换为 Event 和 Review |
| `WorkOrderRecord` (DB) | 演示用工单 | 外部治理系统集成 |
