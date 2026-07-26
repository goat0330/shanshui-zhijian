"""
山水智鉴 V0 — Workbench API Mock Service

V0 使用内存 Mock 数据。
V1 接入 Agent A/B/C 的 Repository 和 Service。
"""

from datetime import datetime
from typing import Optional

from .main import (
    CandidateListItem, CandidateDetail, QualitySummary,
    EvidenceItem, ReviewDecision, EventDetail, EventVersion,
    RunDetail, ArtifactRef, ArtifactDetail,
)

# ══════════════════════════════════════════════════════════
#  Mock Data
# ══════════════════════════════════════════════════════════

_candidates = [
    CandidateListItem(
        candidate_id=f"CAND-{str(i+1).zfill(4)}", change_type="water_extent_increase",
        persistence_status="persistent" if i < 8 else ("uncertain" if i < 12 else "transient"),
        occurrence_count=3 + (i % 6), persistence_ratio=0.5 + (i % 5) * 0.1,
        within_run_ranking=i + 1, batch_rank=i + 1,
        area_m2=12000 + i * 5000,
        temporal_extent=["2026-03-01T00:00:00Z", "2026-06-30T00:00:00Z"],
    )
    for i in range(36)
]

_candidate_details = {
    c.candidate_id: CandidateDetail(
        candidate_id=c.candidate_id,
        candidate_track_id=f"TRACK-{c.candidate_id}",
        schema_version="1.0",
        change_type=c.change_type,
        persistence_status=c.persistence_status,
        temporal_extent=c.temporal_extent,
        occurrence_count=c.occurrence_count,
        persistence_ratio=c.persistence_ratio,
        representative_geometry={"type": "Polygon", "coordinates": [[[106.55, 29.56], [106.56, 29.56], [106.56, 29.57], [106.55, 29.57], [106.55, 29.56]]]},
        union_geometry={"type": "Polygon", "coordinates": [[[106.55, 29.56], [106.56, 29.56], [106.56, 29.57], [106.55, 29.57], [106.55, 29.56]]]},
        score=0.5 + (i % 10) * 0.05,
        score_type="sorting_score",
        score_components={"temporal_consistency": 35, "spectral_magnitude": 25, "spatial_coherence": 20, "prior_occurrence": 20},
        quality_summary=QualitySummary(overall="good" if i % 3 != 0 else "fair"),
        observation_refs=[f"OBS-{c.candidate_id}-1"],
        source_asset_refs=[f"S2-{c.candidate_id}"],
        rule_version="rs01b2",
        run_manifest_ref="RUN-2026-001",
        within_run_ranking=i + 1,
        batch_rank=i + 1,
        area_m2=c.area_m2,
    )
    for i, c in enumerate(_candidates)
}

_evidence = {
    cid: [
        EvidenceItem(evidence_id=f"EVI-{cid}-1", evidence_type="sentinel2_composite", source_modality="optical",
                     source_asset_ref=f"S2-{cid}", captured_at="2026-06-01T03:30:00Z",
                     stance="supporting", quality_summary=QualitySummary(overall="good", cloud_cover=5),
                     provenance="sentinel-2 L2A → NDWI → Otsu threshold"),
        EvidenceItem(evidence_id=f"EVI-{cid}-2", evidence_type="sar_intensity_change", source_modality="sar",
                     source_asset_ref=f"S1-{cid}", captured_at="2026-06-02T10:15:00Z",
                     stance="supporting", quality_summary=QualitySummary(overall="good"),
                     provenance="sentinel-1 GRD → cal/TC → log ratio"),
    ]
    for cid in _candidate_details
}

_events = [
    EventDetail(event_id="EVT-2026-001", candidate_id="CAND-0001", event_type="water_extent_increase",
                status="confirmed", title="长江支流 A 段水面异常扩展",
                created_at="2026-06-01T10:00:00Z", updated_at="2026-06-05T14:30:00Z",
                versions=[
                    EventVersion(version=1, status="under_review", changed_by="system", changed_at="2026-06-01T10:00:00Z", summary="Candidate 创建"),
                    EventVersion(version=2, status="confirmed", changed_by="user-001", changed_at="2026-06-05T14:30:00Z", summary="人工确认"),
                ]),
    EventDetail(event_id="EVT-2026-002", candidate_id="CAND-0003", event_type="turbidity_anomaly",
                status="under_review", title="B 河流域浑浊度异常",
                created_at="2026-06-10T09:00:00Z", updated_at="2026-06-10T09:00:00Z",
                versions=[EventVersion(version=1, status="under_review", changed_by="system", changed_at="2026-06-10T09:00:00Z", summary="Candidate 创建")]),
]

