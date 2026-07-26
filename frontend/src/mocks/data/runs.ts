/* ============================================================
   山水智鉴 V0 — Mock Run Data
   ============================================================ */

import type { RunDTO } from '@/shared/types';

const mockRuns: RunDTO[] = [
  {
    run_id: 'RUN-2026-001',
    task_id: 'RS-01B',
    task_spec_ref: 'rs01b2_multi_temporal_robust_background',
    git_commit: 'a1b2c3d4e5f6789012345678abcdef9012345678',
    git_branch: 'feature/rs-pipeline',
    git_dirty: false,
    started_at: '2026-05-30T08:00:00Z',
    finished_at: '2026-05-30T10:30:00Z',
    execution_status: 'completed',
    input_assets: ['S2-20260501-L2A', 'S2-20260515-L2A', 'S2-20260530-L2A'],
    metadata_sources: ['copernicus-dataspace'],
    config_hash: 'sha256:cfg-v1-abc123',
    output_artifacts: [
      { artifact_id: 'ART-CAND-001', asset_type: 'candidate_geojson', file_path: '/data/products/candidates.geojson', sha256: 'def456...', size_bytes: 1024000 },
      { artifact_id: 'ART-MASK-001', asset_type: 'persistent_mask', file_path: '/data/products/persistent_mask.tif', sha256: 'ghi789...', size_bytes: 5120000 },
      { artifact_id: 'ART-CHANGE', asset_type: 'change_vector', file_path: '/data/products/change.gpkg', sha256: 'jkl012...', size_bytes: 2048000 },
    ],
    failure_stage: null,
    candidate_counts: { persistent: 8, transient: 15, uncertain: 3 },
  },
  {
    run_id: 'RUN-2026-002',
    task_id: 'RS-01A',
    task_spec_ref: 'rs01a_sar_temporal_change',
    git_commit: 'b2c3d4e5f6789012345678abcdef90123456789',
    git_branch: 'feature/agent-a-perception-candidate',
    git_dirty: true,
    started_at: '2026-06-10T06:00:00Z',
    finished_at: '2026-06-10T08:45:00Z',
    execution_status: 'completed',
    input_assets: ['S1-20260601-GRD', 'S1-20260605-GRD', 'S1-20260610-GRD'],
    metadata_sources: ['copernicus-dataspace'],
    config_hash: 'sha256:cfg-v2-def456',
    output_artifacts: [
      { artifact_id: 'ART-CAND-002', asset_type: 'candidate_geojson', file_path: '/data/products/candidates_v2.geojson', sha256: 'mno345...', size_bytes: 2048000 },
      { artifact_id: 'ART-SAR', asset_type: 'sar_anomaly', file_path: '/data/products/sar_anomaly.tif', sha256: 'pqr678...', size_bytes: 8192000 },
    ],
    failure_stage: null,
    candidate_counts: { persistent: 4, transient: 5, uncertain: 1 },
  },
];

export function getMockRuns(): RunDTO[] {
  return mockRuns;
}

export function getMockRun(id: string): RunDTO | undefined {
  return mockRuns.find((r) => r.run_id === id);
}
