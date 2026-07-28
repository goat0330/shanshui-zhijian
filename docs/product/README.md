# 山水智鉴 — 产品方案文档

> 版本: v0.2 (方案审批版)
> 更新: 2026-07-28

---

## 文档清单

| # | 文档 | 内容 |
|---|------|------|
| 1 | [DASHBOARD_PRD.md](./DASHBOARD_PRD.md) | 领导驾驶舱产品需求：定位、信息架构、用户流程、验收标准 |
| 2 | [DASHBOARD_LAYOUT.md](./DASHBOARD_LAYOUT.md) | 两套 16:9 布局方案对比（方案 A / 方案 B） |
| 3 | [COMPONENT_TREE.md](./COMPONENT_TREE.md) | 完整 React 组件层次、共享组件依赖 |
| 4 | [DATA_FIELDS.md](./DATA_FIELDS.md) | 各组件绑定的 API 数据字段、类型定义、请求时序 |
| 5 | [DATA_RELATIONSHIP.md](./DATA_RELATIONSHIP.md) | 五维关系图、数据一致性校验、跳转矩阵 |

---

## 决策路径

```
用户审批
  │
  ├── 审批通过
  │     │
  │     ├── 选定布局方案（A 或 B）
  │     │
  │     └── Agent D 开始实现
  │           ├── Mock 数据 (已有)
  │           ├── 组件实现 (已有)
  │           └── 页面集成 (已有)
  │
  └── 需要修改
        └── 按用户反馈调整方案
```

---

## 与现有实现的对应关系

| 文档章节 | 现有实现状态 |
|----------|-------------|
| 信息架构 / 路由 | ✅ 已实现 (AppLayout + 5 路由) |
| 态势总览 SituationCards | ✅ 已实现 (6 卡片) |
| 空间分布 SpatialDistribution | ✅ 已实现 (CSS 柱状图) |
| 时间趋势 TrendChart | ✅ 已实现 (SVG 折线图) |
| 研判漏斗 ReviewFunnel | ✅ 已实现 (4 阶段) |
| 典型案例 TypicalCases | ✅ 已实现 (5 卡片) |
| Mock 数据 | ✅ 已实现 (dashboard.ts + MSW handlers) |
| 布局方案 | 📋 本文档定义，等待审批 |
| 地图嵌入 (方案 B) | ⏳ 待审批后实现 |
| 案例跳转工作台 | ⏳ 待审批后实现 |
