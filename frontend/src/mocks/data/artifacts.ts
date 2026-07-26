/* ============================================================
   山水智鉴 V0 — Mock Artifact Data
   ============================================================ */

import type { ArtifactDTO } from '@/shared/types';

const mockArtifacts: ArtifactDTO[] = [
  {
    artifact_id: 'ART-CAND-001',
    run_id: 'RUN-2026-001',
    asset_type: 'candidate_geojson',
    file_path: '/data/products/candidates.geojson',
    sha256: 'def456...',
    size_bytes: 1024000,
    cog_url: null,
    tilejson_url: null,
    metadata: { feature_count: 26, crs: 'EPSG:4326' },
  },
  {
    artifact_id: 'ART-MASK-001',
    run_id: 'RUN-2026-001',
    asset_type: 'persistent_mask',
    file_path: '/data/products/persistent_mask.tif',
    sha256: 'ghi789...',
    size_bytes: 5120000,
    cog_url: '/cog/persistent_mask.tif',
    tilejson_url: '/api/v1/cog/tilejson.json?url=/cog/persistent_mask.tif',
    metadata: { width: 512, height: 512, bands: 1, crs: 'EPSG:4326' },
  },
  {
    artifact_id: 'ART-SAR',
    run_id: 'RUN-2026-002',
    asset_type: 'sar_anomaly',
    file_path: '/data/products/sar_anomaly.tif',
    sha256: 'pqr678...',
    size_bytes: 8192000,
    cog_url: '/cog/sar_anomaly.tif',
    tilejson_url: '/api/v1/cog/tilejson.json?url=/cog/sar_anomaly.tif',
    metadata: { width: 256, height: 256, bands: 1, crs: 'EPSG:4326' },
  },
];

export function getMockArtifact(id: string): ArtifactDTO | undefined {
  return mockArtifacts.find((a) => a.artifact_id === id);
}
