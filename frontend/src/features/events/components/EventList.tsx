/* ============================================================
   山水智鉴 V0 — Event 列表
   ============================================================ */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { EventDTO, EventFilters, EventStatus } from '@/shared/types';
import EventDetail from './EventDetail';
import './EventList.css';

async function fetchEvents(filters: EventFilters): Promise<{ data: EventDTO[] }> {
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  const res = await fetch(`/api/v2/events?${params}`);
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

export default function EventList() {
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['events', { status: statusFilter }],
    queryFn: () => fetchEvents({ status: (statusFilter || undefined) as EventStatus | undefined }),
  });

  const statusLabels: Record<string, string> = {
    under_review: '研判任务',
    confirmed: '异常事件',
    rejected: '已驳回',
    needs_more_evidence: '待补证',
  };

  const statusColors: Record<string, string> = {
    under_review: 'var(--color-event-review)',
    confirmed: 'var(--color-event-confirmed)',
    rejected: 'var(--color-event-rejected)',
    needs_more_evidence: 'var(--color-event-more-evidence)',
  };

  const selectedEvent = data?.data?.find((e) => e.event_id === selectedEventId);

  return (
    <div className="event-center-layout">
      <div className="event-list-panel">
        <div className="event-list-controls">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="event-filter-select"
          >
            <option value="">全部状态</option>
            {Object.entries(statusLabels).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
          <span className="text-xs text-muted">{data?.data?.length ?? 0} 个事件</span>
        </div>

        <div className="event-list-items">
          {isLoading && <div className="event-list-empty text-muted">加载中...</div>}
          {error && <div className="event-list-empty" style={{ color: 'var(--color-error)' }}>加载失败</div>}
          {!isLoading && !error && data?.data?.length === 0 && (
            <div className="event-list-empty text-muted">无事件</div>
          )}
          {data?.data?.map((event) => (
            <div
              key={event.event_id}
              className={`event-card ${selectedEventId === event.event_id ? 'event-card--selected' : ''}`}
              onClick={() => setSelectedEventId(event.event_id)}
            >
              <div className="event-card-header">
                <span className="event-card-title">{event.title}</span>
                <span
                  className="event-card-status"
                  style={{
                    background: `${statusColors[event.status]}20`,
                    color: statusColors[event.status],
                  }}
                >
                  {statusLabels[event.status] || event.status}
                </span>
              </div>
              <div className="event-card-meta">
                <span className="text-xs text-muted">{event.event_id}</span>
                <span className="text-xs text-muted">{new Date(event.created_at).toLocaleDateString('zh-CN')}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {selectedEvent && (
        <div className="event-detail-panel">
          <EventDetail event={selectedEvent} />
        </div>
      )}
    </div>
  );
}
