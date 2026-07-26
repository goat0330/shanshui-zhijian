/* ============================================================
   山水智鉴 V0 — Candidate 卡片
   ============================================================ */

import type { CandidateListItem } from '@/shared/types';
import { useWorkbenchStore } from '@/app/store/workbench';

interface CandidateCardProps {
  candidate: CandidateListItem;
  isSelected: boolean;
}

export default function CandidateCard({ candidate, isSelected }: CandidateCardProps) {
  const setSelectedCandidateId = useWorkbenchStore((s) => s.setSelectedCandidateId);

  const statusColor = {
    persistent: 'var(--color-candidate-persistent)',
    transient: 'var(--color-candidate-transient)',
    uncertain: 'var(--color-candidate-uncertain)',
  }[candidate.persistence_status];

  const statusLabel = {
    persistent: '持久性',
    transient: '瞬态',
    uncertain: '不确定',
  }[candidate.persistence_status];

  const changeTypeLabel = candidate.change_type
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase());

  return (
    <div
      className={`candidate-card ${isSelected ? 'candidate-card--selected' : ''}`}
      onClick={() => setSelectedCandidateId(candidate.candidate_id)}
      role="button"
      tabIndex={0}
      style={{
        padding: 'var(--spacing-md)',
        border: `1px solid ${isSelected ? 'var(--color-primary)' : 'var(--color-border)'}`,
        borderLeft: `3px solid ${statusColor}`,
        borderRadius: 'var(--radius-md)',
        cursor: 'pointer',
        background: isSelected ? 'var(--color-primary-light)' : 'var(--color-surface)',
        marginBottom: 'var(--spacing-xs)',
        transition: 'background 0.15s',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--spacing-xs)' }}>
        <span className="text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>{changeTypeLabel}</span>
        <span style={{
          fontSize: 'var(--font-size-xs)',
          padding: '1px 6px',
          borderRadius: 'var(--radius-sm)',
          background: `${statusColor}20`,
          color: statusColor,
          fontWeight: 500,
        }}>{statusLabel}</span>
      </div>

      <div style={{ display: 'flex', gap: 'var(--spacing-md)', marginBottom: 'var(--spacing-xs)' }}>
        <div>
          <div className="text-xs text-muted">排名</div>
          <div className="text-sm font-medium">{candidate.batch_rank}</div>
        </div>
        <div>
          <div className="text-xs text-muted">面积</div>
          <div className="text-sm font-medium">{(candidate.area_m2 / 10000).toFixed(1)}ha</div>
        </div>
        <div>
          <div className="text-xs text-muted">次数</div>
          <div className="text-sm font-medium">{candidate.occurrence_count}</div>
        </div>
        <div>
          <div className="text-xs text-muted">持久性</div>
          <div className="text-sm font-medium">{(candidate.persistence_ratio * 100).toFixed(0)}%</div>
        </div>
      </div>

      <div className="text-xs text-muted">
        {candidate.candidate_id}
      </div>
    </div>
  );
}
