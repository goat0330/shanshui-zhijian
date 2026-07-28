/* ============================================================
   山水智鉴 V0 — API Client
   共享 API 调用函数，所有数据获取通过此层
   ============================================================ */

import config from '@/app/config';
import type {
  CandidateDTO,
  CandidateListItem,
  CandidateFilters,
  EvidenceDTO,
  EventDTO,
  EventFilters,
  ReplayEntry,
  RunDTO,
  RunFilters,
  ArtifactDTO,
  ReviewRequest,
  ReviewDecision,
  PaginatedResponse,
} from '@/shared/types';

const BASE = config.apiBaseUrl;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ code: 'UNKNOWN', message: res.statusText }));
    throw { status: res.status, ...err };
  }
  return res.json();
}

// ── Candidates ──

export function fetchCandidates(filters: CandidateFilters = {}): Promise<PaginatedResponse<CandidateListItem>> {
  const params = new URLSearchParams();
  if (filters.limit) params.set('limit', String(filters.limit));
  if (filters.cursor) params.set('cursor', filters.cursor);
  if (filters.include_transient) params.set('include_transient', 'true');
  if (filters.persistence_status) params.set('persistence_status', filters.persistence_status);
  if (filters.change_type) params.set('change_type', filters.change_type);
  if (filters.run_id) params.set('run_id', filters.run_id);
  if (filters.sort) params.set('sort', filters.sort);
  if (filters.bbox) params.set('bbox', filters.bbox);
  if (filters.time_from) params.set('time_from', filters.time_from);
  if (filters.time_to) params.set('time_to', filters.time_to);
  return request(`/candidates?${params}`);
}

export function fetchCandidate(id: string): Promise<CandidateDTO> {
  return request(`/candidates/${id}`);
}

export function fetchEvidence(candidateId: string): Promise<EvidenceDTO[]> {
  return request(`/candidates/${candidateId}/evidence`);
}

export function fetchCandidateArtifacts(candidateId: string): Promise<ArtifactDTO[]> {
  return request(`/candidates/${candidateId}/artifacts`);
}

export function submitReview(candidateId: string, data: ReviewRequest): Promise<ReviewDecision> {
  return request(`/candidates/${candidateId}/reviews`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ── Events ──

export function fetchEvents(filters: EventFilters = {}): Promise<PaginatedResponse<EventDTO>> {
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  if (filters.limit) params.set('limit', String(filters.limit));
  return request(`/events?${params}`);
}

export function fetchEvent(id: string): Promise<EventDTO> {
  return request(`/events/${id}`);
}

export function fetchEventVersions(eventId: string): Promise<EventDTO['versions']> {
  return request(`/events/${eventId}/versions`);
}

export function fetchReplay(eventId: string): Promise<ReplayEntry[]> {
  return request(`/events/${eventId}/replay`);
}

// ── Runs ──

export function fetchRuns(filters: RunFilters = {}): Promise<PaginatedResponse<RunDTO>> {
  const params = new URLSearchParams();
  if (filters.limit) params.set('limit', String(filters.limit));
  if (filters.execution_status) params.set('execution_status', filters.execution_status);
  return request(`/runs?${params}`);
}

export function fetchRun(id: string): Promise<RunDTO> {
  return request(`/runs/${id}`);
}

// ── Artifacts ──

export function fetchArtifact(id: string): Promise<ArtifactDTO> {
  return request(`/artifacts/${id}`);
}

export function fetchTileJSON(artifactId: string): Promise<{ tilejson: string; tiles: string[] }> {
  return request(`/artifacts/${artifactId}/tilejson`);
}

// ── Map ──

export function fetchCandidateGeoJSON(): Promise<import('@/shared/types').FeatureCollection> {
  return request('/map/candidates.geojson');
}

export function fetchEventGeoJSON(): Promise<import('@/shared/types').FeatureCollection> {
  return request('/map/events.geojson');
}

// ── Summary ──

export function fetchWorkbenchSummary(): Promise<{
  total_candidates: number;
  persistent_count: number;
  uncertain_count: number;
  transient_count: number;
  events_under_review: number;
  events_confirmed: number;
  total_runs: number;
  last_run_at: string;
}> {
  return request('/workbench/summary');
}

// ── Dashboard ──

export interface DashboardSnapshot {
  summary: DashboardSummary;
  change_types: ChangeTypeDistribution[];
  trend: MonthlyTrend[];
  funnel: ReviewFunnelStage[];
  typical_cases: TypicalCase[];
}

export interface DashboardSummary {
  total_candidates: number;
  persistent_count: number;
  uncertain_count: number;
  transient_count: number;
  events_under_review: number;
  events_confirmed: number;
  events_rejected: number;
  events_needs_evidence: number;
  total_runs: number;
  runs_completed: number;
  runs_failed: number;
  last_run_at: string;
  monitoring_area_km2: number;
}

export interface ChangeTypeDistribution {
  change_type: string;
  label: string;
  count: number;
  color: string;
}

export interface MonthlyTrend {
  month: string;
  label: string;
  candidates: number;
  confirmed: number;
}

export interface ReviewFunnelStage {
  stage: string;
  count: number;
  description: string;
}

export interface TypicalCase {
  id: string;
  title: string;
  change_type: string;
  change_type_label: string;
  status: string;
  status_label: string;
  area_m2: number;
  detected_at: string;
  summary: string;
}

export function fetchDashboardSnapshot(): Promise<DashboardSnapshot> {
  return request('/dashboard/snapshot');
}
