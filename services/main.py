"""
山水智鉴 V0 — FastAPI 后端入口

集成:
  - TiTiler (COG 瓦片服务)
  - 产品链 API (DetectionResult / Alert / Review / Event / WorkOrder / Replay)
  - Jinja2 前端页面
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.templating import _TemplateResponse as TemplateResponse
import jinja2
import uvicorn

# ── 路径 ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
COG_DIR = ROOT / "data" / "chongqing_demo" / "cog"
PRODUCTS_DIR = ROOT / "competition" / "spikes" / "chongqing_rs_demo" / "products"
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

# ── 创建应用 ──────────────────────────────────────────────────────
app = FastAPI(title="山水智鉴 V0 — API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 挂载静态文件
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)

# ── 内存存储 (V0 不使用数据库) ──────────────────────────────────
_alerts: list[dict] = []
_events: list[dict] = []
_work_orders: list[dict] = []


# ==================================================================
#   TiTiler 代理 — 提供 COG 瓦片
# ==================================================================
def get_titiler_endpoint():
    """尝试返回可用的 TiTiler 地址"""
    return "http://localhost:8001"


@app.get("/api/v1/cog/tilejson.json")
async def cog_tilejson():
    """返回 COG TileJSON (代理到 TiTiler)"""
    return {
        "tilejson": "2.2.0",
        "name": "chongqing_demo",
        "scheme": "xyz",
        "tiles": [f"{get_titiler_endpoint()}/cog/tilejson.json"],
        "minzoom": 10,
        "maxzoom": 18,
        "bounds": [106.55, 29.545, 106.60, 29.585],
    }


@app.get("/api/v1/cog/layers")
async def cog_layers():
    """可用的 COG 图层列表"""
    layers = []
    for f in sorted(COG_DIR.glob("*_cog.tif")):
        layers.append({
            "name": f.stem.replace("_cog", ""),
            "path": str(f),
            "url": f"/cog/{f.name}",
        })
    return {"layers": layers}


# ==================================================================
#   产品链 API
# ==================================================================

@app.post("/api/v1/detections")
async def ingest_detections():
    """接收 Pipeline 产出的 DetectionResult (JSONL 落地)"""
    products_dir = PRODUCTS_DIR
    jsonl_path = products_dir / "detection_results.jsonl"
    if not jsonl_path.exists():
        raise HTTPException(404, "No detection results found. Run pipeline first.")
    count = 0
    with open(jsonl_path) as f:
        for line in f:
            dr = json.loads(line)
            # 自动生成 alert
            alert = {
                "alert_id": f"ALT-{dr['detection_id']}",
                "detection_id": dr["detection_id"],
                "status": "pending",
                "category": dr.get("category", "candidate"),
                "geometry": dr.get("geometry"),
                "confidence": dr.get("confidence", 0.5),
                "evidence_refs": dr.get("evidence_refs", []),
                "created_at": datetime.now().isoformat(),
            }
            _alerts.append(alert)
            count += 1
    return {"ingested": count, "total_alerts": len(_alerts)}


@app.get("/api/v1/alerts")
async def list_alerts(status: Optional[str] = Query(None)):
    """待核验告警列表"""
    if status:
        return [a for a in _alerts if a["status"] == status]
    return _alerts


@app.post("/api/v1/alerts/{alert_id}/review")
async def review_alert(alert_id: str, action: str = Query(...),
                       reason: Optional[str] = Query(None),
                       reviewer: str = Query("demo_user")):
    """人工核验: 确认或驳回"""
    for a in _alerts:
        if a["alert_id"] == alert_id:
            if action == "confirm":
                a["status"] = "confirmed"
                a["reviewed_at"] = datetime.now().isoformat()
                a["reviewed_by"] = reviewer
                # 自动生成 GovernanceEvent
                event = {
                    "event_id": f"EVT-{alert_id}",
                    "alert_id": alert_id,
                    "title": f"异常确认: {a.get('category', 'candidate')}",
                    "status": "open",
                    "created_at": datetime.now().isoformat(),
                }
                _events.append(event)
                return {"status": "confirmed", "event_id": event["event_id"]}
            elif action == "reject":
                if not reason:
                    raise HTTPException(400, "驳回时必须填写原因")
                a["status"] = "rejected"
                a["reject_reason"] = reason
                a["reviewed_at"] = datetime.now().isoformat()
                a["reviewed_by"] = reviewer
                return {"status": "rejected", "reason": reason}
    raise HTTPException(404, f"Alert {alert_id} not found")


@app.get("/api/v1/events")
async def list_events():
    """已确认的事件列表"""
    return _events


@app.post("/api/v1/events/{event_id}/work-orders")
async def create_work_order(event_id: str, assignee: str = Query("demo_dispatcher")):
    """创建工单"""
    event = next((e for e in _events if e["event_id"] == event_id), None)
    if not event:
        raise HTTPException(404, f"Event {event_id} not found")
    wo = {
        "order_id": f"WO-{event_id}",
        "event_id": event_id,
        "assignee": assignee,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    _work_orders.append(wo)
    return wo


@app.get("/api/v1/work-orders")
async def list_work_orders():
    return _work_orders


@app.put("/api/v1/work-orders/{order_id}/status")
async def update_work_order(order_id: str, status: str = Query(...),
                            feedback: str = Query("")):
    """更新工单状态"""
    for wo in _work_orders:
        if wo["order_id"] == order_id:
            wo["status"] = status
            if feedback:
                wo["feedback"] = feedback
            if status == "completed":
                wo["completed_at"] = datetime.now().isoformat()
            return wo
    raise HTTPException(404, f"Work order {order_id} not found")


@app.get("/api/v1/replay")
async def get_replay():
    """全流程回放"""
    return {
        "alerts": _alerts,
        "events": _events,
        "work_orders": _work_orders,
    }


# ==================================================================
#   前端页面
# ==================================================================

@app.get("/", response_class=HTMLResponse)
async def map_page(request: Request):
    template = jinja_env.get_template("map.html")
    html = template.render({"request": request})
    return HTMLResponse(html)


@app.get("/review", response_class=HTMLResponse)
async def review_page(request: Request):
    template = jinja_env.get_template("review.html")
    html = template.render({"request": request, "alerts": _alerts})
    return HTMLResponse(html)


@app.get("/events", response_class=HTMLResponse)
async def events_page(request: Request):
    template = jinja_env.get_template("events.html")
    html = template.render({"request": request, "events": _events, "work_orders": _work_orders})
    return HTMLResponse(html)


@app.get("/replay", response_class=HTMLResponse)
async def replay_page(request: Request):
    template = jinja_env.get_template("replay.html")
    html = template.render({"request": request, "alerts": _alerts, "events": _events, "work_orders": _work_orders})
    return HTMLResponse(html)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
