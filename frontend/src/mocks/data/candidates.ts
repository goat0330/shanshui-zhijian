/* ============================================================
   山水智鉴 V0 — Mock Candidate Data
   ============================================================ */

import type { CandidateDTO, CandidateListItem } from '@/shared/types';

const baseGeometry = {
  type: 'Polygon' as const,
  coordinates: [[[106.55, 29.56], [106.56, 29.56], [106.56, 29.57], [106.55, 29.57], [106.55, 29.56]]],
};

const geometries = [
  baseGeometry,
  { type: 'MultiPolygon' as const, coordinates: [[[[106.57, 29.55], [106.58, 29.55], [106.58, 29.56], [106.57, 29.56], [106.57, 29.55]]], [[[106.575, 29.555], [106.585, 29.555], [106.585, 29.565], [106.575, 29.565], [106.575, 29.555]]]] },
  { type: 'Polygon' as const, coordinates: [[[106.52, 29.58], [106.53, 29.58], [106.53, 29.59], [106.52, 29.59], [106.52, 29.58]]] },
  { type: 'Polygon' as const, coordinates: [[[106.60, 29.54], [106.61, 29.54], [106.61, 29.55], [106.60, 29.55], [106.60, 29.54]]] },
  { type: 'Polygon' as const, coordinates: [[[106.48, 29.57], [106.49, 29.57], [106.49, 29.58], [106.48, 29.58], [106.48, 29.57]]] },
  { type: 'Polygon' as const, coordinates: [[[106.62, 29.60], [106.63, 29.60], [106.63, 29.61], [106.62, 29.61], [106.62, 29.60]]] },
  { type: 'Polygon' as const, coordinates: [[[106.54, 29.53], [106.55, 29.53], [106.55, 29.54], [106.54, 29.54], [106.54, 29.53]]] },
  { type: 'Polygon' as const, coordinates: [[[106.58, 29.62], [106.59, 29.62], [106.59, 29.63], [106.58, 29.63], [106.58, 29.62]]] },
  { type: 'Polygon' as const, coordinates: [[[106.50, 29.55], [106.51, 29.55], [106.51, 29.56], [106.50, 29.56], [106.50, 29.55]]] },
  { type: 'Polygon' as const, coordinates: [[[106.64, 29.58], [106.65, 29.58], [106.65, 29.59], [106.64, 29.59], [106.64, 29.58]]] },
  { type: 'Polygon' as const, coordinates: [[[106.45, 29.60], [106.46, 29.60], [106.46, 29.61], [106.45, 29.61], [106.45, 29.60]]] },
  { type: 'Polygon' as const, coordinates: [[[106.59, 29.57], [106.60, 29.57], [106.60, 29.58], [106.59, 29.58], [106.59, 29.57]]] },
];

const changeTypes = [
  'water_extent_increase', 'water_extent_decrease', 'turbidity_anomaly',
  'algae_bloom', 'bank_collapse', 'suspected_discharge',
  'water_extent_increase', 'vegetation_change', 'water_extent_decrease',
  'sediment_anomaly', 'algae_bloom', 'bank_collapse',
];

function makeIds(prefix: string, count: number): string[] {
  return Array.from({ length: count }, (_, i) => `${prefix}-${String(i + 1).padStart(4, '0')}`);
}

const persistentIds = makeIds('CAND', 12);
const uncertainIds = makeIds('CAND-U', 4);
const transientIds = makeIds('CAND-T', 20);

function makeCandidate(id: string, persistence: 'persistent' | 'uncertain' | 'transient', idx: number): CandidateDTO {
  const area_m2 = Math.round(5000 + Math.random() * 95000);
  const occCount = persistence === 'transient' ? 1 : Math.floor(2 + Math.random() * 8);
  const score = Math.round((0.3 + Math.random() * 0.65) * 1000) / 1000;

  return {
    candidate_id: id,
    candidate_track_id: `TRACK-${id}`,
    schema_version: '1.0',
    change_type: changeTypes[idx % changeTypes.length],
    persistence_status: persistence,
    temporal_extent: ['2026-03-01T00:00:00Z', '2026-06-30T00:00:00Z'],
    occurrence_count: occCount,
    persistence_ratio: persistence === 'transient' ? 0.05 : Math.round((0.3 + Math.random() * 0.6) * 100) / 100,
    representative_geometry: geometries[idx % geometries.length],
    union_geometry: geometries[idx % geometries.length],
    score,
    score_type: 'sorting_score',
    score_components: {
      temporal_consistency: Math.round(Math.random() * 40),
      spectral_magnitude: Math.round(Math.random() * 30),
      spatial_coherence: Math.round(Math.random() * 20),
      prior_occurrence: Math.round(Math.random() * 10),
    },
    quality_summary: { overall: ['good', 'fair', 'poor'][idx % 3] as 'good' | 'fair' | 'poor' },
    observation_refs: [`OBS-${id}-1`, `OBS-${id}-2`],
    source_asset_refs: [`S2-${id}-A`, `S2-${id}-B`],
    rule_version: 'rs01b2',
    run_manifest_ref: 'RUN-2026-001',
    within_run_ranking: idx + 1,
    batch_rank: idx + 1,
    area_m2,
    review_state: null,
  };
}

// Build mock dataset
export const mockCandidates: CandidateDTO[] = [
  ...persistentIds.map((id, i) => makeCandidate(id, 'persistent', i)),
  ...uncertainIds.map((id, i) => makeCandidate(id, 'uncertain', i + 12)),
  ...transientIds.map((id, i) => makeCandidate(id, 'transient', i + 16)),
];

export const mockCandidateListItems: CandidateListItem[] = mockCandidates.map((c) => ({
  candidate_id: c.candidate_id,
  change_type: c.change_type,
  persistence_status: c.persistence_status,
  occurrence_count: c.occurrence_count,
  persistence_ratio: c.persistence_ratio,
  within_run_ranking: c.within_run_ranking,
  batch_rank: c.batch_rank,
  area_m2: c.area_m2,
  temporal_extent: c.temporal_extent,
  review_state: c.review_state,
}));

export function getMockCandidate(id: string): CandidateDTO | undefined {
  return mockCandidates.find((c) => c.candidate_id === id);
}
