/* ============================================================
    山水智鉴 V0 — 空间分布组件 (Dashboard)
    显示异常候选的变化类型分布条形图（纯 CSS）
    ============================================================ */

import { useQuery } from '@tanstack/react-query';
import { fetchDashboardChangeTypes } from '@/shared/api/client';
import { Loading, ErrorState, EmptyState } from '@/shared/ui';

export default function SpatialDistribution() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', 'change-types'],
    queryFn: fetchDashboardChangeTypes,
  });

  if (isLoading) return <div className="dashboard-chart"><Loading /></div>;
  if (error) return <div className="dashboard-chart"><ErrorState message="变化类型数据加载失败" /></div>;
  if (!data || data.length === 0) return <div className="dashboard-chart"><EmptyState message="暂无变化类型数据" /></div>;

  const maxCount = Math.max(...data.map((d) => d.count));

  return (
    <section className="dashboard-chart">
      <h4 className="dashboard-chart-title">异常候选 — 变化类型分布</h4>
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
    </section>
  );
}
