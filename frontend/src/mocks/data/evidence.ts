/* ============================================================
   山水智鉴 V0 — Mock Evidence Data
   ============================================================ */

import type { EvidenceDTO } from '@/shared/types';

export function getMockEvidence(candidateId: string): EvidenceDTO[] {
  const baseEvidence: EvidenceDTO[] = [
    {
      evidence_id: `EVI-${candidateId}-1`,
      evidence_type: 'sentinel2_composite',
      source_modality: 'optical',
      source_asset_ref: `S2-${candidateId}-20260601`,
      derived_asset_ref: null,
      captured_at: '2026-06-01T03:30:00Z',
      stance: 'supporting',
      quality_summary: { overall: 'good', cloud_cover: 5 },
      provenance: 'sentinel-2 L2A → NDWI → Otsu threshold',
      unavailable_reason: null,
    },
    {
      evidence_id: `EVI-${candidateId}-2`,
      evidence_type: 'sar_intensity_change',
      source_modality: 'sar',
      source_asset_ref: `S1-${candidateId}-20260602`,
      derived_asset_ref: null,
      captured_at: '2026-06-02T10:15:00Z',
      stance: 'supporting',
      quality_summary: { overall: 'good' },
      provenance: 'sentinel-1 GRD → cal/TC → log ratio',
      unavailable_reason: null,
    },
    {
      evidence_id: `EVI-${candidateId}-3`,
      evidence_type: 'historical_comparison',
      source_modality: 'optical',
      source_asset_ref: `S2-${candidateId}-20260115`,
      derived_asset_ref: null,
      captured_at: '2026-01-15T03:25:00Z',
      stance: 'supporting',
      quality_summary: { overall: 'good', cloud_cover: 2 },
      provenance: 'sentinel-2 L2A → NDWI comparison vs baseline',
      unavailable_reason: null,
    },
  ];

  // Add an optical-unavailable case for some candidates
  if (candidateId.endsWith('5') || candidateId.endsWith('8')) {
    baseEvidence.push({
      evidence_id: `EVI-${candidateId}-4`,
      evidence_type: 'high_res_optical',
      source_modality: 'optical',
      source_asset_ref: `PL-${candidateId}-20260605`,
      derived_asset_ref: null,
      captured_at: '2026-06-05T03:45:00Z',
      stance: 'inconclusive',
      quality_summary: { overall: 'poor', cloud_cover: 85 },
      provenance: 'PlanetScope — cloud coverage too high',
      unavailable_reason: '云覆盖过高 (>80%)，光学证据不可用',
    });
  }

  // Contradicting evidence for uncertain candidates
  if (candidateId.endsWith('0') || candidateId.endsWith('3')) {
    baseEvidence.push({
      evidence_id: `EVI-${candidateId}-5`,
      evidence_type: 'field_report',
      source_modality: 'text',
      source_asset_ref: `FIELD-${candidateId}-20260610`,
      derived_asset_ref: null,
      captured_at: '2026-06-10T08:00:00Z',
      stance: 'contradicting',
      quality_summary: { overall: 'fair' },
      provenance: '巡查员现场报告',
      unavailable_reason: null,
    });
  }

  return baseEvidence;
}
