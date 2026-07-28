# 山水智鉴 — 领导驾驶舱 (Dashboard) 产品需求文档

> 版本: v0.3 (B2 定稿)
> 更新: 2026-07-28
> 负责人: Agent D
> 状态: B2 已确认，骨架实现中

---

## 1. 产品定位

领导驾驶舱是山水智鉴的**管理者入口**，面向：
- 河湖治理管理者 — 快速掌握管辖区域异常态势
- 比赛演示评委 — 理解产品整体治理闭环和价值
- 外部参观/汇报场景 — 16:9 大屏展示

**与研判工作台的关系：**
- 同一 React 工程，共享组件、类型和 API
- 工作台侧重单 Candidate 深度研判，驾驶舱侧重全局态势感知
- 驾驶舱为只读视图，操作入口导向工作台
- 地图、图例、图层组件共用

---

## 2. 信息架构

### 2.1 一级导航（与应用一致）

```
山水智鉴 V0
├── 驾驶舱       (/dashboard)    ← 本方案
├── 研判工作台   (/workbench)    ← 路由统一
├── 事件中心     (/events)
├── 运行记录     (/runs)
└── 系统设置     (/settings)
```

导航栏项顺序：**驾驶舱排第一**，体现"先看全局、再进细节"的使用逻辑。
`/` 自动重定向到 `/workbench`。

### 2.2 驾驶舱页面结构

```
Dashboard Page  (/dashboard)
│
├── 顶部标题栏
│   ├── 页面标题 "研判驾驶舱"
│   └── DataSourceBadge: MOCK / FIXTURE / REAL（三态）
│
├── [KPI 行] 6 张态势卡片（单行）
│   ├── 异常候选总数
│   ├── 持久性异常
│   ├── 瞬态异常
│   ├── 待研判事件
│   ├── 已确认事件
│   └── 监测范围 (km²)
│
├── [三栏 B2 布局]（1920×1080 无滚动）
│   │
│   ├── 左栏: 月度趋势 + 研判链漏斗
│   │   ├── 趋势图 (TrendChart)
│   │   └── 漏斗 4 阶段 (ReviewFunnel)
│   │         候选产生 → 证据就绪 → 已完成研判 → 已生成事件版本
│   │
│   ├── 中间: GovernanceMap（主视觉）
│   │   ├── Candidate GeoJSON 按 change_type 着色
│   │   └── Event GeoJSON 按 status 着色
│   │
│   └── 右栏: 类型分布 + 典型案例
│       ├── 变化类型柱状图 (SpatialDistribution)
│       └── 典型案例卡片 (TypicalCases)
```

---

## 3. 用户流程

### 3.1 管理者日常浏览流

```
打开驾驶舱 (/dashboard)
  │
  ├─ KPI 行: 6 个关键数字一目了然
  │     ├─ 异常总量？待处理积压？监测范围？
  │     └─ 数据来源标记 (MOCK / FIXTURE / REAL)
  │
  ├─ 中间地图: 空间热点分布
  │     ├─ Candidate 异常聚集区域
  │     ├─ Event 按状态可视化
  │     └─ 缩放/平移探索
  │
  ├─ 左栏: 时间维度 + 流程进度
  │     ├─ 月度趋势: 候选量/确认量变化
  │     └─ 研判链漏斗: 各阶段转化率
  │
  └─ 右栏: 分类分析 + 详情入口
        ├─ 类型分布: 哪种异常最多
        └─ 典型案例: 点击跳转到工作台
```

### 3.2 与工作台的跳转关系

```
驾驶舱 (/dashboard)                  研判工作台 (/workbench)
─────────────────                    ──────────────────────
典型案例卡片点击 ──────────────→ ?candidate_id=xxx
           ←──────────────── 研判完成后回到驾驶舱
```

---

## 4. 数据需求

| 数据维度 | API 端点 | 刷新频率 | 数据量 |
|----------|----------|----------|--------|
| 全量驾驶舱数据 | GET /api/v2/dashboard/snapshot | 页面加载 | 1 条复合响应 |
| Candidate GeoJSON | GET /api/v2/map/candidates.geojson | 地图加载 | ~36 条 |
| Event GeoJSON | GET /api/v2/map/events.geojson | 地图加载 | ~3 条 |

### Snapshot 响应结构

```json
{
  "summary": { "total_candidates": 36, "persistent_count": 12, ... },
  "change_types": [{ "change_type": "water_extent_increase", "label": "水面扩展", "count": 10, "color": "#1565c0" }, ...],
  "trend": [{ "month": "2026-03", "label": "3月", "candidates": 8, "confirmed": 0 }, ...],
  "funnel": [{ "stage": "candidates_created", "count": 36, "description": "算法检测异常候选" }, ...],
  "typical_cases": [{ "id": "EVT-2026-001", "title": "长江支流 A 段水面异常扩展", ... }]
}
```

---

## 5. 非功能要求

| 要求 | 标准 |
|------|------|
| 首屏加载 | < 3 秒 (Mock 模式) |
| Dashboard 布局 | 1920×1080 单屏无滚动 |
| 大屏适配 | 16:9 全屏适配，内容等比缩放 |
| 响应式 | 低于 1280px 自动降级为单栏滚动 |
| 数据标注 | 必须显式标注数据来源 (MOCK / FIXTURE / REAL) |
| 状态完整性 | Loading / Error / Empty 全覆盖 |
| 数据隔离 | 不访问数据库，不读取文件系统 |

---

## 6. 禁止事项

- 禁止显示风险概率、准确率、严重度、违法确认、污染确认
- 禁止"已处理"或 action_taken 字段
- 禁止宣称"实时数据"或"真实治理成效"
- 禁止将排序分称为"概率"
- 禁止自动轮询（页面刷新手动触发）
- 禁止引入额外图表库（纯 CSS + SVG 实现图表，减少依赖）

---

## 7. 验收标准

| ID | 标准 | 验证方式 |
|----|------|----------|
| D-AC01 | 6 张 KPI 卡片数据显示正确 | Playwright 断言 |
| D-AC02 | 三栏布局渲染（左/中/右） | Playwright 截图对比 |
| D-AC03 | 地图居中显示、Candidate/Event 图层加载 | 视觉确认 |
| D-AC04 | 月度趋势柱状图正常渲染 | Playwright 截图对比 |
| D-AC05 | 研判漏斗 4 阶段正确（候选产生→证据就绪→已完成研判→已生成事件版本） | Playwright 断言文本 |
| D-AC06 | 空间分布柱状图正常渲染 | Playwright 截图对比 |
| D-AC07 | 典型案例卡片显示（无 severity 字段） | Playwright 断言 |
| D-AC08 | DataSourceBadge 显示 MOCK | Playwright 检查文本 |
| D-AC09 | 1920×1080 不滚动 | Viewport 测试 |
| D-AC10 | 1280px 以下自动降级单栏 | Viewport 响应式测试 |
| D-AC11 | 所有请求有 Loading 态 | 断言 loading 元素 |
| D-AC12 | API Error 显示 Error State | Mock 500 测试 |
| D-AC13 | 空数据 Empty State | Mock 空数据测试 |
| D-AC14 | 点击案例卡片跳转 /workbench?candidate_id=xxx | Playwright 路由断言 |
| D-AC15 | DataSourceBadge 三态切换正确 | 配置验证 |
