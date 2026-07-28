import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { fetchDashboardSnapshot } from '@/shared/api/client';
import { Loading, ErrorState, EmptyState } from '@/shared/ui';

const statusLabels: Record<string, string> = {
  confirmed: '已确认',
  under_review: '研判中',
  needs_more_evidence: '待补证',
  rejected: '已驳回',
};

const statusColors: Record<string, string> = {
  confirmed: 'var(--color-event-confirmed)',
  under_review: 'var(--color-event-review)',
  needs_more_evidence: 'var(--color-event-more-evidence)',
  rejected: 'var(--color-text-muted)',
};

export default function TypicalCases() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard-snapshot'],
    queryFn: fetchDashboardSnapshot,
    select: (d) => d.typical_cases,
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorState message="典型案例加载失败" />;
  if (!data || data.length === 0) return <EmptyState message="暂无典型案例" />;

  const formatArea = (m2: number): string => {
    if (m2 >= 10000) return `${(m2 / 10000).toFixed(1)} ha`;
    return `${m2.toLocaleString()} m²`;
  };

  const handleClick = (candidateId?: string) => {
    if (candidateId) {
      navigate(`/workbench?candidate_id=${candidateId}`);
    }
  };

  return (
    <div className="typical-cases-list">
      {data.map((c) => (
        <div key={c.id} className="typical-case-card" onClick={() => handleClick(c.candidate_id)}>
          <div className="typical-case-header">
            <span className="typical-case-title">{c.title}</span>
            <span className="typical-case-badge" style={{ backgroundColor: statusColors[c.status] || 'var(--color-text-muted)' }}>
              {statusLabels[c.status] || c.status}
            </span>
          </div>
          <div className="typical-case-tags">
            <span className="typical-case-tag">{c.change_type_label}</span>
            <span className="typical-case-tag">{formatArea(c.area_m2)}</span>
            <span className="typical-case-tag">{c.detected_at}</span>
          </div>
          <p className="typical-case-summary">{c.summary}</p>
        </div>
      ))}
    </div>
  );
}
