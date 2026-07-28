# 山水智鉴 — Dashboard 数据字段绑定

> 版本: v0.2
> 更新: 2026-07-28

---

## 1. GET /api/v2/dashboard/summary

### 响应结构

```typescript
interface DashboardSummary {
  total_candidates: number;          // 异常候选总数
  persistent_count: number;          // 持久性异常
  transient_count: number;           // 瞬态异常
  uncertain_count: number;           // 不确定异常
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

### 绑定到 SituationCards

| 卡片 | 字段 | 类型 | 示例 | 颜色 |
|------|------|------|------|------|
| 异常候选 | `total_candidates` | number | 36 | 蓝色 |
| 持久性异常 | `persistent_count` | number | 12 | 橙色 |
| 瞬态异常 | `transient_count` | number | 20 | 灰色 |
| 待研判事件 | `under_review` | number | 1 | 红色 |
| 已确认事件 | `confirmed` | number | 1 | 绿色 |
| 监测范围 | `monitored_area_km2` | number | 156.42 | 青色 |

---

## 2. GET /api/v2/dashboard/change-types

### 响应结构

```typescript
interface ChangeTypeDistribution {
  change_type: string;               // 变化类型标识
  label: string;                     // 中文显示名
  count: number;                     // 数量
  color: string;                     // 颜色 (#hex)
}
```

### 绑定到 SpatialDistribution

| 柱状条 | 字段 | 示例值 |
|--------|------|--------|
| 标签 | `label` | "水面扩展" |
| 数量 | `count` | 8 |
| 颜色 | `color` | "#2196F3" |
| 柱宽 | `count / max(count) * 100%` | 100% |

### 典型数据

| change_type | label | 典型数量 |
|-------------|-------|----------|
| water_extent_increase | 水面扩展 | 8 |
| water_extent_decrease | 水面缩减 | 6 |
| turbidity_anomaly | 浑浊度异常 | 5 |
| algae_bloom | 藻类爆发 | 4 |
| bank_collapse | 岸线崩塌 | 3 |
| suspected_discharge | 疑似排污 | 3 |
| sediment_anomaly | 沉积异常 | 4 |
| vegetation_change | 植被变化 | 3 |

---

## 3. GET /api/v2/dashboard/trend

### 响应结构

```typescript
interface MonthlyTrend {
  month: string;                     // "2026-03"
  label: string;                     // "3月"
  candidate_count: number;           // 当月候选量
  confirmed_count: number;           // 当月确认量
}
```

### 绑定到 TrendChart

| 图元素 | 字段 | 说明 |
|--------|------|------|
| X 轴 | `label` | 月份标签 |
| Y 轴 | 动态范围 | 数量刻度 |
| 候选折线 | `candidate_count` | 蓝色连线 |
| 确认折线 | `confirmed_count` | 绿色连线 |
| Tooltip | `month + 双值` | 悬浮显示 |

### 典型数据

| 月份 | candidate_count | confirmed_count |
|------|----------------:|----------------:|
| 3月 | 10 | 0 |
| 4月 | 8 | 1 |
| 5月 | 12 | 0 |
| 6月 | 6 | 0 |

---

## 4. GET /api/v2/dashboard/funnel

### 响应结构

```typescript
interface ReviewFunnelStage {
  stage: string;                     // 阶段标识
  label: string;                     // 中文阶段名
  count: number;                     // 本阶段数量
  percentage?: number;               // 转化率 (可选)
}
```

### 绑定到 ReviewFunnel

| 阶段 | 字段 | 典型值 |
|------|------|--------|
| 总候选 | `count[0]` | 36 |
| 进入研判 (under_review) | `count[1]` | 3 |
| 已确认 (confirmed) | `count[2]` | 1 |
| 已处理 (action_taken) | `count[3]` | 1 |

转化率计算：`stage[i].count / stage[0].count * 100`

---

## 5. GET /api/v2/dashboard/typical-cases

### 响应结构

```typescript
interface TypicalCase {
  case_id: string;                   // 案例 ID
  title: string;                     // 案例标题
  status: 'confirmed' | 'rejected' | 'under_review' | 'needs_more_evidence';
  change_type: string;               // 变化类型
  change_type_label: string;         // 中文变化类型
  severity: string;                  // 严重程度描述
  area_m2: number;                   // 面积 (m²)
  detected_at: string;               // 检测时间 (ISO)
  summary: string;                   // 案例摘要
  candidate_id: string;              // 关联 Candidate ID (跳转用)
  event_id?: string;                 // 关联 Event ID (跳转用)
}
```

### 绑定到 CaseCard

| 卡片元素 | 字段 | 示例 |
|----------|------|------|
| 标题 | `title` | "长江支流 A 段水面异常扩展" |
| 状态标签 | `status` | confirmed → 绿色 / under_review → 橙色 |
| 变化类型 | `change_type_label` | "水面扩展" |
| 面积 | `area_m2` | 53,247 m² |
| 日期 | `detected_at` | "2026-04-12" |
| 摘要 | `summary` | "该区域在4月12日的SAR影像中..." |
| 跳转 | `candidate_id` | "CAND-0001" |

---

## 6. 数据流总图

```
Browser (Dashboard Page)
  │
  ├── useEffect on mount (no polling)
  │     │
  │     ├── fetchDashboardSummary()         → SituationCards
  │     ├── fetchDashboardChangeTypes()     → SpatialDistribution
  │     ├── fetchDashboardTrend()           → TrendChart
  │     ├── fetchDashboardFunnel()          → ReviewFunnel
  │     └── fetchDashboardTypicalCases()    → TypicalCases
  │
  ├── Parallel loading (Promise.all)
  │     └── 全部 5 个请求同时发出
  │
  ├── Each fetch:
  │     ├── pending    → <Loading />
  │     ├── success    → render data
  │     └── error      → <ErrorState onRetry={refetch} />
  │
  └── 空数组/0 值     → <EmptyState />
```

### TanStack Query 配置

| Query Key | TTL | Stale Time | 重试 |
|-----------|-----|------------|------|
| `['dashboard-summary']` | 5min | 30s | 3 |
| `['dashboard-change-types']` | 5min | 30s | 3 |
| `['dashboard-trend']` | 5min | 30s | 3 |
| `['dashboard-funnel']` | 5min | 30s | 3 |
| `['dashboard-typical-cases']` | 5min | 30s | 3 |

### 请求时序

```
t=0  ── 页面挂载
       ├── 5 个请求并行发出
       ├── 同时显示 5 个 <Loading />
       ├── 100-300ms 后 (Mock 延迟)
       ├── 逐个返回 → 逐个渲染
       └── 全部就绪 → Dashboard 完整显示
t=+n ── 用户点击案例 → 跳转工作台
t=+n ── 用户返回驾驶舱 → TanStack Query 缓存命中 → 瞬时渲染
```
