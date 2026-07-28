# 山水智鉴 — Dashboard B2 数据关系图

> 版本: v0.3 (B2 定稿)
> 更新: 2026-07-28

---

## 1. B2 五维关系图

```
                   ┌───────────────────────┐
                   │  GET /dashboard/snapshot│
                   └──────────┬────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                  ▼
     ┌──────────┐     ┌────────────┐     ┌──────────────┐
     │ summary  │     │ change_types│     │   funnel     │
     └────┬─────┘     └─────┬──────┘     └──────┬───────┘
          │                 │                   │
          ▼                 ▼                   ▼
    ┌──────────┐     ┌────────────┐     ┌──────────────┐
    │Situation │     │Spatial     │     │ ReviewFunnel │
    │Cards     │     │Distribution│     │ 4 stages     │
    └──────────┘     └────────────┘     └──────────────┘
          │                                     │
          │           ┌────────────┐            │
          │           │   trend    │            │
          │           └─────┬──────┘            │
          │                 ▼                   │
          │           ┌────────────┐            │
          └──────────►│ TrendChart │◄───────────┘
                      └────────────┘

     ┌────────────────┐     ┌───────────────────────┐
     │ typical_cases  │     │  GovernanceMap         │
     └───────┬────────┘     │  (separate GeoJSON     │
             ▼              │   from /map/*)         │
     ┌──────────────┐       └───────────────────────┘
     │ TypicalCases │
     │ (no severity)│
     └──────────────┘
```

## 2. 数据一致性校验

| 规则 | 说明 |
|------|------|
| summary.total_candidates = Σ change_types[].count | 类型分布之和等于总数 |
| summary.total_candidates = funnel[0].count | 漏斗首阶段等于总数 |
| summary.confirmed = funnel[2].count | 已确认数=漏斗第3阶段 |
| trend[].candidates 月度和 = summary.total_candidates | (近似) |

## 3. 跳转矩阵

| 操作 | 来源 | 目标 | 参数 |
|------|------|------|------|
| 点击典型案例 | Dashboard | /workbench | ?candidate_id=xxx |
