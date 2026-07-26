/* ============================================================
   山水智鉴 V0 — MSW Handler Index
   ============================================================ */

import { http, HttpResponse, delay } from 'msw';
import { mockCandidateListItems, getMockCandidate } from '@/mocks/data/candidates';
import { getMockEvidence } from '@/mocks/data/evidence';
import { getMockEvents, getMockEvent, getMockReplay, getEventForCandidate } from '@/mocks/data/events';
import { getMockRuns, getMockRun } from '@/mocks/data/runs';
import { getMockReview, addMockReview } from '@/mocks/data/reviews';
import { getMockArtifact } from '@/mocks/data/artifacts';
import type { CandidateDTO, EventDTO, ReviewRequest, PaginatedResponse, ApiError } from '@/shared/types';

const API = '/api/v2';

// Helper to simulate delay
async function simDelay(ms = 300) {
  await delay(ms);
}

export const handlers = [
  // ── Candidates ──

  http.get(`${API}/candidates`, async ({ request }) => {
    await simDelay();
    const url = new URL(request.url);
    const includeTransient = url.searchParams.get('include_transient') === 'true';
    const persistence = url.searchParams.get('persistence_status');
    const changeType = url.searchParams.get('change_type');
    const sort = url.searchParams.get('sort') || 'score';

    let list = [...mockCandidateListItems];

    // Filter by persistence
    if (persistence && persistence !== 'all') {
      list = list.filter((c) => c.persistence_status === persistence);
    } else if (!includeTransient) {
      list = list.filter((c) => c.persistence_status !== 'transient');
    }

    // Filter by change_type
    if (changeType) {
      list = list.filter((c) => c.change_type === changeType);
    }

    // Sort
    if (sort === 'area') {
      list.sort((a, b) => b.area_m2 - a.area_m2);
    } else if (sort === 'occurrence_count') {
      list.sort((a, b) => b.occurrence_count - a.occurrence_count);
    } else {
      // default: score ranking (lower batch_rank = higher score = displayed first)
      list.sort((a, b) => (a.batch_rank ?? 999) - (b.batch_rank ?? 999));
    }

    const response: PaginatedResponse<typeof list[0]> = {
      data: list.slice(0, 20),
      pagination: { cursor: null, has_more: false, total: list.length },
    };

    // Empty state test
    if (url.searchParams.get('empty') === 'true') {
      return HttpResponse.json({ data: [], pagination: { cursor: null, has_more: false, total: 0 } });
    }

    return HttpResponse.json(response);
  }),

  http.get(`${API}/candidates/:candidate_id`, async ({ params }) => {
    await simDelay(100);
    const candidate = getMockCandidate(params.candidate_id as string);
    if (!candidate) {
      return HttpResponse.json({ code: 'NOT_FOUND', message: 'Candidate 不存在', details: {}, trace_id: 'mock-001' } as ApiError, { status: 404 });
    }
    return HttpResponse.json(candidate);
  }),

  http.get(`${API}/candidates/:candidate_id/evidence`, async ({ params }) => {
    await simDelay();
    const evidence = getMockEvidence(params.candidate_id as string);
    return HttpResponse.json(evidence);
  }),

  http.get(`${API}/candidates/:candidate_id/artifacts`, async ({ params }) => {
    await simDelay();
    const candidate = getMockCandidate(params.candidate_id as string);
    if (!candidate) {
      return HttpResponse.json({ code: 'NOT_FOUND', message: 'Candidate 不存在', details: {}, trace_id: 'mock-002' } as ApiError, { status: 404 });
    }
    // Map source_asset_refs to artifact IDs
    const artifacts = candidate.source_asset_refs.map((ref) => getMockArtifact(ref));
    return HttpResponse.json(artifacts.filter(Boolean));
  }),

  http.post(`${API}/candidates/:candidate_id/reviews`, async ({ params, request }) => {
    await simDelay(200);
    const body = (await request.json()) as ReviewRequest;
    const candidateId = params.candidate_id as string;

    // Simulate conflict
    if (candidateId === 'CAND-0010') {
      return HttpResponse.json({ code: 'CONFLICT', message: '版本冲突 — 该 Candidate 已被其他人更新', details: { current_version: 2, your_version: body.base_version }, trace_id: 'mock-conflict' } as ApiError, { status: 409 });
    }

    const review = {
      review_id: `REV-${Date.now()}`,
      candidate_id: candidateId,
      action: body.action,
      category: body.category ?? null,
      comment: body.comment,
      evidence_refs: body.evidence_refs,
      actor_ref: body.actor_ref,
      base_version: body.base_version,
      reviewed_at: new Date().toISOString(),
    };

    addMockReview(review);

    return HttpResponse.json(review, { status: 201 });
  }),

  // ── Events ──

  http.get(`${API}/events`, async ({ request }) => {
    await simDelay();
    const url = new URL(request.url);
    const status = url.searchParams.get('status');
    let events = getMockEvents();
    if (status) {
      events = events.filter((e) => e.status === status);
    }
    const response: PaginatedResponse<EventDTO> = {
      data: events,
      pagination: { cursor: null, has_more: false, total: events.length },
    };
    if (url.searchParams.get('empty') === 'true') {
      return HttpResponse.json({ data: [], pagination: { cursor: null, has_more: false, total: 0 } });
    }
    return HttpResponse.json(response);
  }),

  http.get(`${API}/events/:event_id`, async ({ params }) => {
    await simDelay(100);
    const event = getMockEvent(params.event_id as string);
    if (!event) {
      return HttpResponse.json({ code: 'NOT_FOUND', message: 'Event 不存在', details: {}, trace_id: 'mock-003' } as ApiError, { status: 404 });
    }
    return HttpResponse.json(event);
  }),

  http.get(`${API}/events/:event_id/versions`, async ({ params }) => {
    await simDelay();
    const event = getMockEvent(params.event_id as string);
    if (!event) {
      return HttpResponse.json({ code: 'NOT_FOUND', message: 'Event 不存在', details: {}, trace_id: 'mock-004' } as ApiError, { status: 404 });
    }
    return HttpResponse.json(event.versions);
  }),

  http.get(`${API}/events/:event_id/replay`, async ({ params }) => {
    await simDelay();
    const replay = getMockReplay(params.event_id as string);
    return HttpResponse.json(replay);
  }),

  // ── Runs ──

  http.get(`${API}/runs`, async ({ request }) => {
    await simDelay();
    const url = new URL(request.url);
    const runs = getMockRuns();
    const response: PaginatedResponse<typeof runs[0]> = {
      data: runs,
      pagination: { cursor: null, has_more: false, total: runs.length },
    };
    if (url.searchParams.get('empty') === 'true') {
      return HttpResponse.json({ data: [], pagination: { cursor: null, has_more: false, total: 0 } });
    }
    return HttpResponse.json(response);
  }),

  http.get(`${API}/runs/:run_id`, async ({ params }) => {
    await simDelay(100);
    const run = getMockRun(params.run_id as string);
    if (!run) {
      return HttpResponse.json({ code: 'NOT_FOUND', message: 'Run 不存在', details: {}, trace_id: 'mock-005' } as ApiError, { status: 404 });
    }
    return HttpResponse.json(run);
  }),

  // ── Artifacts ──

  http.get(`${API}/artifacts/:artifact_id`, async ({ params }) => {
    await simDelay();
    const artifact = getMockArtifact(params.artifact_id as string);
    if (!artifact) {
      return HttpResponse.json({ code: 'NOT_FOUND', message: 'Artifact 不存在', details: {}, trace_id: 'mock-006' } as ApiError, { status: 404 });
    }
    return HttpResponse.json(artifact);
  }),

  http.get(`${API}/artifacts/:artifact_id/tilejson`, async ({ params }) => {
    await simDelay();
    const artifact = getMockArtifact(params.artifact_id as string);
    if (!artifact) {
      return HttpResponse.json({ code: 'NOT_FOUND', message: 'Artifact 不存在', details: {}, trace_id: 'mock-007' } as ApiError, { status: 404 });
    }
    return HttpResponse.json({
      tilejson: '2.2.0',
      name: artifact.artifact_id,
      scheme: 'xyz',
      tiles: [artifact.tilejson_url || ''],
      minzoom: 10,
      maxzoom: 18,
      bounds: [106.45, 29.53, 106.65, 29.63],
    });
  }),

  // ── Map ──

  http.get(`${API}/map/candidates.geojson`, async () => {
    await simDelay();
    const features = mockCandidateListItems.map((c) => {
      const candidate = getMockCandidate(c.candidate_id);
      return {
        type: 'Feature',
        id: c.candidate_id,
        geometry: candidate?.representative_geometry || null,
        properties: {
          candidate_id: c.candidate_id,
          change_type: c.change_type,
          persistence_status: c.persistence_status,
          batch_rank: c.batch_rank,
        },
      };
    });
    return HttpResponse.json({ type: 'FeatureCollection', features });
  }),

  http.get(`${API}/map/events.geojson`, async () => {
    await simDelay();
    const features = getMockEvents().map((e) => {
      const candidate = getMockCandidate(e.candidate_id);
      return {
        type: 'Feature',
        id: e.event_id,
        geometry: candidate?.representative_geometry || null,
        properties: {
          event_id: e.event_id,
          title: e.title,
          status: e.status,
          event_type: e.event_type,
        },
      };
    });
    return HttpResponse.json({ type: 'FeatureCollection', features });
  }),

  // ── Summary ──

  http.get(`${API}/workbench/summary`, async () => {
    await simDelay();
    return HttpResponse.json({
      total_candidates: 36,
      persistent_count: 12,
      uncertain_count: 4,
      transient_count: 20,
      events_under_review: 1,
      events_confirmed: 1,
      total_runs: 2,
      last_run_at: '2026-06-10T08:45:00Z',
    });
  }),

  // ── 500 Error ──

  http.get(`${API}/error-test`, async () => {
    await simDelay();
    return HttpResponse.json({ code: 'SERVICE_ERROR', message: '服务内部错误', details: {}, trace_id: 'mock-500' } as ApiError, { status: 500 });
  }),
];
