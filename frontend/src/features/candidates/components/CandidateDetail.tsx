/* ============================================================
   山水智鉴 V0 — Candidate 详情
   ============================================================ */

import { useQuery } from '@tanstack/react-query';
import type { CandidateDTO } from '@/shared/types';
import EvidencePanel from '@/features/evidence/components/EvidencePanel';
import ReviewForm from '@/features/review/components/ReviewForm';
import './CandidateDetail.css';

async function fetchCandidate(id: string): Promise<CandidateDTO> {
  const res = await fetch(`/api/v2/candidates/${id}`);
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

interface CandidateDetailProps {
  candidateId: string;
}

export default function CandidateDetail({ candidateId }: CandidateDetailProps) {
  const { data: candidate, isLoading, error } = useQuery({
    queryKey: ['candidate', candidateId],
    queryFn: () => fetchCandidate(candidateId),
  });

  if (isLoading) {
    return <div className="detail-loading"><span className="text-muted">加载详情...</span></div>;
  }

  if (error || !candidate) {
    return (
      <div className="detail-loading">
        <span style={{ color: 'var(--color-error)' }}>加载失败</span>
      </div>
    );
  }

  const statusColor = {
    persistent: 'var(--color-candidate-persistent)',
    transient: 'var(--color-candidate-transient)',
    uncertain: 'var(--color-candidate-uncertain)',
  }[candidate.persistence_status];

  return (
    <div className="candidate-detail">
      <div className="detail-section">
        <h4 className="detail-section-title">{candidate.candidate_id}</h4>
        <div className="detail-status-row">
          <span className="detail-badge" style={{ background: `${statusColor}20`, color: statusColor }}>
            {candidate.persistence_status}
          </span>
          <span className="text-sm">{candidate.change_type.replace(/_/g, ' ')}</span>
        </div>
      </div>

      {/* Score - MUST use correct label */}
      <div className="detail-section">
        <h5 className="detail-section-title">排序评估</h5>
        <div className="detail-score-label">
          本次运行排序分：<strong>{candidate.score.toFixed(3)}</strong>
        </div>
        <div className="detail-score-label">
          本批候选排名：<strong>{candidate.batch_rank}</strong>
        </div>
        <div className="score-breakdown">
          <div className="score-component">
            <span className="text-xs text-muted">时间一致性</span>
            <div className="score-bar-track">
              <div className="score-bar-fill" style={{ width: `${candidate.score_components.temporal_consistency}%` }} />
            </div>
          </div>
          <div className="score-component">
            <span className="text-xs text-muted">光谱幅度</span>
            <div className="score-bar-track">
              <div className="score-bar-fill" style={{ width: `${candidate.score_components.spectral_magnitude}%` }} />
            </div>
          </div>
          <div className="score-component">
            <span className="text-xs text-muted">空间一致性</span>
            <div className="score-bar-track">
              <div className="score-bar-fill" style={{ width: `${candidate.score_components.spatial_coherence}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* Metadata */}
      <div className="detail-section">
        <h5 className="detail-section-title">基础信息</h5>
        <div className="detail-meta-grid">
          <div><span className="text-xs text-muted">面积</span><div className="text-sm">{(candidate.area_m2 / 10000).toFixed(2)} ha</div></div>
          <div><span className="text-xs text-muted">发生次数</span><div className="text-sm">{candidate.occurrence_count}</div></div>
          <div><span className="text-xs text-muted">持久性比率</span><div className="text-sm">{(candidate.persistence_ratio * 100).toFixed(1)}%</div></div>
          <div><span className="text-xs text-muted">质量</span><div className="text-sm">{candidate.quality_summary.overall}</div></div>
          <div><span className="text-xs text-muted">规则版本</span><div className="text-sm">{candidate.rule_version}</div></div>
          <div><span className="text-xs text-muted">Schema</span><div className="text-sm">{candidate.schema_version}</div></div>
        </div>
      </div>

      {/* Evidence */}
      <EvidencePanel candidateId={candidateId} />

      {/* Review */}
      <ReviewForm candidateId={candidateId} />
    </div>
  );
}
