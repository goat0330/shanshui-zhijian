# 山水智鉴 V0 — 合同缺口记录

> 版本: v0.1
> 更新: 2026-07-26

---

## Gap 记录格式

每条 Gap 包含：
- gap_id: 唯一标识
- 当前合同: 现有 Schema 定义
- 前端需求: 前端展示需要的数据
- 缺失字段: 具体缺失的内容
- 建议负责人: A/B/C
- 临时 Mock 处理: 如何伪造
- 是否阻断: yes/no
- 期望解决版本: 目标版本

---

## Gap List

### GAP-001: Candidate 合同缺失

| 字段 | 说明 |
|------|------|
| gap_id | GAP-001 |
| 当前合同 | `core/schemas/detection_result.py` — DetectionResult 是唯一候选合同，但无 persistence / temporal / score_components 字段 |
| 前端需求 | Candidate 需要 persistence_status, occurrence_count, persistence_ratio, temporal_extent, score_components, run_manifest_ref |
| 缺失字段 | persistence_status, occurrence_count, persistence_ratio, temporal_extent, score_components, run_manifest_ref, representative_geometry, union_geometry, quality_summary |
| 建议负责人 | Agent A |
| 临时 Mock 处理 | 在 Mock 数据中直接构造完整 CandidateDTO |
| 是否阻断 | yes |
| 期望解决版本 | v0.2 |

### GAP-002: Review 合同缺失

| 字段 | 说明 |
|------|------|
| gap_id | GAP-002 |
| 当前合同 | 无 Review 专用 Schema |
| 前端需求 | ReviewDecision 完整 schema：action, category, comment, evidence_refs, actor_ref, base_version |
| 缺失字段 | 完整合同缺失 |
| 建议负责人 | Agent C |
| 临时 Mock 处理 | 在 Mock 数据中构造 ReviewDecisionDTO |
| 是否阻断 | yes |
| 期望解决版本 | v0.2 |

### GAP-003: Event 合同需扩展

| 字段 | 说明 |
|------|------|
| gap_id | GAP-003 |
| 当前合同 | `core/schemas/event.py` — GovernanceEvent 只有 open/processing/completed/closed 状态 |
| 前端需求 | under_review / confirmed / rejected / needs_more_evidence 状态；版本历史；Candidate 引用 |
| 缺失字段 | status 枚举值扩展；versions 数组；candidate_ref |
| 建议负责人 | Agent C |
| 临时 Mock 处理 | 在 Mock 中扩展 status 枚举 |
| 是否阻断 | yes (前端需要 under_review 状态) |
| 期望解决版本 | v0.2 |

### GAP-004: Replay 合同缺失

| 字段 | 说明 |
|------|------|
| gap_id | GAP-004 |
| 当前合同 | 无 Replay 相关 Schema |
| 前端需求 | ReplayEntry: operation_type, timestamp, actor, before_state, after_state, details |
| 缺失字段 | 完整合同缺失 |
| 建议负责人 | Agent C |
| 临时 Mock 处理 | 在 Mock 数据中构造 ReplayEntryDTO |
| 是否阻断 | no (V0 用 Mock 数据演示) |
| 期望解决版本 | v0.2 |

### GAP-005: RunManifest 合同缺失

| 字段 | 说明 |
|------|------|
| gap_id | GAP-005 |
| 当前合同 | 无 RunManifest 相关 Schema |
| 前端需求 | run_id, task_id, task_spec_ref, git_commit, git_branch, git_dirty, started_at, finished_at, execution_status, input_assets, metadata_sources, config_hash, output_artifacts, artifact_sha256, failure_stage, candidate_counts |
| 缺失字段 | 完整合同缺失 |
| 建议负责人 | Agent B |
| 临时 Mock 处理 | 在 Mock 数据中构造 RunManifestDTO |
| 是否阻断 | no (V0 用 Mock 数据演示) |
| 期望解决版本 | v0.2 |

### GAP-006: Evidence 合同需扩展

| 字段 | 说明 |
|------|------|
| gap_id | GAP-006 |
| 当前合同 | `core/schemas/evidence.py` — EvidenceItem 缺少 source_modality, stance, provenance, quality_summary, unavailable_reason |
| 前端需求 | source_modality, stance, provenance, quality_summary, unavailable_reason |
| 缺失字段 | source_modality, stance, provenance, unavailable_reason |
| 建议负责人 | Agent A |
| 临时 Mock 处理 | 在 Mock 中扩展字段 |
| 是否阻断 | no |
| 期望解决版本 | v0.2 |
