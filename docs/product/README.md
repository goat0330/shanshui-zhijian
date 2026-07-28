# 山水智鉴 — 产品方案文档

> 版本: v0.3 (B2 定稿 / 骨架实现中)
> 更新: 2026-07-28

---

## 文档清单

| # | 文档 | 内容 |
|---|------|------|
| 1 | [DASHBOARD_PRD.md](./DASHBOARD_PRD.md) | 驾驶舱 PRD — B2 布局、路由统一、snapshot API、DataSourceBadge |
| 2 | [DASHBOARD_LAYOUT.md](./DASHBOARD_LAYOUT.md) | B2 16:9 单屏布局 — 左(趋势+漏斗)/中(地图)/右(分布+案例) |
| 3 | [COMPONENT_TREE.md](./COMPONENT_TREE.md) | B2 组件树、数据来源映射 |
| 4 | [DATA_FIELDS.md](./DATA_FIELDS.md) | 收口 snapshot API 字段绑定 |
| 5 | [DATA_RELATIONSHIP.md](./DATA_RELATIONSHIP.md) | B2 五维关系图、一致性校验 |

---

## 实现状态

| 组件 | 状态 | 备注 |
|------|------|------|
| 路由 /workbench + /dashboard | ✅ 骨架已实现 | `/` → `/workbench` redirect |
| DataSourceBadge 三态 | ✅ 骨架已实现 | MOCK / FIXTURE / REAL |
| B2 三栏布局 | ✅ 骨架已实现 | left 280px / center flex / right 300px |
| SituationCards 6 KPI | ✅ 已有实现 | 已适配 snapshot |
| TrendChart | ✅ 已有实现 | 已适配紧凑 SVG |
| ReviewFunnel | ✅ 已有实现 | 新 4 阶段 |
| SpatialDistribution | ✅ 已有实现 | 已适配 snapshot |
| TypicalCases | ✅ 已有实现 | 已移除 severity |
| GovernanceMap 嵌入 | ✅ 骨架已实现 | 居中主视觉 |
| Snapshot API (Mock) | ✅ 已实现 | 单端点收口 5 维数据 |
