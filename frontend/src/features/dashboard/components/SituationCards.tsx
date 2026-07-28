import { useQuery } from '@tanstack/react-query';
import { fetchDashboardSnapshot } from '@/shared/api/client';
import { Loading, ErrorState } from '@/shared/ui';

interface CardDef {
  key: string;
  label: string;
  value: number | string;
  unit?: string;
  color: string;
}

export default function SituationCards() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard-snapshot'],
    queryFn: fetchDashboardSnapshot,
  });

  if (isLoading) return <Loading />;
  if (error || !data) return <ErrorState message="态势数据加载失败" />;

  const s = data.summary;
  const cards: CardDef[] = [
    { key: 'candidates', label: '异常候选', value: s.total_candidates, unit: '个', color: 'var(--color-primary)' },
    { key: 'persistent', label: '持久性异常', value: s.persistent_count, unit: '个', color: 'var(--color-candidate-persistent)' },
    { key: 'transient', label: '瞬态异常', value: s.transient_count, unit: '个', color: 'var(--color-candidate-transient)' },
    { key: 'events-review', label: '待研判事件', value: s.events_under_review, unit: '件', color: 'var(--color-event-review)' },
    { key: 'events-confirmed', label: '已确认事件', value: s.events_confirmed, unit: '件', color: 'var(--color-event-confirmed)' },
    { key: 'area', label: '监测范围', value: s.monitoring_area_km2.toFixed(1), unit: 'km²', color: 'var(--color-info)' },
  ];

  return (
    <div className="situation-cards">
      {cards.map((card) => (
        <div key={card.key} className="situation-card" style={{ borderTopColor: card.color }}>
          <div className="situation-card-header">
            <span className="situation-card-label">{card.label}</span>
          </div>
          <div className="situation-card-value">
            {card.value}
            {card.unit && <span className="situation-card-unit">{card.unit}</span>}
          </div>
        </div>
      ))}
    </div>
  );
}
