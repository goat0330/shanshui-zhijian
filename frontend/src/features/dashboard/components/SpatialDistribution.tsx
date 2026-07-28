import { useQuery } from '@tanstack/react-query';
import { fetchDashboardSnapshot } from '@/shared/api/client';
import { Loading, ErrorState, EmptyState } from '@/shared/ui';

export default function SpatialDistribution() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard-snapshot'],
    queryFn: fetchDashboardSnapshot,
    select: (d) => d.change_types,
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorState message="变化类型数据加载失败" />;
  if (!data || data.length === 0) return <EmptyState message="暂无变化类型数据" />;

  const maxCount = Math.max(...data.map((d) => d.count));

  return (
    <div className="distribution-chart">
      {data.map((item) => {
        const pct = maxCount > 0 ? (item.count / maxCount) * 100 : 0;
        return (
          <div key={item.change_type} className="distribution-row">
            <span className="distribution-label">{item.label}</span>
            <div className="distribution-bar-wrapper">
              <div
                className="distribution-bar"
                style={{ width: `${pct}%`, backgroundColor: item.color }}
              />
            </div>
            <span className="distribution-count">{item.count}</span>
          </div>
        );
      })}
    </div>
  );
}
