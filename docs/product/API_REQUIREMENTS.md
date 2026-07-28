# 山水智鉴 V0 — API 需求文档

> 版本: v0.1
> 更新: 2026-07-26

---

## 1. API 设计原则

- 薄应用：仅负责参数校验、分页筛选、Query Service
- 调用 Agent C Service 而非直接修改 Event
- 读取 Agent B RunManifest 而非直接拼接文件路径
- 读取 Agent A Candidate Envelope
- 调用 TiTiler 提供瓦片
- 统一错误格式

## 2. 接口清单

### Candidates

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v2/candidates` | Candidate 列表（分页+筛选） |
| GET | `/api/v2/candidates/{candidate_id}` | Candidate 详情 |
| GET | `/api/v2/candidates/{candidate_id}/evidence` | Evidence 列表 |
| GET | `/api/v2/candidates/{candidate_id}/artifacts` | Artifact 列表 |
| POST | `/api/v2/candidates/{candidate_id}/reviews` | 提交 Review |

### Events

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v2/events` | Event 列表 |
| GET | `/api/v2/events/{event_id}` | Event 详情 |
| GET | `/api/v2/events/{event_id}/versions` | Event 版本历史 |
| GET | `/api/v2/events/{event_id}/replay` | Replay 条目 |

### Runs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v2/runs` | Run 列表 |
| GET | `/api/v2/runs/{run_id}` | Run 详情 |

### Artifacts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v2/artifacts/{artifact_id}` | Artifact 详情 |
| GET | `/api/v2/artifacts/{artifact_id}/tilejson` | TileJSON 信息 |

### Map

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v2/map/candidates.geojson` | 所有 Candidate 的 GeoJSON |
| GET | `/api/v2/map/events.geojson` | 所有 Event 的 GeoJSON |

### Summary

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v2/workbench/summary` | 工作台概览统计 |

---

## 3. 统一查询参数

```
limit: int (default 20, max 100)
cursor: str (游标分页)
status: str (Event 状态筛选)
change_type: str
persistence_status: str
aoi_id: str
run_id: str
time_from: str (ISO datetime)
time_to: str (ISO datetime)
bbox: str (west,south,east,north)
sort: str (字段名, 前缀 - 表示降序)
include_transient: bool (default false)
```

## 4. 统一错误格式

```json
{
  "code": "ERROR_CODE",
  "message": "用户可理解的信息",
  "details": {},
  "trace_id": "uuid"
}
```

### Error Codes
| Code | HTTP | Description |
|------|------|-------------|
| NOT_FOUND | 404 | 资源不存在 |
| VALIDATION_ERROR | 422 | 参数校验失败 |
| CONFLICT | 409 | 版本冲突 |
| SERVICE_ERROR | 500 | 服务内部错误 |
| RATE_LIMITED | 429 | 请求过频繁 |

## 5. 分页规范

```json
{
  "data": [...],
  "pagination": {
    "cursor": "next_cursor_value",
    "has_more": true,
    "total": 42
  }
}
```
