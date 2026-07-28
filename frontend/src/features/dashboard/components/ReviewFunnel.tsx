/* ============================================================
    山水智鉴 V0 — 研判漏斗组件 (Dashboard)
    展示研判流程各阶段数据流失
    ============================================================ */

import { useQuery } from '@tanstack/react-query';
import { fetchDashboardFunnel } from '@/shared/api/client';
import { Loading, ErrorState, EmptyState } from '@/shared/ui';

export default function ReviewFunnel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', 'funnel'],
    queryFn: fetchDashboardFunnel,
  });

  if (isLoading) return <div className="dashboard-chart"><Loading /></div>;
  if (error) return <div className="dashboard-chart"><ErrorState message="漏斗数据加载失败" /></div>;
  if (!data || data.length === 0) return <div className="dashboard-chart"><EmptyState message="暂无漏斗数据" /></div>;

  const maxCount = data[0]?.count ?? 1;

  return (
    <section className="dashboard-chart">
      <h4 className="dashboard-chart-title">研判处置漏斗</h4>
      <div className="funnel-container">
        {data.map((stage, idx) => {
          const pct = (stage.count / maxCount) * 100;
          const dropPct = idx > 0 && data[idx - 1].count > 0
            ? Math.round((1 - stage.count / data[idx - 1].count) * 100)
            : null;
          return (
            <div key={stage.stage} className="funnel-stage">
              <div className="funnel-bar-wrapper">
                <div
                  className="funnel-bar"
                  style={{ width: `${pct}%` }}
                >
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
    </section>
  );
}
