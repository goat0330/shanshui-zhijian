# 山水智鉴 — WB-02 用户验收包

> 版本: v0.4
> 更新: 2026-07-28
> 负责人: Agent D

---

## 1. 访问信息

- 本地启动: `cd frontend && npx vite --host 0.0.0.0 --port 5173`
- 访问地址: `http://localhost:5173/dashboard`
- 后端 API: 无需单独启动 (Mock 模式通过 MSW 拦截)
- 真实后端: `cd .. && uvicorn apps.workbench_api.main:app --reload --port 8000`

---

## 2. 截图

| 分辨率 | 文件 |
|--------|------|
| 1920×1080 | `frontend/tests/screenshots/dashboard-1920x1080.png` |
| 1366×768 | `frontend/tests/screenshots/dashboard-1366x768.png` |

---

## 3. React 组件树

```
DashboardPage  →  B2 三栏无滚动布局 (1920×1080)
│
├── DataSourceBadge          ← config.apiMode 自动 MOCK/FIXTURE/REAL
├── SituationCards           ← 6 KPI：异常候选 / 持久性 / 瞬态 / 待研判 / 已确认 / 监测范围
│   └── SituationCard × 6    ← 颜色编码顶部边框
│
├── [左栏 280px]
│   ├── TrendChart           ← SVG 柱状图 (候选人/确认量/月)
│   └── ReviewFunnel         ← 4 阶段垂直漏斗
│       └── FunnelStage × 4 ← 候选产生→证据就绪→已完成研判→已生成事件版本
│
├── [中间 flex 1]
│   └── GovernanceMap        ← readonly 模式 (无 Toolbar/StatusBar/Popup)
│       ├── Candidate GeoJSON (persistence_status 着色)
│       └── Event GeoJSON (status 着色)
│
└── [右栏 300px]
    ├── SpatialDistribution  ← CSS 水平柱状图 (8 种变化类型)
    └── TypicalCases         ← 5 张卡片，点击跳转 /workbench
```

---

## 4. 六个 KPI 的产品定义

| 卡片 | 数据字段 | 说明 | 数据来源 |
|------|---------|------|---------|
| 异常候选 | `summary.total_candidates` | 算法产出的全部异常候选图斑数 | mock: getDashboardSnapshot().summary |
| 持久性异常 | `summary.persistent_count` | 多次观测持续存在的异常 (persistent) | 同上 |
| 瞬态异常 | `summary.transient_count` | 单次观测出现的瞬态异常 (transient) | 同上 |
| 待研判事件 | `summary.events_under_review` | under_review 状态的事件数 | 同上 |
| 已确认事件 | `summary.events_confirmed` | confirmed 状态的事件数 | 同上 |
| 监测范围 | `summary.monitoring_area_km2` | 当前有效覆盖面积 (km²) | 同上 |

---

## 5. 数据来源

| 组件 | 数据 | 后端端点 | Mock 模式 (MSW) | Real 模式 (后端) |
|------|------|---------|----------------|-----------------|
| SituationCards | DashboardSummary | dashboard/snapshot → .summary | MSW 拦截返回 mock 数据 | 后端 real_service (event_governance pipeline) |
| TrendChart | MonthlyTrend[] | dashboard/snapshot → .trend | 同上 | 后端聚合 |
| ReviewFunnel | FunnelStage[] | dashboard/snapshot → .funnel | 同上 | 后端 pipeline.get_snapshot().funnel |
| SpatialDistribution | ChangeTypeDTO[] | dashboard/snapshot → .change_types | 同上 | 后端 mock 回退 |
| TypicalCases | TypicalCaseDTO[] | dashboard/snapshot → .typical_cases | 同上 | 后端 mock 回退 |
| GovernanceMap | Candidate/Event GeoJSON | /map/candidates.geojson | MSW 拦截 | 后端回退 mock_service |
| Workbench | Candidate 列表 | /candidates | MSW 拦截 | candidate_store (SQLite) |
| Workbench | Candidate 详情 | /candidates/{id} | MSW 拦截 | 后端回退 mock |
| Events | Event 列表 | /events | MSW 拦截 | event_governance (SQLite) |
| DataSourceBadge | apiMode config | 读取 VITE_API_MODE | 显示 MOCK | 显示 REAL |

### Real 模式已知 Mock 回退

| 端点 | 原因 | 依赖 |
|------|------|------|
| /dashboard/snapshot change_types | event_governance 无 change type 聚合 | Agent C pipeline 升级 |
| /map/candidates.geojson | candidate_store 无 GeoJSON | Agent A 存储接入 |
| /candidates/{id}/evidence | event_governance 未接入证据 | Agent C |
| /artifacts, /runs | Agent B RunManifest 未接入 | Agent B |

---

## 6. TypeScript Build

```
npx tsc --noEmit  →  0 errors
```

## 7. Vitest

```
Test Files  6 passed (6)
     Tests  43 passed (43)
```

## 8. 后端 API

```
python -c "from apps.workbench_api.mock_service import get_dashboard_snapshot; ..."
→  36 candidates, 8 change types, 4 months, 4 funnel stages, 5 typical cases
```