_runs = [
    RunDetail(run_id="RUN-2026-001", task_id="RS-01B", task_spec_ref="rs01b2_multi_temporal_robust_background",
              git_commit="a1b2c3d4e5f6", git_branch="feature/rs-pipeline", git_dirty=False,
              started_at="2026-05-30T08:00:00Z", finished_at="2026-05-30T10:30:00Z",
              execution_status="completed",
              input_assets=["S2-20260501-L2A", "S2-20260515-L2A", "S2-20260530-L2A"],
              metadata_sources=["copernicus-dataspace"], config_hash="sha256:abc123",
              output_artifacts=[ArtifactRef(artifact_id="ART-CAND-001", asset_type="candidate_geojson",
                                           file_path="/data/products/candidates.geojson",
                                           sha256="def456", size_bytes=1024000)],
              candidate_counts={"persistent": 8, "transient": 15, "uncertain": 3}),
]

_artifacts = {
    "ART-CAND-001": ArtifactDetail(artifact_id="ART-CAND-001", run_id="RUN-2026-001",
                                   asset_type="candidate_geojson", file_path="/data/products/candidates.geojson",
                                   sha256="def456", size_bytes=1024000, metadata={"feature_count": 26, "crs": "EPSG:4326"}),
}

_reviews = {}

_geojson = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": c.candidate_id,
            "geometry": _candidate_details[c.candidate_id].representative_geometry,
            "properties": {"candidate_id": c.candidate_id, "change_type": c.change_type, "persistence_status": c.persistence_status, "batch_rank": c.batch_rank},
        }
        for c in _candidates
    ],
}

_summary = {
    "total_candidates": 36,
    "persistent_count": 12,
    "uncertain_count": 4,
    "transient_count": 20,
    "events_under_review": 1,
    "events_confirmed": 1,
    "total_runs": 1,
    "last_run_at": "2026-05-30T10:30:00Z",
}


# ══════════════════════════════════════════════════════════
#  Query Services
# ══════════════════════════════════════════════════════════

def get_candidates(persistence_status=None, change_type=None, include_transient=False, sort="score", limit=20):
    items = _candidates
    if not include_transient:
        items = [c for c in items if c.persistence_status != "transient"]
    if persistence_status:
        items = [c for c in items if c.persistence_status == persistence_status]
    return items[:limit], len(items)


def get_candidate(candidate_id: str):
    return _candidate_details.get(candidate_id)


def get_evidence(candidate_id: str):
    return _evidence.get(candidate_id, [])


def submit_review(candidate_id: str, review_data: dict):
    from .main import ReviewDecision
    decision = ReviewDecision(
        review_id=f"REV-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        candidate_id=candidate_id,
        action=review_data["action"],
        category=review_data.get("category"),
        comment=review_data["comment"],
        evidence_refs=review_data.get("evidence_refs", []),
        actor_ref=review_data.get("actor_ref", "unknown"),
        base_version=review_data.get("base_version", 1),
        reviewed_at=datetime.now().isoformat(),
    )
    _reviews[candidate_id] = decision
    return decision


def get_events(status=None):
    if status:
        return [e for e in _events if e.status == status]
    return _events


def get_event(event_id: str):
    for e in _events:
        if e.event_id == event_id:
            return e
    return None


def get_event_replay(event_id: str):
    return []


def get_runs(execution_status=None):
    if execution_status:
        return [r for r in _runs if r.execution_status == execution_status]
    return _runs


def get_run(run_id: str):
    for r in _runs:
        if r.run_id == run_id:
            return r
    return None


def get_artifact(artifact_id: str):
    return _artifacts.get(artifact_id)


def get_candidate_geojson():
    return _geojson


def get_event_geojson():
    return {"type": "FeatureCollection", "features": []}


def get_summary():
    return _summary
