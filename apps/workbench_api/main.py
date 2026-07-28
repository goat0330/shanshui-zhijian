"""
山水智鉴 V0 — Workbench API

薄应用层：
- 参数校验
- 分页筛选
- Query Service
- 调用 Agent C Service
- 读取 Agent B RunManifest
- 读取 Agent A Candidate Envelope
- 调用 TiTiler
- 统一错误

不得:
- 直接修改 Event 状态
- 直接修改 Candidate
- 直接写 SQL
- 绕过 Repository
- 拼接算法文件路径
- 调用 SAR Tool
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── App ──────────────────────────────────────────────────
app = FastAPI(title="山水智鉴 V0 — Workbench API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ══════════════════════════════════════════════════════════
#  DTO (Data Transfer Objects)
#  V0 使用 Pydantic Models 作为 DTO
#  V1 应从 Core Schema Contracts 派生
# ══════════════════════════════════════════════════════════

# ── Error ──

class ApiErrorResponse(BaseModel):
    code: str
    message: str
    details: dict = {}
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


# ── Pagination ──

class Pagination(BaseModel):
    cursor: Optional[str] = None
    has_more: bool = False
    total: int = 0


class PaginatedResponse(BaseModel):
    data: list
    pagination: Pagination


# ── Candidate DTO ──

class QualitySummary(BaseModel):
    overall: str = "good"
    cloud_cover: Optional[float] = None
    geometric_quality: Optional[str] = None
    artifact_count: Optional[int] = None


class CandidateListItem(BaseModel):
    candidate_id: str
    change_type: str
    persistence_status: str
    occurrence_count: int
    persistence_ratio: float
    within_run_ranking: int
    batch_rank: int
    area_m2: float
    temporal_extent: list[str]
    review_state: Optional[str] = None


class CandidateDetail(BaseModel):
    candidate_id: str
    candidate_track_id: str
    schema_version: str
    change_type: str
    persistence_status: str
    temporal_extent: list[str]
    occurrence_count: int
    persistence_ratio: float
    representative_geometry: dict
    union_geometry: dict
    score: float
    score_type: str
    score_components: dict
    quality_summary: QualitySummary
    observation_refs: list[str]
    source_asset_refs: list[str]
    rule_version: str
    run_manifest_ref: str
    within_run_ranking: int
    batch_rank: int
    area_m2: float
    review_state: Optional[str] = None


# ── Evidence DTO ──

class EvidenceItem(BaseModel):
    evidence_id: str
    evidence_type: str
    source_modality: str
    source_asset_ref: str
    derived_asset_ref: Optional[str] = None
    captured_at: str
    stance: str
    quality_summary: QualitySummary
    provenance: str
    unavailable_reason: Optional[str] = None


# ── Review DTO ──

class ReviewRequest(BaseModel):
    action: str  # confirm | reject | reclassify | needs_more_evidence
    category: Optional[str] = None
    comment: str
    evidence_refs: list[str] = []
    actor_ref: str = "unknown"
    base_version: int = 1


class ReviewDecision(BaseModel):
    review_id: str
    candidate_id: str
    action: str
    category: Optional[str] = None
    comment: str
    evidence_refs: list[str]
    actor_ref: str
    base_version: int
    reviewed_at: str


# ── Event DTO ──

class EventVersion(BaseModel):
    version: int
    status: str
    changed_by: str
    changed_at: str
    summary: str


class EventDetail(BaseModel):
    event_id: str
    candidate_id: str
    event_type: str
    status: str
    title: str
    created_at: str
    updated_at: str
    versions: list[EventVersion] = []
    timeline: list[dict] = []


# ── Run DTO ──

class ArtifactRef(BaseModel):
    artifact_id: str
    asset_type: str
    file_path: str
    sha256: str
    size_bytes: int


class RunDetail(BaseModel):
    run_id: str
    task_id: str
    task_spec_ref: str
    git_commit: str
    git_branch: str
    git_dirty: bool
    started_at: str
    finished_at: Optional[str] = None
    execution_status: str
    input_assets: list[str] = []
    metadata_sources: list[str] = []
    config_hash: str
    output_artifacts: list[ArtifactRef] = []
    failure_stage: Optional[str] = None
    candidate_counts: dict = {}


# ── Artifact DTO ──

class ArtifactDetail(BaseModel):
    artifact_id: str
    run_id: str
    asset_type: str
    file_path: str
    sha256: str
    size_bytes: int
    cog_url: Optional[str] = None
    tilejson_url: Optional[str] = None
    metadata: dict = {}


# ── Dashboard DTO ──

class DashboardSummaryDTO(BaseModel):
    total_candidates: int = 0
    persistent_count: int = 0
    uncertain_count: int = 0
    transient_count: int = 0
    events_under_review: int = 0
    events_confirmed: int = 0
    events_rejected: int = 0
    events_needs_evidence: int = 0
    total_runs: int = 0
    runs_completed: int = 0
    runs_failed: int = 0
    last_run_at: str = ""
    monitoring_area_km2: float = 0.0


class ChangeTypeDTO(BaseModel):
    change_type: str
    label: str
    count: int
    color: str


class MonthlyTrendDTO(BaseModel):
    month: str
    label: str
    candidates: int
    confirmed: int


class FunnelStageDTO(BaseModel):
    stage: str
    count: int
    description: str


class TypicalCaseDTO(BaseModel):
    id: str
    title: str
    change_type: str
    change_type_label: str
    status: str
    status_label: str
    area_m2: float
    detected_at: str
    summary: str
    candidate_id: Optional[str] = None


class DashboardSnapshotResponse(BaseModel):
    summary: DashboardSummaryDTO
    change_types: list[ChangeTypeDTO]
    trend: list[MonthlyTrendDTO]
    funnel: list[FunnelStageDTO]
    typical_cases: list[TypicalCaseDTO]


# ══════════════════════════════════════════════════════════
#  In-Memory Store (V0 不连接数据库)
# ══════════════════════════════════════════════════════════

# Service layer — 使用 real_service (接入 C 的 event_governance)
from . import real_service as _rs


# ══════════════════════════════════════════════════════════
#  Error Handler 统一错误处理
# ══════════════════════════════════════════════════════════

@app.exception_handler(Exception)
async def generic_error_handler(request, exc):
    if isinstance(exc, HTTPException):
        raise exc
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"code": "SERVICE_ERROR", "message": "服务内部错误", "details": {"error": str(exc)}},
    )


# ══════════════════════════════════════════════════════════
#  API Endpoints
# ══════════════════════════════════════════════════════════

# ── Summary ──

@app.get("/api/v2/workbench/summary")
async def summary():
    return _rs.get_summary()


# ── Candidates ──

class CandidateIntakeRequest(BaseModel):
    candidate_id: str
    observation_refs: list[str]
    temporal_extent: dict
    candidate_type: str
    score: float
    geometry: dict | None = None
    evidence_refs: list[str] = []
    rule_version: str = "1.0.0"


@app.post("/api/v2/candidates/intake")
async def intake_candidate(req: CandidateIntakeRequest):
    from core.schemas.contracts.candidate import DetectionCandidate, CandidateQualitySummary
    candidate = DetectionCandidate(
        candidate_id=req.candidate_id,
        observation_refs=req.observation_refs,
        temporal_extent=req.temporal_extent,
        candidate_type=req.candidate_type,
        score=req.score,
        geometry=req.geometry,
        evidence_refs=req.evidence_refs,
        rule_version=req.rule_version,
    )
    from .real_service import ensure_db, do_intake
    session = ensure_db()
    result = do_intake(session, candidate)
    session.commit()
    return result


@app.get("/api/v2/candidates")
async def list_candidates(
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = None,
    persistence_status: Optional[str] = None,
    change_type: Optional[str] = None,
    aoi_id: Optional[str] = None,
    run_id: Optional[str] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    bbox: Optional[str] = None,
    sort: Optional[str] = "score",
    include_transient: bool = False,
):
    items, total = _rs.get_candidates(
        persistence_status=persistence_status,
        change_type=change_type,
        include_transient=include_transient,
        sort=sort,
        limit=limit,
    )
    return PaginatedResponse(
        data=[item.model_dump() for item in items],
        pagination=Pagination(total=total),
    )


@app.get("/api/v2/candidates/{candidate_id}")
async def get_candidate_detail(candidate_id: str):
    candidate = _rs.get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=ApiErrorResponse(
                code="NOT_FOUND",
                message=f"Candidate {candidate_id} 不存在",
            ).model_dump(),
        )
    return candidate.model_dump()


@app.get("/api/v2/candidates/{candidate_id}/evidence")
async def list_evidence(candidate_id: str):
    return [e.model_dump() for e in _rs.get_evidence(candidate_id)]


@app.get("/api/v2/candidates/{candidate_id}/artifacts")
async def list_candidate_artifacts(candidate_id: str):
    # V0 返回空列表，待 Agent B 接入
    return []


@app.post("/api/v2/candidates/{candidate_id}/reviews")
async def create_review(candidate_id: str, review: ReviewRequest):
    if review.action not in ("confirm", "reject", "reclassify", "needs_more_evidence"):
        raise HTTPException(
            status_code=422,
            detail=ApiErrorResponse(
                code="VALIDATION_ERROR",
                message=f"无效的 action: {review.action}",
            ).model_dump(),
        )
    if review.action == "reject" and not review.comment:
        raise HTTPException(
            status_code=422,
            detail=ApiErrorResponse(
                code="VALIDATION_ERROR",
                message="驳回时必须填写原因",
            ).model_dump(),
        )

    gov_result = _rs.submit_review(candidate_id, review.model_dump())
    return ReviewDecision(
        review_id=gov_result.review_id,
        candidate_id=candidate_id,
        action=gov_result.decision,
        category=gov_result.category,
        comment=gov_result.comment or gov_result.reason,
        evidence_refs=[],
        actor_ref=gov_result.reviewer,
        base_version=gov_result.expected_version,
        reviewed_at=gov_result.reviewed_at,
    ).model_dump()


# ── Events ──

@app.get("/api/v2/events")
async def list_events(
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = None,
    status: Optional[str] = None,
    change_type: Optional[str] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
):
    items = _rs.get_events(status=status)
    return PaginatedResponse(
        data=[item.model_dump() for item in items],
        pagination=Pagination(total=len(items)),
    )


@app.get("/api/v2/events/{event_id}")
async def get_event_detail(event_id: str):
    event = _rs.get_event(event_id)
    if not event:
        raise HTTPException(
            status_code=404,
            detail=ApiErrorResponse(
                code="NOT_FOUND",
                message=f"Event {event_id} 不存在",
            ).model_dump(),
        )
    return event.model_dump()


@app.get("/api/v2/events/{event_id}/versions")
async def get_event_versions(event_id: str):
    event = _rs.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Event 不存在"})
    return [v.model_dump() for v in event.versions]


@app.get("/api/v2/events/{event_id}/replay")
async def get_event_replay(event_id: str):
    return _rs.get_event_replay(event_id)


# ── Runs ──

@app.get("/api/v2/runs")
async def list_runs(
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = None,
    execution_status: Optional[str] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
):
    items = _rs.get_runs(execution_status=execution_status)
    return PaginatedResponse(
        data=[item.model_dump() for item in items],
        pagination=Pagination(total=len(items)),
    )


@app.get("/api/v2/runs/{run_id}")
async def get_run_detail(run_id: str):
    run = _rs.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=404,
            detail=ApiErrorResponse(
                code="NOT_FOUND",
                message=f"Run {run_id} 不存在",
            ).model_dump(),
        )
    return run.model_dump()


# ── Artifacts ──

@app.get("/api/v2/artifacts/{artifact_id}")
async def get_artifact_detail(artifact_id: str):
    artifact = _rs.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=404,
            detail=ApiErrorResponse(
                code="NOT_FOUND",
                message=f"Artifact {artifact_id} 不存在",
            ).model_dump(),
        )
    return artifact.model_dump()


@app.get("/api/v2/artifacts/{artifact_id}/tilejson")
async def get_artifact_tilejson(artifact_id: str):
    artifact = _rs.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Artifact 不存在"})
    return {
        "tilejson": "2.2.0",
        "name": artifact_id,
        "scheme": "xyz",
        "tiles": [artifact.tilejson_url or ""],
        "minzoom": 10,
        "maxzoom": 18,
        "bounds": [106.45, 29.53, 106.65, 29.63],
    }


# ── Map ──

@app.get("/api/v2/map/candidates.geojson")
async def map_candidates_geojson():
    return _rs.get_candidate_geojson()


@app.get("/api/v2/map/events.geojson")
async def map_events_geojson():
    return _rs.get_event_geojson()


# ── Dashboard ──

@app.get("/api/v2/dashboard/snapshot", response_model=DashboardSnapshotResponse)
async def dashboard_snapshot():
    return _rs.get_dashboard_snapshot()


# ══════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
