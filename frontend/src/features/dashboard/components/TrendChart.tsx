/* ============================================================
    山水智鉴 V0 — 趋势图组件 (Dashboard)
    SVG 柱状图展示月度异常检测趋势
    ============================================================ */

import { useQuery } from '@tanstack/react-query';
import { fetchDashboardTrend } from '@/shared/api/client';
import { Loading, ErrorState, EmptyState } from '@/shared/ui';

export default function TrendChart() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', 'trend'],
    queryFn: fetchDashboardTrend,
  });

  if (isLoading) return <div className="dashboard-chart"><Loading /></div>;
  if (error) return <div className="dashboard-chart"><ErrorState message="趋势数据加载失败" /></div>;
  if (!data || data.length === 0) return <div className="dashboard-chart"><EmptyState message="暂无趋势数据" /></div>;

  const maxVal = Math.max(...data.map((d) => d.candidates));

  const CHART_WIDTH = 360;
  const CHART_HEIGHT = 180;
  const BAR_PADDING = 24;
  const barWidth = (CHART_WIDTH - BAR_PADDING * 2) / data.length - 8;
  const chartBottom = CHART_HEIGHT - 24;

  return (
    <section className="dashboard-chart">
      <h4 className="dashboard-chart-title">月度异常检测趋势</h4>
      <svg viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} className="trend-chart-svg" preserveAspectRatio="xMidYMid meet">
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
          const y = chartBottom - (ratio * (CHART_HEIGHT - 40));
          return (
            <line
              key={ratio}
              x1={BAR_PADDING}
              y1={y}
              x2={CHART_WIDTH - BAR_PADDING}
              y2={y}
              stroke="var(--color-border-light)"
              strokeWidth={1}
            />
          );
        })}
        {/* Bars */}
        {data.map((d, i) => {
          const x = BAR_PADDING + i * ((CHART_WIDTH - BAR_PADDING * 2) / data.length) + 4;
          const barH = maxVal > 0 ? (d.candidates / maxVal) * (CHART_HEIGHT - 44) : 0;
          const y = chartBottom - barH;
          return (
            <g key={d.month}>
              <rect x={x} y={y} width={barWidth} height={barH} rx={3} fill="var(--color-primary)" opacity={0.75}>
                <title>{d.label}: {d.candidates} 候选</title>
              </rect>
              {/* Confirmed marker */}
              {d.confirmed > 0 && (
                <circle cx={x + barWidth / 2} cy={y - 6} r={4} fill="var(--color-event-confirmed)">
                  <title>{d.label}: {d.confirmed} 确认</title>
                </circle>
              )}
              <text x={x + barWidth / 2} y={CHART_HEIGHT - 4} textAnchor="middle" fontSize={10} fill="var(--color-text-muted)">
                {d.label}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="trend-legend">
        <span className="trend-legend-item">
          <span className="trend-legend-dot" style={{ background: 'var(--color-primary)' }} />
          异常候选
        </span>
        <span className="trend-legend-item">
          <span className="trend-legend-dot" style={{ background: 'var(--color-event-confirmed)' }} />
          已确认事件
        </span>
      </div>
    </section>
  );
}
