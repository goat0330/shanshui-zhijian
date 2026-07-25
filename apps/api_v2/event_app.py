"""
C7 — 独立 FastAPI v2 纵切

接口:
POST /api/v2/candidates/intake   — 摄入 Candidate 并生成 Event
GET  /api/v2/events              — 事件列表
GET  /api/v2/events/{event_id}   — 事件详情
POST /api/v2/events/{event_id}/reviews  — 提交审核
GET  /api/v2/events/{event_id}/replay   — 事件时间线
GET  /api/v2/evidence/{evidence_id}     — 证据详情

要求:
- 不修改旧 FastAPI 服务
- 不直接访问模型临时目录
- 不连接 Competition 链
- 使用 Pydantic 输入输出
"""

import json, os, sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# 确保项目根目录在 sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.schemas.contracts.event import AnomalyEvent
from core.schemas.contracts.review import ReviewDecision
from core.schemas.contracts.evidence import Evidence
from core.schemas.contracts.replay import ReplayEntry
from services.repositories.interfaces import Repository
from services.repositories.sqlite_repository import SQLiteRepository, SQLiteRepositoryConfig
from services.event_intelligence.candidate_intake import CandidateIntake, CandidateIntakeError, IncompatibleSchemaError
from services.event_intelligence.evidence_assembler import EvidenceAssembler
from services.event_intelligence.event_service import EventService, EventServiceError, EventConflictError, EventNotFoundError, InvalidTransitionError, DuplicateEventError
from services.review.review_service import ReviewService, ReviewServiceError
from services.replay.replay_service import ReplayService


# ==================================================================
#   应用创建
# ==================================================================

