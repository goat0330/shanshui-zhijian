# 山水智鉴 V0 — UI 状态模型

> 版本: v0.1
> 更新: 2026-07-26

---

## 1. 状态分层

### URL 持久化状态 (页面刷新后恢复)
```
candidate_id    → 当前选中的 Candidate
run_id          → 当前筛选的 Run
aoi_id          → 当前筛选的 AOI
bbox            → 地图视口
persistence_status → 持久性筛选
change_type     → 变化类型筛选
include_transient  → 是否显示 transient
sort            → 排序方式
```

### Zustand 运行时状态 (不持久化)
```
selectedCandidateId
map viewport (zoom, center, bounds)
layer visibility (Map<string, boolean>)
layer opacity (Map<string, number>)
compare mode (none | opacity | split)
active panels (left | right visibility)
timeline position
```

### TanStack Query 服务端状态 (缓存)
```
candidates list & detail
evidence
events
replay
runs
artifacts
```

---

## 2. Zustand Store 定义

```typescript
interface WorkbenchStore {
  // Selection
  selectedCandidateId: string | null;
  setSelectedCandidateId: (id: string | null) => void;

  // Map
  viewport: MapViewport;
  setViewport: (viewport: MapViewport) => void;
  compareMode: 'none' | 'opacity' | 'split';
  setCompareMode: (mode: 'none' | 'opacity' | 'split') => void;

  // Layers
  layerVisibility: Record<string, boolean>;
  setLayerVisibility: (id: string, visible: boolean) => void;
  layerOpacity: Record<string, number>;
  setLayerOpacity: (id: string, opacity: number) => void;

  // Panels
  leftPanelOpen: boolean;
  rightPanelOpen: boolean;
  toggleLeftPanel: () => void;
  toggleRightPanel: () => void;
}
```

---

## 3. 数据获取策略 (TanStack Query)

| Query Key | TTL | Stale Time | Retry |
|-----------|-----|------------|-------|
| ['candidates', filters] | 5 min | 30s | 3 |
| ['candidate', id] | 5 min | 30s | 3 |
| ['evidence', candidateId] | 5 min | 30s | 3 |
| ['events', filters] | 5 min | 30s | 3 |
| ['event', id] | 5 min | 30s | 3 |
| ['runs', filters] | 5 min | 30s | 3 |
| ['run', id] | 5 min | 30s | 3 |
| ['replay', eventId] | 5 min | 30s | 3 |
| ['artifacts', id] | 5 min | 30s | 3 |

---

## 4. URL 搜索参数

```typescript
interface URLSearchParams {
  candidate_id?: string;
  run_id?: string;
  aoi_id?: string;
  bbox?: string;        // "lng,lat,zoom"
  persistence_status?: 'persistent' | 'uncertain' | 'all';
  change_type?: string;
  include_transient?: '0' | '1';
  sort?: 'score' | 'area' | 'occurrence_count' | 'temporal_extent';
}
```
