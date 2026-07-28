# 山水智鉴 — React 组件树 (B2 布局)

> 版本: v0.3 (B2 定稿)
> 更新: 2026-07-28

---

## 1. 完整组件层次

```
<App>
  └── <QueryClientProvider>
        └── <RouterProvider router={router}>
              └── <AppLayout>                              # 共享布局 + 导航
                    │
                    ├── <DashboardPage>                     # /dashboard — B2 布局
                    │     │
                    │     ├── <DashboardHeader>
                    │     │     ├── Title "研判驾驶舱"
                    │     │     └── <DataSourceBadge mode="MOCK" />  # 三态: MOCK/FIXTURE/REAL
                    │     │
                    │     ├── <SituationCards>              # ① KPI 行 — 6 卡片单行
                    │     │     └── <SituationCard> × 6
                    │     │           ├── label / value / unit
                    │     │           └── color (顶部边框色)
                    │     │
                    │     ├── [三栏 B2] left/center/right
                    │     │     │
                    │     │     ├── [left]                   # 左栏 280px
                    │     │     │     ├── <TrendChart>       # ② 月度趋势 SVG
                    │     │     │     └── <ReviewFunnel>     # ③ 研判链漏斗
                    │     │     │           候选产生→证据就绪→已完成研判→已生成事件版本
                    │     │     │
                    │     │     ├── [center]                 # 中间 flex 1
                    │     │     │     └── <GovernanceMap>    # ④ 地图主视觉
                    │     │     │           readonly mode
                    │     │     │           Candidate/Event GeoJSON 图层
                    │     │     │
                    │     │     └── [right]                  # 右栏 300px
                    │     │           ├── <SpatialDistribution>  # ⑤ 类型分布
                    │     │           └── <TypicalCases>     # ⑥ 典型案例 (无 severity)
                    │     │
                    │     └── (no page scroll — 1920×1080 全屏)
                    │
                    ├── <WorkbenchPage>                     # /workbench — 路由统一
                    ├── <EventCenterPage>                   # /events
                    ├── <RunCenterPage>                     # /runs
                    └── <SettingsPage>                      # /settings
```

## 2. API 数据来源

| 组件 | 数据源 | Query Key |
|------|--------|-----------|
| SituationCards | snapshot.summary | dashboard-snapshot |
| TrendChart | snapshot.trend | dashboard-snapshot |
| ReviewFunnel | snapshot.funnel | dashboard-snapshot |
| SpatialDistribution | snapshot.change_types | dashboard-snapshot |
| TypicalCases | snapshot.typical_cases | dashboard-snapshot |
| GovernanceMap | /map/candidates.geojson + /map/events.geojson | (内部) |

## 3. 共享组件

| 组件 | 使用场景 | Dashboard 差异 |
|------|----------|---------------|
| GovernanceMap | 中间主视觉 | readonly, Candidate/Event 图层 |
| LayerRegistry | 间接使用 | 仅 GeoJSON 图层 |
| Loading | 加载态 | 无差异 |
| ErrorState | 错误态 | 无差异 |
| EmptyState | 空数据 | 无差异 |
