/* ============================================================
   山水智鉴 V0 — 证据面板
   ============================================================ */

import { useQuery } from '@tanstack/react-query';
import type { EvidenceDTO } from '@/shared/types';
import './EvidencePanel.css';

async function fetchEvidence(candidateId: string): Promise<EvidenceDTO[]> {
  const res = await fetch(`/api/v2/candidates/${candidateId}/evidence`);
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

interface EvidencePanelProps {
  candidateId: string;
}

const stanceColors: Record<string, string> = {
  supporting: '#2e7d32',
  contradicting: '#c62828',
  inconclusive: '#f57c00',
};

const stanceLabels: Record<string, string> = {
  supporting: '支持',
  contradicting: '反对',
  inconclusive: '不确定',
};

export default function EvidencePanel({ candidateId }: EvidencePanelProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['evidence', candidateId],
    queryFn: () => fetchEvidence(candidateId),
  });

  return (
    <div className="detail-section">
      <h5 className="detail-section-title">证据</h5>
      {isLoading && <div className="text-sm text-muted">加载证据...</div>}
      {!isLoading && (!data || data.length === 0) && (
        <div className="text-sm text-muted">无可用证据</div>
      )}
      {data?.map((evidence) => (
        <div key={evidence.evidence_id} className="evidence-item">
          <div className="evidence-header">
            <span className="evidence-modal">{evidence.source_modality}</span>
            <span className="evidence-stance" style={{ background: `${stanceColors[evidence.stance]}20`, color: stanceColors[evidence.stance] }}>
              {stanceLabels[evidence.stance]}
            </span>
          </div>
          <div className="evidence-type text-xs text-muted">{evidence.evidence_type}</div>
          <div className="evidence-time text-xs text-muted">
            {new Date(evidence.captured_at).toLocaleDateString('zh-CN')}
          </div>
          <div className="evidence-quality text-xs">
            质量: {evidence.quality_summary.overall}
            {evidence.quality_summary.cloud_cover !== undefined && ` | 云量: ${evidence.quality_summary.cloud_cover}%`}
          </div>
          <div className="text-xs" style={{ color: 'var(--color-text-secondary)', marginTop: 2 }}>
            {evidence.provenance}
          </div>
          {evidence.unavailable_reason && (
            <div className="evidence-unavailable">
              ⚠ {evidence.unavailable_reason}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
