# 山水智鉴 V0 — 信息架构

> 版本: v0.1
> 更新: 2026-07-26

---

## 1. 导航架构

```
山水智鉴 V0
├── 研判工作台 (/)
│   ├── Candidate 队列 (左侧栏)
│   ├── 地图与影像 (中央)
│   │   ├── 地图容器
│   │   ├── 图层面板
│   │   ├── 对比面板
│   │   ├── 图例
│   │   └── 状态栏
│   └── 详情与操作 (右侧栏)
│       ├── Candidate 详情
│       ├── Evidence 面板
│       └── Review 表单
├── 事件中心 (/events)
│   ├── Event 列表 (筛选)
│   └── Event 详情
│       ├── 版本历史
│       ├── Candidate 来源
│       ├── Evidence Bundle
│       ├── Review Decision
│       └── 地图定位
├── 运行记录 (/runs)
│   ├── Run 列表 (筛选)
│   └── Run 详情
│       ├── 参数与配置
│       ├── Candidate→Observation→Asset→Artifact
│       └── 产物校验
└── 系统设置 (/settings)
    ├── API 模式切换 (Mock / Real)
    └── 显示设置
```

---

## 2. 对象模型

```
RunManifest
  ├── run_id
  ├── started_at / finished_at
  ├── execution_status
  ├── git_commit / git_branch / git_dirty
  ├── task_spec_ref
  ├── metadata_sources
  ├── config_hash
  ├── input_assets
  ├── output_artifacts
  ├── artifact_sha256
  ├── failure_stage
  └── candidate_counts

Candidate (来自 Agent A)
  ├── candidate_id
  ├── candidate_track_id
  ├── schema_version
  ├── change_type
  ├── persistence_status (persistent / transient / uncertain)
  ├── temporal_extent
  ├── occurrence_count
  ├── persistence_ratio
  ├── representative_geometry
  ├── union_geometry
  ├── score / score_type / score_components
  ├── quality_summary
  ├── observation_refs
  ├── source_asset_refs
  ├── run_manifest_ref
  └── rule_version

EvidenceBundle
  ├── evidence_id
  ├── evidence_type
  ├── source_modality
  ├── source_asset_ref
  ├── derived_asset_ref
  ├── captured_at
  ├── stance (supporting / contradicting / inconclusive)
  ├── quality_summary
  ├── provenance
  └── unavailable_reason

ReviewDecision
  ├── review_id
  ├── candidate_id
  ├── action (confirm / reject / reclassify / needs_more_evidence)
  ├── category (reclassified category)
  ├── comment
  ├── evidence_refs
  ├── actor_ref
  ├── base_version
  └── reviewed_at

Event (来自 Agent C)
  ├── event_id
  ├── candidate_id
  ├── event_type
  ├── status (under_review / confirmed / rejected / needs_more_evidence)
  ├── title
  ├── versions[]
  └── timeline[]

Artifact
  ├── artifact_id
  ├── run_id
  ├── asset_type
  ├── file_path
  ├── sha256
  ├── size_bytes
  ├── cog_url
  ├── tilejson_url
  └── metadata
```

---

## 3. 状态流转

### Review 状态
```
Candidate (pending)
  ├→ confirm  → Event (confirmed)
  ├→ reject   → Event (rejected)
  ├→ reclassify → Event (reclassified with new category)
  └→ needs_more_evidence → Event (under_review + flag)
```

### Event 状态
```
under_review
  ├→ confirmed
  ├→ rejected
  └→ needs_more_evidence (追加证据后回到 under_review)
```

---

## 4. 数据关系

```
Run → Candidate (1:N)
Candidate → EvidenceBundle (1:1)
Candidate → ReviewDecision (1:N, versioned)
Candidate → Event (1:1 after confirm)
Event → ReplayEntry (1:N)
Run → Artifact (1:N)
Candidate → Artifact (N:N through observation_refs)
```
