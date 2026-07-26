/* ============================================================
   山水智鉴 V0 — 核心类型定义
   这些类型与 Workbench API DTO 一致
   最终版本应从 OpenAPI 生成
   ============================================================ */

// ── Candidate ──

export type ChangeType = string;
export type PersistenceStatus = 'persistent' | 'transient' | 'uncertain';

export interface GeoJSONGeometry {
  type: string;
  coordinates: any;
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: Array<{
    type: 'Feature';
    id?: string;
    geometry: GeoJSONGeometry | null;
    properties: Record<string, any>;
  }>;
}

export interface CandidateDTO {
  candidate_id: string;
  candidate_track_id: string;
  schema_version: string;
  change_type: ChangeType;
  persistence_status: PersistenceStatus;
  temporal_extent: [string, string];
  occurrence_count: number;
  persistence_ratio: number;
  representative_geometry: GeoJSONGeometry;
  union_geometry: GeoJSONGeometry;
  score: number;
  score_type: string;
  score_components: Record<string, number>;
  quality_summary: QualitySummary;
  observation_refs: string[];
  source_asset_refs: string[];
  rule_version: string;
  run_manifest_ref: string;
  within_run_ranking: number;
  batch_rank: number;
  area_m2: number;
  review_state: ReviewState | null;
}

export interface QualitySummary {
  overall: 'good' | 'fair' | 'poor';
  cloud_cover?: number;
  geometric_quality?: string;
  artifact_count?: number;
}

export interface CandidateListItem {
  candidate_id: string;
  change_type: ChangeType;
  persistence_status: PersistenceStatus;
  occurrence_count: number;
  persistence_ratio: number;
  within_run_ranking: number;
  batch_rank: number;
  area_m2: number;
  temporal_extent: [string, string];
  review_state: ReviewState | null;
}

// ── Evidence ──

export interface EvidenceDTO {
  evidence_id: string;
  evidence_type: string;
  source_modality: string;
  source_asset_ref: string;
  derived_asset_ref: string | null;
  captured_at: string;
  stance: 'supporting' | 'contradicting' | 'inconclusive';
  quality_summary: QualitySummary;
  provenance: string;
  unavailable_reason: string | null;
}

// ── Review ──

export type ReviewAction = 'confirm' | 'reject' | 'reclassify' | 'needs_more_evidence';
export type ReviewState = 'pending' | 'confirmed' | 'rejected' | 'needs_more_evidence';

export interface ReviewRequest {
  action: ReviewAction;
  category?: string;
  comment: string;
  evidence_refs: string[];
  actor_ref: string;
  base_version: number;
}

export interface ReviewDecision {
  review_id: string;
  candidate_id: string;
  action: ReviewAction;
  category: string | null;
  comment: string;
  evidence_refs: string[];
  actor_ref: string;
  base_version: number;
  reviewed_at: string;
}

// ── Event ──

export type EventStatus = 'under_review' | 'confirmed' | 'rejected' | 'needs_more_evidence';

export interface EventDTO {
  event_id: string;
  candidate_id: string;
  event_type: string;
  status: EventStatus;
  title: string;
  created_at: string;
  updated_at: string;
  versions: EventVersion[];
  timeline: ReplayEntry[];
}

export interface EventVersion {
  version: number;
  status: EventStatus;
  changed_by: string;
  changed_at: string;
  summary: string;
}

// ── Run ──

export interface RunDTO {
  run_id: string;
  task_id: string;
  task_spec_ref: string;
  git_commit: string;
  git_branch: string;
  git_dirty: boolean;
  started_at: string;
  finished_at: string | null;
  execution_status: 'running' | 'completed' | 'failed' | 'cancelled';
  input_assets: string[];
  metadata_sources: string[];
  config_hash: string;
  output_artifacts: ArtifactRef[];
  failure_stage: string | null;
  candidate_counts: Record<PersistenceStatus, number>;
}

export interface ArtifactRef {
  artifact_id: string;
  asset_type: string;
  file_path: string;
  sha256: string;
  size_bytes: number;
}

// ── Artifact ──

export interface ArtifactDTO {
  artifact_id: string;
  run_id: string;
  asset_type: string;
  file_path: string;
  sha256: string;
  size_bytes: number;
  cog_url: string | null;
  tilejson_url: string | null;
  metadata: Record<string, unknown>;
}

// ── Replay ──

export interface ReplayEntry {
  replay_id: string;
  event_id: string;
  operation_type: string;
  timestamp: string;
  actor: string;
  before_state: Record<string, unknown>;
  after_state: Record<string, unknown>;
  details: Record<string, unknown>;
}

// ── Map ──

export const LAYER_GROUPS = ['basemap', 'sar', 'change', 'mask', 'vector'] as const;
export type LayerGroup = (typeof LAYER_GROUPS)[number];
export type LayerType = 'raster' | 'vector' | 'mask' | 'candidate' | 'event';
export type SourceType = 'tilejson' | 'geojson' | 'cog';

export interface LegendItem {
  label: string;
  color: string;
  value?: number | string;
}

export interface LayerLegend {
  type: 'gradient' | 'categorical' | 'single';
  items: LegendItem[];
}

export interface WorkbenchLayer {
  id: string;
  title: string;
  group: LayerGroup;
  layerType: LayerType;
  sourceType: SourceType;
  sourceUrl: string;
  visibleByDefault: boolean;
  opacity: number;
  zIndex: number;
  legend?: LayerLegend;
  temporalExtent?: [string, string];
  bounds?: [number, number, number, number];
  metadata?: Record<string, unknown>;
}

// ── API ──

export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    cursor: string | null;
    has_more: boolean;
    total: number;
  };
}

export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
  trace_id: string;
}

export interface CandidateFilters {
  limit?: number;
  cursor?: string;
  change_type?: string;
  persistence_status?: string;
  aoi_id?: string;
  run_id?: string;
  time_from?: string;
  time_to?: string;
  bbox?: string;
  sort?: string;
  include_transient?: boolean;
}

export interface EventFilters {
  limit?: number;
  cursor?: string;
  status?: EventStatus;
  change_type?: string;
  time_from?: string;
  time_to?: string;
}

export interface RunFilters {
  limit?: number;
  cursor?: string;
  execution_status?: string;
  time_from?: string;
  time_to?: string;
}

// ── GeoJSON ──

export type FeatureCollection = GeoJSONFeatureCollection;

// ── Compare Mode ──

export type CompareMode = 'none' | 'opacity' | 'split';

// ── Workbench Store ──

export interface MapViewport {
  center: [number, number];
  zoom: number;
  bounds?: [number, number, number, number];
}

export interface WorkbenchState {
  selectedCandidateId: string | null;
  viewport: MapViewport;
  compareMode: CompareMode;
  layerVisibility: Record<string, boolean>;
  layerOpacity: Record<string, number>;
  leftPanelOpen: boolean;
  rightPanelOpen: boolean;
}
