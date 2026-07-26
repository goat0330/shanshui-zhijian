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


# ══════════════════════════════════════════════════════════
#  In-Memory Store (V0 不连接数据库)
# ══════════════════════════════════════════════════════════

# Mock data imports
from .mock_service import get_candidates, get_candidate, get_evidence, get_events, get_event, get_event_replay, get_runs, get_run, get_artifact, get_candidate_geojson, get_event_geojson, get_summary, submit_review


# ══════════════════════════════════════════════════════════
#  Error Handler 统一错误处理
# ══════════════════════════════════════════════════════════

@app.exception_handler(Exception)
async def generic_error_handler(request, exc):
    if isinstance(exc, HTTPException):
        raise exc
    return ApiErrorResponse(
        code="SERVICE_ERROR",
        message="服务内部错误",
        details={"error": str(exc)},
    )


# ══════════════════════════════════════════════════════════
#  API Endpoints
# ══════════════════════════════════════════════════════════

# ── Summary ──

@app.get("/api/v2/workbench/summary")
async def summary():
    return get_summary()


# ── Candidates ──

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
    items, total = get_candidates(
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
    candidate = get_candidate(candidate_id)
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
    return [e.model_dump() for e in get_evidence(candidate_id)]


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

    result = submit_review(candidate_id, review.model_dump())
    return result.model_dump()


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
    items = get_events(status=status)
    return PaginatedResponse(
        data=[item.model_dump() for item in items],
        pagination=Pagination(total=len(items)),
    )


@app.get("/api/v2/events/{event_id}")
async def get_event_detail(event_id: str):
    event = get_event(event_id)
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
    event = get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Event 不存在"})
    return [v.model_dump() for v in event.versions]


@app.get("/api/v2/events/{event_id}/replay")
async def get_event_replay(event_id: str):
    return get_event_replay(event_id)


# ── Runs ──

@app.get("/api/v2/runs")
async def list_runs(
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = None,
    execution_status: Optional[str] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
):
    items = get_runs(execution_status=execution_status)
    return PaginatedResponse(
        data=[item.model_dump() for item in items],
        pagination=Pagination(total=len(items)),
    )


@app.get("/api/v2/runs/{run_id}")
async def get_run_detail(run_id: str):
    run = get_run(run_id)
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
    artifact = get_artifact(artifact_id)
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
    artifact = get_artifact(artifact_id)
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
    return get_candidate_geojson()


@app.get("/api/v2/map/events.geojson")
async def map_events_geojson():
    return get_event_geojson()


# ══════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
