# 山水智鉴 — Dashboard 数据字段绑定

> 版本: v0.3 (B2 定稿)
> 更新: 2026-07-28

---

## 1. GET /api/v2/dashboard/snapshot（单一收口端点）

### 响应结构

```typescript
interface DashboardSnapshot {
  summary: DashboardSummary;
  change_types: ChangeTypeDistribution[];
  trend: MonthlyTrend[];
  funnel: ReviewFunnelStage[];
  typical_cases: TypicalCase[];
}

interface DashboardSummary {
  total_candidates: number;          // 异常候选总数
  persistent_count: number;          // 持久性异常
  uncertain_count: number;           // 不确定异常
  transient_count: number;           // 瞬态异常
  under_review: number;              // 待研判事件
  confirmed: number;                 // 已确认事件
  rejected: number;                  // 已驳回事件
  needs_evidence: number;            // 需补充证据
  total_runs: number;                // 总运行次数
  completed_runs: number;            // 成功运行
  failed_runs: number;               // 失败运行
  last_run_date: string;             // 最近运行时间 (ISO)
  monitored_area_km2: number;        // 监测范围 (km²)
}
```

---

## 2. 绑定到 SituationCards（6 KPI）

| 卡片 | 字段 | 颜色 |
|------|------|------|
| 异常候选 | `summary.total_candidates` | primary |
| 持久性异常 | `summary.persistent_count` | candidate-persistent |
| 瞬态异常 | `summary.transient_count` | candidate-transient |
| 待研判事件 | `summary.under_review` | event-review |
| 已确认事件 | `summary.confirmed` | event-confirmed |
| 监测范围 | `summary.monitored_area_km2` | info |

---

## 3. 绑定到 ChangeTypeDistribution

| 柱状条 | 字段 | 示例 |
|--------|------|------|
| 标签 | `label` | "水面扩展" |
| 数量 | `count` | 10 |
| 颜色 | `color` | "#1565c0" |

---

## 4. 绑定到 MonthlyTrend

| 图元素 | 字段 | 说明 |
|--------|------|------|
| X 轴 | `label` | "3月" |
| 候选柱 | `candidates` | 蓝色柱 |
| 确认标记 | `confirmed` | 绿色圆点 |

---

## 5. 绑定到 ReviewFunnelStage（4 阶段）

| 阶段 | stage 标识 | 字段 | 说明 |
|------|-----------|------|------|
| 候选产生 | `candidates_created` | `count` | 总候选数 |
| 证据就绪 | `evidence_ready` | `count` | 已完成证据收集 |
| 已完成研判 | `reviewed` | `count` | 已给出明确决策 |
| 已生成事件版本 | `event_versioned` | `count` | 已生成正式事件 |

---

## 6. 绑定到 TypicalCase

| 卡片元素 | 字段 | 示例 |
|----------|------|------|
| 标题 | `title` | "长江支流 A 段水面异常扩展" |
| 状态标签 | `status` | "confirmed" |
| 变化类型 | `change_type_label` | "水面扩展" |
| 面积 | `area_m2` | 45200 |
| 日期 | `detected_at` | "2026-06-01" |
| 摘要 | `summary` | "Sentinel-2 多时相分析显示..." |
| 跳转 | 无 severity 字段 | — |

---

## 7. 数据流总图

```
DashboardPage mount
  │
  ├── fetchDashboardSnapshot()  → DashboardSnapshot
  │     ├── .summary            → SituationCards
  │     ├── .change_types       → SpatialDistribution
  │     ├── .trend              → TrendChart
  │     ├── .funnel             → ReviewFunnel
  │     └── .typical_cases      → TypicalCases
  │
  └── GovernanceMap (internal)
        ├── fetchCandidateGeoJSON()
        └── fetchEventGeoJSON()
```

### TanStack Query 配置

| Query Key | TTL | Stale Time |
|-----------|-----|------------|
| `['dashboard-snapshot']` | 5min | 30s |
