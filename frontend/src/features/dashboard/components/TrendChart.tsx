import { useQuery } from '@tanstack/react-query';
import { fetchDashboardSnapshot } from '@/shared/api/client';
import { Loading, ErrorState, EmptyState } from '@/shared/ui';

const CHART_WIDTH = 260;
const CHART_HEIGHT = 130;
const BAR_PADDING = 16;
const CHART_BOTTOM = CHART_HEIGHT - 20;

export default function TrendChart() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard-snapshot'],
    queryFn: fetchDashboardSnapshot,
    select: (d) => d.trend,
  });

  if (isLoading) return <Loading />;
  if (error) return <ErrorState message="趋势数据加载失败" />;
  if (!data || data.length === 0) return <EmptyState message="暂无趋势数据" />;

  const maxVal = Math.max(...data.map((d) => d.candidates));
  const barWidth = (CHART_WIDTH - BAR_PADDING * 2) / data.length - 6;

  return (
    <div className="trend-chart">
      <svg viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} className="trend-chart-svg" preserveAspectRatio="xMidYMid meet">
        {[0, 0.5, 1].map((ratio) => {
          const y = CHART_BOTTOM - (ratio * (CHART_HEIGHT - 28));
          return (
            <line key={ratio} x1={BAR_PADDING} y1={y} x2={CHART_WIDTH - BAR_PADDING} y2={y} stroke="var(--color-border-light)" strokeWidth={1} />
          );
        })}
        {data.map((d, i) => {
          const x = BAR_PADDING + i * ((CHART_WIDTH - BAR_PADDING * 2) / data.length) + 3;
          const barH = maxVal > 0 ? (d.candidates / maxVal) * (CHART_HEIGHT - 36) : 0;
          const y = CHART_BOTTOM - barH;
          return (
            <g key={d.month}>
              <rect x={x} y={y} width={barWidth} height={barH} rx={2} fill="var(--color-primary)" opacity={0.75}>
                <title>{d.label}: {d.candidates} 候选</title>
              </rect>
              {d.confirmed > 0 && (
                <circle cx={x + barWidth / 2} cy={y - 4} r={3} fill="var(--color-event-confirmed)">
                  <title>{d.label}: {d.confirmed} 确认</title>
                </circle>
              )}
              <text x={x + barWidth / 2} y={CHART_HEIGHT - 3} textAnchor="middle" fontSize={8} fill="var(--color-text-muted)">{d.label}</text>
            </g>
          );
        })}
      </svg>
      <div className="trend-legend">
        <span className="trend-legend-item"><span className="trend-legend-dot" style={{ background: 'var(--color-primary)' }} />候选</span>
        <span className="trend-legend-item"><span className="trend-legend-dot" style={{ background: 'var(--color-event-confirmed)' }} />确认</span>
      </div>
    </div>
  );
}
