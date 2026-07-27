/* ============================================================
    山水智鉴 V0 — 典型案例组件 (Dashboard)
    ============================================================ */

import { useQuery } from '@tanstack/react-query';
import { fetchDashboardTypicalCases } from '@/shared/api/client';
import { Loading, ErrorState, EmptyState } from '@/shared/ui';

const severityColors: Record<string, string> = {
  high: 'var(--color-error)',
  medium: 'var(--color-warning)',
  low: 'var(--color-text-muted)',
};

const severityLabels: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
};

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
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', 'typical-cases'],
    queryFn: fetchDashboardTypicalCases,
  });

  if (isLoading) return <div className="dashboard-section"><Loading /></div>;
  if (error) return <div className="dashboard-section"><ErrorState message="典型案例加载失败" /></div>;
  if (!data || data.length === 0) return <div className="dashboard-section"><EmptyState message="暂无典型案例" /></div>;

  const formatArea = (m2: number): string => {
    if (m2 >= 10000) return `${(m2 / 10000).toFixed(1)} ha`;
    return `${m2.toLocaleString()} m²`;
  };

  return (
    <section className="dashboard-section">
      <h4 className="dashboard-chart-title">典型案例</h4>
      <div className="typical-cases-list">
        {data.map((c) => (
          <div key={c.id} className="typical-case-card">
            <div className="typical-case-header">
              <span className="typical-case-title">{c.title}</span>
              <span
                className="typical-case-badge"
                style={{
                  backgroundColor: statusColors[c.status] || 'var(--color-text-muted)',
                }}
              >
                {statusLabels[c.status] || c.status}
              </span>
            </div>
            <div className="typical-case-tags">
              <span className="typical-case-tag">{c.change_type_label}</span>
              <span
                className="typical-case-tag typical-case-severity"
                style={{ borderColor: severityColors[c.severity], color: severityColors[c.severity] }}
              >
                {severityLabels[c.severity]} 优先级
              </span>
              <span className="typical-case-tag">{formatArea(c.area_m2)}</span>
              <span className="typical-case-tag">{c.detected_at}</span>
            </div>
            <p className="typical-case-summary">{c.summary}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
