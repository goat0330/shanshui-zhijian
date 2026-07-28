import { useQuery } from '@tanstack/react-query';
import { fetchDashboardSnapshot } from '@/shared/api/client';
import { Loading, ErrorState, EmptyState } from '@/shared/ui';

export default function ReviewFunnel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard-snapshot'],
    queryFn: fetchDashboardSnapshot,
    select: (d) => d.funnel,
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorState message="漏斗数据加载失败" />;
  if (!data || data.length === 0) return <EmptyState message="暂无漏斗数据" />;

  const maxCount = data[0]?.count ?? 1;

  return (
    <div className="funnel-container">
      {data.map((stage, idx) => {
        const pct = (stage.count / maxCount) * 100;
        const dropPct = idx > 0 && data[idx - 1].count > 0
          ? Math.round((1 - stage.count / data[idx - 1].count) * 100)
          : null;
        return (
          <div key={stage.stage} className="funnel-stage">
            <div className="funnel-bar-wrapper">
              <div className="funnel-bar" style={{ width: `${pct}%` }}>
                <span className="funnel-bar-label">{stage.count}</span>
              </div>
            </div>
            <div className="funnel-meta">
              <span className="funnel-stage-label">{stage.description}</span>
              {dropPct !== null && dropPct > 0 && (
                <span className="funnel-drop">↓ {dropPct}%</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
