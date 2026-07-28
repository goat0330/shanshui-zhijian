# 山水智鉴 — React 组件树

> 版本: v0.2
> 更新: 2026-07-28

---

## 1. 完整组件层次

```
<App>
  └── <QueryClientProvider>
        └── <RouterProvider router={router}>
              └── <AppLayout>                                    # 共享布局 + 导航
                    │
                    ├── <DashboardPage>                          # /dashboard
                    │     ├── <DashboardHeader>
                    │     │     ├── Title "研判驾驶舱"
                    │     │     └── MockBadge (脉冲动画)
                    │     │
                    │     ├── <SituationCards>                   # ① 态势总览
                    │     │     └── <SituationCard> × 6
                    │     │           ├── label (中文标签)
                    │     │           ├── value (number)
                    │     │           ├── color (顶部边框色)
                    │     │           └── subtitle (单位/说明)
                    │     │
                    │     ├── <SpatialDistribution>              # ② 空间分布
                    │     │     ├── Title "变化类型分布"
                    │     │     ├── <DistributionBar> × N
                    │     │     │     ├── label (变化类型)
                    │     │     │     ├── count (数量)
                    │     │     │     ├── bar (宽度 = count/max)
                    │     │     │     └── color (类型色)
                    │     │     └── (点击跳转工作台)
                    │     │
                    │     ├── <TrendChart>                       # ② 时间趋势
                    │     │     ├── Title "月度趋势"
                    │     │     ├── <svg> 折线/柱状图
                    │     │     │     ├── X轴 (月份)
                    │     │     │     ├── Y轴 (数量)
                    │     │     │     ├── candidate 折线
                    │     │     │     └── confirmed 折线
                    │     │     └── Legend (候选量 / 确认量)
                    │     │
                    │     ├── <ReviewFunnel>                     # ③ 研判漏斗
                    │     │     ├── Title "研判漏斗"
                    │     │     ├── <FunnelStage> × 4
                    │     │     │     ├── label (阶段名)
                    │     │     │     ├── count (数量)
                    │     │     │     ├── barWidth (占比)
                    │     │     │     └── percentage (转化率)
                    │     │     └── (点击跳转工作台)
                    │     │
                    │     └── <TypicalCases>                     # ④ 典型案例
                    │           ├── Title "典型案例"
                    │           ├── <CaseCard> × N
                    │           │     ├── title (事件标题)
                    │           │     ├── status (状态标签)
                    │           │     ├── changeType (变化类型)
                    │           │     ├── area (面积)
                    │           │     ├── date (发生日期)
                    │           │     ├── summary (简述)
                    │           │     └── onClick → 跳转工作台
                    │           └── (水平滚动)
                    │
                    ├── <WorkbenchPage>                          # 已实现
                    ├── <EventCenterPage>                        # 已实现
                    ├── <RunCenterPage>                          # 已实现
                    └── <SettingsPage>                           # 已实现
```

---

## 2. 共享组件依赖

### 复用自研判工作台的组件

| 组件 | 复用方式 | 驾驶舱中差异 |
|------|----------|-------------|
| `GovernanceMap` | **方案 B 使用** | readonly 模式：禁选、禁对比、禁图层编辑 |
| `LayerRegistry` | 间接使用 | 仅加载 Candidate + Event 图层 |
| `Loading` | 直接使用 | 无差异 |
| `ErrorState` | 直接使用 | 无差异 |
| `EmptyState` | 直接使用 | 无差异 |
| `WorkbenchLayer` 类型 | 类型引用 | 仅使用 GeoJSON 子集 |
| `CandidateDTO` | 类型引用 | 典型案例的数据来源 |
| `EventDTO` | 类型引用 | 典型案例的数据来源 |
| Design Tokens | CSS 变量引用 | 无差异 |

### 驾驶舱专有组件（新增）

| 组件 | 文件路径 | 依赖 |
|------|----------|------|
| `SituationCards` | features/dashboard/components/SituationCards.tsx | DashboardSummary API |
| `SituationCard` | 同文件内联 | — |
| `SpatialDistribution` | features/dashboard/components/SpatialDistribution.tsx | ChangeTypeDistribution API |
| `DistributionBar` | 同文件内联 | — |
| `TrendChart` | features/dashboard/components/TrendChart.tsx | MonthlyTrend API |
| `ReviewFunnel` | features/dashboard/components/ReviewFunnel.tsx | ReviewFunnelStage API |
| `FunnelStage` | 同文件内联 | — |
| `TypicalCases` | features/dashboard/components/TypicalCases.tsx | TypicalCase API |
| `CaseCard` | 同文件内联 | — |

---

## 3. 状态管理归属

```
TanStack Query (服务端缓存)
  ├── dashboardSummary     → SituationCards
  ├── dashboardChangeTypes → SpatialDistribution
  ├── dashboardTrend       → TrendChart
  ├── dashboardFunnel      → ReviewFunnel
  └── dashboardTypicalCases → TypicalCases

Zustand (UI 状态)
  └── (Dashboard 不需要额外 UI 状态，全用组件本地 state)

URL 持久化
  └── (Dashboard 不需要 URL 恢复)
```
