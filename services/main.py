"""
山水智鉴 V0 — FastAPI 后端入口 (SQLite 持久化)

集成:
  - TiTiler (COG 瓦片服务)
  - 产品链 API (DetectionResult / Alert / Review / Event / WorkOrder / Replay)
  - Jinja2 前端页面
  - SQLite 持久化 (服务重启数据不丢)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
import jinja2
import uvicorn
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, AlertRecord, EventRecord, WorkOrderRecord
from core.event_governance.bridge import PerceptionToAlertBridge
from core.event_governance.pipeline import EventGovernancePipeline
from core.event_governance.persistence import create_session as create_gov_session
from core.schemas.contracts.perception import PerceptionResult

# ── 路径 ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
COG_DIR = ROOT / "data" / "chongqing_demo" / "cog"
PRODUCTS_DIR = ROOT / "competition" / "spikes" / "chongqing_rs_demo" / "products"
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
DB_PATH = str(ROOT / "data" / "chongqing_demo" / "shanshui.db")

# ── 数据库初始化 ──────────────────────────────────────────────────
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── 创建应用 ──────────────────────────────────────────────────────
app = FastAPI(title="山水智鉴 V0 — API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)


def db_to_dict(db_obj):
    """SQLAlchemy 对象转 dict，去掉 '_sa_instance_state'"""
    return {c.name: getattr(db_obj, c.name) for c in db_obj.__table__.columns if c.name != "id"}


# ==================================================================
#   TiTiler 代理
# ==================================================================
@app.get("/api/v1/cog/tilejson.json")
async def cog_tilejson():
    return {
        "tilejson": "2.2.0", "name": "chongqing_demo", "scheme": "xyz",
        "tiles": ["http://localhost:8001/cog/tilejson.json"],
        "minzoom": 10, "maxzoom": 18,
        "bounds": [106.55, 29.545, 106.60, 29.585],
    }


# ==================================================================
#   产品链 API (SQLite 持久化)
# ==================================================================

@app.post("/api/v1/detections")
async def ingest_detections():
    """导入 Pipeline 产出的 DetectionResult (JSONL)"""
    jsonl_path = PRODUCTS_DIR / "detection_results.jsonl"
    if not jsonl_path.exists():
        raise HTTPException(404, "请先运行 Pipeline: python pipeline/run_pipeline.py")

    db = next(get_db())
    count = 0
    with open(jsonl_path) as f:
        for line in f:
            dr = json.loads(line)
            alert_id = f"ALT-{dr['detection_id']}"
            existing = db.query(AlertRecord).filter_by(alert_id=alert_id).first()
            if existing:
                continue
            alert = AlertRecord(
                alert_id=alert_id,
                detection_id=dr["detection_id"],
                status="pending",
                category=dr.get("category", "candidate"),
                confidence=dr.get("confidence", 0.5),
                geometry=json.dumps(dr.get("geometry"), ensure_ascii=False) if dr.get("geometry") else "",
                evidence_refs=json.dumps(dr.get("evidence_refs", []), ensure_ascii=False),
                created_at=datetime.now().isoformat(),
            )
            db.add(alert)
            count += 1
    db.commit()
    total = db.query(AlertRecord).count()
    db.close()
    return {"ingested": count, "total_alerts": total}


@app.get("/api/v1/alerts")
async def list_alerts(status: Optional[str] = Query(None)):
    db = next(get_db())
    q = db.query(AlertRecord)
    if status:
        q = q.filter_by(status=status)
    results = [db_to_dict(r) for r in q.all()]
    db.close()
    # geometry 反序列化
    for r in results:
        if r.get("geometry"):
            try:
                r["geometry"] = json.loads(r["geometry"])
            except (json.JSONDecodeError, TypeError):
                pass
    return results


@app.post("/api/v1/alerts/{alert_id}/review")
async def review_alert(alert_id: str, action: str = Query(...),
                       reason: Optional[str] = Query(None),
                       reviewer: str = Query("demo_user")):
    db = next(get_db())
    alert = db.query(AlertRecord).filter_by(alert_id=alert_id).first()
    if not alert:
        db.close()
        raise HTTPException(404, f"Alert {alert_id} not found")

    now = datetime.now().isoformat()
    if action == "confirm":
        alert.status = "confirmed"
        alert.reviewed_at = now
        alert.reviewed_by = reviewer
        event = EventRecord(
            event_id=f"EVT-{alert_id}",
            alert_id=alert_id,
            title=f"异常确认: {alert.category}",
            status="open",
            created_at=now,
        )
        db.add(event)
        db.commit()
        db.close()
        return {"status": "confirmed", "event_id": f"EVT-{alert_id}"}
    elif action == "reject":
        if not reason:
            db.close()
            raise HTTPException(400, "驳回时必须填写原因")
        alert.status = "rejected"
        alert.reject_reason = reason
        alert.reviewed_at = now
        alert.reviewed_by = reviewer
        db.commit()
        db.close()
        return {"status": "rejected", "reason": reason}
    db.close()
    raise HTTPException(400, f"Unknown action: {action}")


@app.get("/api/v1/events")
async def list_events():
    db = next(get_db())
    results = [db_to_dict(r) for r in db.query(EventRecord).all()]
    db.close()
    return results


@app.post("/api/v1/events/{event_id}/work-orders")
async def create_work_order(event_id: str, assignee: str = Query("demo_dispatcher")):
    db = next(get_db())
    event = db.query(EventRecord).filter_by(event_id=event_id).first()
    if not event:
        db.close()
        raise HTTPException(404, f"Event {event_id} not found")
    wo = WorkOrderRecord(
        order_id=f"WO-{event_id}",
        event_id=event_id,
        assignee=assignee,
        status="pending",
        created_at=datetime.now().isoformat(),
    )
    db.add(wo)
    db.commit()
    db.close()
    return {"order_id": wo.order_id, "event_id": wo.event_id, "status": wo.status}


@app.get("/api/v1/work-orders")
async def list_work_orders():
    db = next(get_db())
    results = [db_to_dict(r) for r in db.query(WorkOrderRecord).all()]
    db.close()
    return results


@app.put("/api/v1/work-orders/{order_id}/status")
async def update_work_order(order_id: str, status: str = Query(...),
                            feedback: str = Query("")):
    db = next(get_db())
    wo = db.query(WorkOrderRecord).filter_by(order_id=order_id).first()
    if not wo:
        db.close()
        raise HTTPException(404, f"Work order {order_id} not found")
    wo.status = status
    if feedback:
        wo.feedback = feedback
    if status == "completed":
        wo.completed_at = datetime.now().isoformat()
    db.commit()
    db.close()
    return {"order_id": wo.order_id, "status": wo.status, "feedback": wo.feedback}


# ==================================================================
#   事件治理 v2 API (Perception Ingest + Pipeline)
# ==================================================================

_gov_session = None


def _get_gov_session():
    global _gov_session
    if _gov_session is None:
        _gov_session = create_gov_session()
    return _gov_session


@app.post("/api/v2/ingest/perception")
async def ingest_perception(payload: dict = Body(...)):
    session = _get_gov_session()
    try:
        pr = PerceptionResult(**payload)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid PerceptionResult: {e}")

    pipeline = EventGovernancePipeline(session)
    result = pipeline.process(pr)
    session.commit()

    return {
        "status": "ingested",
        "event_id": result.event.event_id,
        "candidate_id": result.candidate_id,
        "bundle_id": result.bundle_id,
        "n_observations": result.n_observations,
        "event_version": result.event.version,
        "is_idempotent": result.is_idempotent,
    }


@app.get("/api/v2/governance/stats")
async def governance_stats():
    session = _get_gov_session()
    pipeline = EventGovernancePipeline(session)
    return pipeline.get_stats()


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    session = _get_gov_session()
    pipeline = EventGovernancePipeline(session)
    stats = pipeline.get_stats()
    return HTMLResponse(
        jinja_env.get_template("dashboard.html").render(
            {"request": request, "stats": stats}
        )
    )


@app.get("/api/v1/replay")
async def get_replay():
    db = next(get_db())
    alerts = [db_to_dict(r) for r in db.query(AlertRecord).all()]
    events = [db_to_dict(r) for r in db.query(EventRecord).all()]
    work_orders = [db_to_dict(r) for r in db.query(WorkOrderRecord).all()]
    db.close()
    return {"alerts": alerts, "events": events, "work_orders": work_orders}


# ==================================================================
#   前端页面
# ==================================================================

@app.get("/", response_class=HTMLResponse)
async def map_page(request: Request):
    return HTMLResponse(jinja_env.get_template("map.html").render({"request": request}))


@app.get("/review", response_class=HTMLResponse)
async def review_page(request: Request):
    db = next(get_db())
    alerts = [db_to_dict(r) for r in db.query(AlertRecord).all()]
    db.close()
    return HTMLResponse(jinja_env.get_template("review.html").render({"request": request, "alerts": alerts}))


@app.get("/events", response_class=HTMLResponse)
async def events_page(request: Request):
    db = next(get_db())
    events = [db_to_dict(r) for r in db.query(EventRecord).all()]
    work_orders = [db_to_dict(r) for r in db.query(WorkOrderRecord).all()]
    db.close()
    return HTMLResponse(jinja_env.get_template("events.html").render(
        {"request": request, "events": events, "work_orders": work_orders}))


@app.get("/replay", response_class=HTMLResponse)
async def replay_page(request: Request):
    db = next(get_db())
    alerts = [db_to_dict(r) for r in db.query(AlertRecord).all()]
    events = [db_to_dict(r) for r in db.query(EventRecord).all()]
    work_orders = [db_to_dict(r) for r in db.query(WorkOrderRecord).all()]
    db.close()
    return HTMLResponse(jinja_env.get_template("replay.html").render(
        {"request": request, "alerts": alerts, "events": events, "work_orders": work_orders}))


if __name__ == "__main__":
    print(f"  DB: {DB_PATH}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
