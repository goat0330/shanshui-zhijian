/* ============================================================
    山水智鉴 V0 — 态势卡片组件 (Dashboard)
    ============================================================ */

import { useQuery } from '@tanstack/react-query';
import { fetchDashboardSummary } from '@/shared/api/client';
import { Loading, ErrorState } from '@/shared/ui';

interface CardDef {
  key: string;
  label: string;
  value: number | string;
  unit?: string;
  color: string;
  icon: string;
}

export default function SituationCards() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: fetchDashboardSummary,
  });

  if (isLoading) return <div className="dashboard-section"><Loading /></div>;
  if (error || !data) return <div className="dashboard-section"><ErrorState message="态势数据加载失败" /></div>;

  const cards: CardDef[] = [
    { key: 'candidates', label: '异常候选', value: data.total_candidates, unit: '个', color: 'var(--color-primary)', icon: '🔍' },
    { key: 'persistent', label: '持久性异常', value: data.persistent_count, unit: '个', color: 'var(--color-candidate-persistent)', icon: '🔴' },
    { key: 'transient', label: '瞬态异常', value: data.transient_count, unit: '个', color: 'var(--color-candidate-transient)', icon: '🟠' },
    { key: 'events-review', label: '待研判事件', value: data.events_under_review, unit: '件', color: 'var(--color-event-review)', icon: '📋' },
    { key: 'events-confirmed', label: '已确认事件', value: data.events_confirmed, unit: '件', color: 'var(--color-event-confirmed)', icon: '✅' },
    { key: 'area', label: '监测范围', value: data.monitoring_area_km2.toFixed(1), unit: 'km²', color: 'var(--color-info)', icon: '🗺️' },
  ];

  return (
    <section className="dashboard-section">
      <div className="situation-cards">
        {cards.map((card) => (
          <div key={card.key} className="situation-card" style={{ borderTopColor: card.color }}>
            <div className="situation-card-header">
              <span className="situation-card-icon">{card.icon}</span>
              <span className="situation-card-label">{card.label}</span>
            </div>
            <div className="situation-card-value">
              {card.value}
              {card.unit && <span className="situation-card-unit">{card.unit}</span>}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
