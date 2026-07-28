# 山水智鉴 — 地图·指标·趋势·漏斗·案例 关系图

> 版本: v0.2
> 更新: 2026-07-28

---

## 1. 核心数据关系

```
                ┌──────────────────────────────────┐
                │        RunManifest (运行)         │
                │   run_id / status / candidates    │
                └────────────┬─────────────────────┘
                             │ 1:N
                             ▼
                ┌──────────────────────────────────┐
                │         Candidate (候选)          │
                │   candidate_id / change_type      │
                │   score / persistence_status      │
                │   geometry / area_m2              │
                └────┬──────────┬──────────────────┘
                     │ 1:1      │ 1:N
                     ▼          ▼
          ┌──────────────────┐  ┌──────────────────────┐
          │  EvidenceBundle  │  │   ReviewDecision      │
          │  stance / type   │  │   action / category   │
          └──────────────────┘  └──────────┬───────────┘
                                           │ 1:1 (after review)
                                           ▼
                               ┌──────────────────────┐
                               │   Event (事件)        │
                               │   status / versions   │
                               └──────────────────────┘
```

---

## 2. Dashboard 组件间的数据依赖

### 2.1 数据维度的交叉关系

```
                  Dashboard 页面
                       │
         ┌─────────────┼─────────────┬──────────────┬──────────────┐
         ▼             ▼             ▼              ▼              ▼
   ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐
   │ Situation │ │ Spatial    │ │  Trend   │ │  Review    │ │  Typical     │
   │  Cards    │ │ Distribution│ │  Chart   │ │  Funnel    │ │  Cases       │
   └────┬─────┘ └──────┬─────┘ └────┬─────┘ └─────┬──────┘ └──────┬───────┘
        │              │            │             │               │
        │              │            │             │               │
        ▼              ▼            ▼             ▼               ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                        底层事实 (Candidate/Event)                    │
  └─────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据交叉引用

| 数据对 | 关系 | 一致性校验 |
|--------|------|-----------|
| 态势卡 total_candidates ↔ 漏斗总候选 | 必须相等 | `total === funnel[0].count` |
| 态势卡 confirmed ↔ 漏斗 confirmed | 必须相等 | `confirmed === funnel[2].count` |
| 态势卡 under_review ↔ 漏斗 under_review | 必须相等 | `under_review === funnel[1].count` |
| 态势卡 persistent + transient + uncertain ↔ total | 求和校验 | `p + t + u === total` |
| 趋势图月度数据 ↔ 候选数据 | 月度之和应为总数 | `Σ monthly.candidate === total` |
| 典型案例 ↔ 已确认事件/待研判事件 | 案例覆盖可用状态 | `cases.length ≤ total` |
| 空间分布各类型数量之和 | 应等于 total_candidates | `Σ change_type.count === total` |

---

## 3. Dashboard 与 Workbench 的关系

### 3.1 数据同源

```
              SQLite / PostGIS
                    │
                    ▼
         Workbench API (apps/workbench_api/)
          ├── /api/v2/candidates/*       ← 共享
          ├── /api/v2/events/*           ← 共享
          ├── /api/v2/runs/*             ← 共享
          ├── /api/v2/evidence/*         ← 仅工作台
          ├── /api/v2/review/*           ← 仅工作台
          ├── /api/v2/map/*              ← 共享
          └── /api/v2/dashboard/*        ← 仅驾驶舱 (聚合查询)
                    │
         ┌──────────┴──────────┐
         ▼                     ▼
   Dashboard (只读)      Workbench (读写)
   聚合/统计视图         单条操作视图
```

### 3.2 交互跳转矩阵

```
用户操作                   来源           目标           参数传递
─────────────────────    ──────         ──────         ──────
点击典型案例卡片           Dashboard      Workbench      ?candidate_id=CAND-0001
点击空间分布某类型         Dashboard      Workbench      ?change_type=water_extent_increase
点击漏斗某阶段            Dashboard      Workbench      ?status=under_review
研判完成返回               Workbench      Dashboard      刷新
```

---

## 4. 地图·指标·趋势·漏斗·案例 五维关联图

### 4.1 方案 A（无地图）

```
┌──── 指标 ────┐
│ SituationCards│
│ 6 个关键数字  │
└──────┬───────┘
       │ 总量约束
       ▼
┌──── 漏斗 ────┐         ┌──── 趋势 ────┐         ┌──── 分布 ────┐
│ ReviewFunnel │ ◄──────► │ TrendChart  │         │ SpatialDist │
│ 4 阶段转化   │ 时间     │ 月度走势     │         │ 类型占比     │
│             │ 切片      │ (候选+确认)  │         │ (8 种类型)   │
└──────┬───────┘         └─────────────┘         └──────┬───────┘
       │ 状态过滤                                        │ 类型过滤
       ▼                                                ▼
┌──── 案例 ────┐                                   ┌────────────┐
│ TypicalCases │ ◄──────────────────────────────────│ Dashboard  │
│ 5 张案例卡片 │   点击跳转                          │ 工作台跳转 │
└──────────────┘                                   └────────────┘
```

### 4.2 方案 B（有地图）

```
┌──── 指标 ────┐
│ SituationCards│
│ 6 个关键数字  │
└──────┬───────┘
       │ 总量约束
       ▼
┌──── 地图 ────┐
│ GovernanceMap│
│ Candidate/   │
│ Event 热点    │
│ (readonly)   │
└──────┬───────┘
       │ 空间维度
       ▼                           ┌─────────────────────┐
┌──── 漏斗 ────┐    ┌──── 趋势 ────┐│    ┌──── 分布 ────┐  │
│ ReviewFunnel │    │ TrendChart  ││    │ SpatialDist │  │
│ 4 阶段转化   │◄──►│ 月度走势     ││    │ 类型占比     │  │
│             │ 协同 │ (候选+确认)  ││    │ (8 种类型)   │  │
└──────┬───────┘    └─────────────┘│    └──────┬───────┘  │
       │ 状态过滤                  │           │ 类型过滤  │
       ▼                           │           ▼          │
┌──── 案例 ────┐                   │  ┌────────────┐     │
│ TypicalCases │ ◄─────────────────┼──│ Dashboard  │     │
│ 5 张卡片     │   点击跳转         │  │ 工作台跳转 │     │
└──────────────┘                   │  └────────────┘     │
                                   └─────────────────────┘
```

### 4.3 数据一致性规则

```
DashboardSummary.total_candidates
  = Σ SpatialDistribution[].count                            // 类型分布总和
  = ReviewFunnel[0].count                                     // 漏斗首阶段
  = Σ TrendChart[].candidate_count                            // 月度候选之和
  = persistent + transient + uncertain                        // 态势卡子项之和

DashboardSummary.confirmed
  = ReviewFunnel[2].count                                     // 漏斗"已确认"阶段
  = TypicalCases.filter(status='confirmed').length             // 已确认案例数
```

---

## 5. 数据流向时序图

```
Page Mount
    │
    ▼
┌─────────────────────┐
│ 并行发起 5 个请求    │
│ Promise.allSettled   │
└──────┬──────────────┘
       │
       ├── success ────► 渲染组件
       │                    │
       │                    ├── SituationCards: 6 数字
       │                    ├── SpatialDistribution: 8 柱状条
       │                    ├── TrendChart: 4-6 月折线
       │                    ├── ReviewFunnel: 4 阶段
       │                    └── TypicalCases: 5 卡片
       │
       └── error ──────► 显示 ErrorState + Retry
                              │
                              └── retry ──► 重新请求
                              └── ignore  → 保留空区域

Page Refresh / Navigate Away → 缓存保留 5min → 返回时瞬时渲染
```

---

## 6. 数据血缘

```
Source System       →  API Layer          →  Dashboard
─────────────────────────────────────────────────────────
Candidate Table     →  /candidates        →  SituationCards.total_candidates
                    →  /dashboard/summary  →  SituationCards (所有)
                    →  /dashboard/change-types → SpatialDistribution
                    →  /dashboard/trend    →  TrendChart
Event Table         →  /dashboard/summary  →  confirmed/under_review
                    →  /dashboard/funnel   →  ReviewFunnel
                    →  /dashboard/typical-cases → TypicalCases
                    →  /events             →  (典型) 跳转后事件详情
Map GeoJSON         →  /map/candidates.geojson → 地图热点
                    →  /map/events.geojson      → 地图热点
```