def create_app(
    db_path: str | None = None,
    repo: Repository | None = None,
) -> FastAPI:
    app = FastAPI(title="山水智鉴 V2 — Event Chain API", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── 依赖注入 ──────────────────────────────────────────────
    if repo is None:
        config = SQLiteRepositoryConfig(
            db_path=db_path or str(ROOT / "data" / "agent_c_v2.db"),
        )
        repo = SQLiteRepository(config)

    intake = CandidateIntake(repo)
    assembler = EvidenceAssembler(repo)
    event_svc = EventService(repo)
    review_svc = ReviewService(event_svc)
    replay_svc = ReplayService(repo)

    # ── 请求/响应模型 (G1.1-C2 typed) ─────────────────────────

    class CandidateDeliveryEnvelope(BaseModel):
        """Typed API request envelope for candidate intake."""
        idempotency_key: str = Field(..., min_length=1)
        candidate_id: str = Field(..., min_length=1)
        payload_version: str = Field(default="v0.2")
        candidate_data: dict = Field(...)
        assets: list[dict] = Field(default_factory=list)
        evidence_refs: list[str] = Field(default_factory=list)
        modalities_present: list[str] = Field(default_factory=list)
        modalities_missing: list[str] = Field(default_factory=list)

    class ReviewRequest(BaseModel):
        action: str = Field(..., description="confirm/reject/reclassify/needs_more_evidence")
        reviewer: str = Field(default="api_user")
        comment: str | None = None
        reason_code: str | None = None
        decision_id: str | None = None
        new_category: str | None = Field(None, description="reclassify 必填")

    class ErrorResponse(BaseModel):
        error: str
        detail: str | None = None
        code: str | None = None

    # ── API ────────────────────────────────────────────────────

    @app.post("/api/v2/candidates/intake", status_code=201)
    async def intake_candidate(req: IntakeRequest):
        """摄入 Candidate 并自动生成 Event。"""
        try:
            # 1. Candidate Intake
            idem_key, candidate = intake.ingest_candidate_dict(req.candidate_data)

            # 2. Evidence Assembly
            modalities_info = intake.get_modalities_info(req.candidate_data)
            evidence_list, bundle = assembler.assemble(
                candidate=candidate,
                assets=req.candidate_data.get("assets", []),
                modalities_present=modalities_info.get("modalities_present"),
                modalities_missing=modalities_info.get("modalities_missing"),
                missing_context_notes=req.candidate_data.get("missing_context_notes"),
                evidence_refs=req.candidate_data.get("candidate", {}).get("evidence_refs", []),
            )

            # 3. Event Creation
            event = event_svc.create_event(
                candidate=candidate,
                bundle=bundle,
                idempotency_key=idem_key,
            )

            # 4. Replay
            replay_svc.record_candidate_received(event.event_id, candidate.candidate_id)
            replay_svc.record_evidence_assembled(
                event.event_id, bundle.bundle_id,
                bundle.modalities_present, bundle.modalities_missing,
            )
            replay_svc.record_event_created(event)

            return {
                "status": "ok",
                "event_id": event.event_id,
                "event_version": event.event_version,
                "bundle_id": bundle.bundle_id,
                "evidence_count": len(evidence_list),
                "modalities_missing": bundle.modalities_missing,
            }
        except IncompatibleSchemaError as e:
            raise HTTPException(400, detail={"code": "incompatible_schema", "message": str(e)})
        except CandidateIntakeError as e:
            raise HTTPException(400, detail={"code": "candidate_intake_error", "message": str(e)})
        except DuplicateEventError as e:
            raise HTTPException(409, detail={"code": "duplicate_event", "message": str(e)})
        except EventConflictError as e:
            raise HTTPException(409, detail={"code": "event_conflict", "message": str(e)})
        except Exception as e:
            raise HTTPException(500, detail={"code": "internal_error", "message": str(e)})

    @app.get("/api/v2/events")
    async def list_events():
        """事件列表。"""
        try:
            events = event_svc.repo.list_events()
            return [e.model_dump() for e in events]
        except Exception as e:
            raise HTTPException(500, detail=str(e))

    @app.get("/api/v2/events/{event_id}")
    async def get_event(event_id: str):
        """事件详情。"""
        event = event_svc.repo.get_event(event_id)
        if event is None:
            raise HTTPException(404, detail={"code": "event_not_found", "message": f"Event {event_id} 不存在"})
        return event.model_dump()

    @app.post("/api/v2/events/{event_id}/reviews", status_code=200)
    async def submit_review(event_id: str, req: ReviewRequest):
        """提交审核决策。"""
        try:
            if req.action == "confirm":
                result_event, changed = review_svc.confirm(
                    event_id=event_id, reviewer=req.reviewer,
                    comment=req.comment, reason_code=req.reason_code,
                    decision_id=req.decision_id,
                )
            elif req.action == "reject":
                result_event, changed = review_svc.reject(
                    event_id=event_id, reviewer=req.reviewer,
                    comment=req.comment, reason_code=req.reason_code,
                    decision_id=req.decision_id,
                )
            elif req.action == "needs_more_evidence":
                result_event, changed = review_svc.needs_more_evidence(
                    event_id=event_id, reviewer=req.reviewer,
                    comment=req.comment, reason_code=req.reason_code,
                    decision_id=req.decision_id,
                )
            elif req.action == "reclassify":
                if not req.new_category:
                    raise HTTPException(400, detail="reclassify 需要 new_category")
                result_event, changed = review_svc.reclassify(
                    event_id=event_id, new_category=req.new_category,
                    reviewer=req.reviewer, comment=req.comment,
                    reason_code=req.reason_code, decision_id=req.decision_id,
                )
            else:
                raise HTTPException(400, detail=f"未知 action: {req.action}")

            # Replay
            replay_svc.record_review_submitted(
                ReviewDecision(
                    decision_id=req.decision_id or f"api_{event_id}_{result_event.event_version}",
                    event_ref=event_id,
                    base_event_version=result_event.event_version - 1,
                    action=req.action,
                    reviewer_ref=req.reviewer,
                    resulting_event_version=result_event.event_version,
                ),
                event_version=result_event.event_version,
            )

            return {
                "status": "ok",
                "event_id": result_event.event_id,
                "event_version": result_event.event_version,
                "event_state": result_event.status,
                "changed": changed,
            }
        except EventNotFoundError as e:
            raise HTTPException(404, detail={"code": "event_not_found", "message": str(e)})
        except EventConflictError as e:
            raise HTTPException(409, detail={"code": "version_conflict", "message": str(e)})
        except InvalidTransitionError as e:
            raise HTTPException(400, detail={"code": "invalid_transition", "message": str(e)})
        except Exception as e:
            raise HTTPException(500, detail=str(e))

    @app.get("/api/v2/events/{event_id}/replay")
    async def get_replay(event_id: str):
        """事件时间线。"""
        try:
            timeline = replay_svc.get_timeline(event_id)
            return [e.model_dump() for e in timeline]
        except Exception as e:
            raise HTTPException(500, detail=str(e))

    @app.get("/api/v2/evidence/{evidence_id}")
    async def get_evidence(evidence_id: str):
        """证据详情。"""
        evidence = repo.get_evidence(evidence_id)
        if evidence is None:
            raise HTTPException(
                404, detail={"code": "evidence_not_found", "message": f"Evidence {evidence_id} 不存在"}
            )
        return evidence.model_dump()

    return app


# ── 独立启动 ─────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8100)
