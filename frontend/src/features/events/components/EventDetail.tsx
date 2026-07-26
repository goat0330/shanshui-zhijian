/* ============================================================
   山水智鉴 V0 — Event 详情
   ============================================================ */

import { useQuery } from '@tanstack/react-query';
import type { EventDTO, ReplayEntry } from '@/shared/types';
import ReplayTimeline from '@/features/replay/components/ReplayTimeline';

async function fetchReplay(eventId: string): Promise<ReplayEntry[]> {
  const res = await fetch(`/api/v2/events/${eventId}/replay`);
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

interface EventDetailProps {
  event: EventDTO;
}

export default function EventDetail({ event }: EventDetailProps) {
  const { data: replay } = useQuery({
    queryKey: ['replay', event.event_id],
    queryFn: () => fetchReplay(event.event_id),
  });

  const statusLabels: Record<string, string> = {
    under_review: '研判任务',
    confirmed: '异常事件',
    rejected: '已驳回',
    needs_more_evidence: '待补证',
  };

  return (
    <div className="event-detail" style={{ padding: '0 var(--spacing-lg)' }}>
      <h4 style={{ marginBottom: 'var(--spacing-lg)' }}>{event.title}</h4>

      <div className="detail-section">
        <h5 className="detail-section-title">基本信息</h5>
        <div className="detail-meta-grid">
          <div><span className="text-xs text-muted">Event ID</span><div className="text-sm">{event.event_id}</div></div>
          <div><span className="text-xs text-muted">状态</span><div className="text-sm">{statusLabels[event.status] || event.status}</div></div>
          <div><span className="text-xs text-muted">类型</span><div className="text-sm">{event.event_type}</div></div>
          <div><span className="text-xs text-muted">创建时间</span><div className="text-sm">{new Date(event.created_at).toLocaleString('zh-CN')}</div></div>
          <div><span className="text-xs text-muted">更新时间</span><div className="text-sm">{new Date(event.updated_at).toLocaleString('zh-CN')}</div></div>
          <div><span className="text-xs text-muted">来源 Candidate</span><div className="text-sm">{event.candidate_id}</div></div>
        </div>
      </div>

      <div className="detail-section">
        <h5 className="detail-section-title">版本历史</h5>
        {event.versions.map((v) => (
          <div key={v.version} style={{
            padding: 'var(--spacing-sm)',
            borderLeft: '2px solid var(--color-primary)',
            marginBottom: 'var(--spacing-xs)',
            marginLeft: 'var(--spacing-sm)',
          }}>
            <div style={{ display: 'flex', gap: 'var(--spacing-sm)', alignItems: 'center' }}>
              <span className="text-xs" style={{ fontWeight: 600 }}>v{v.version}</span>
              <span className="text-xs text-muted">{new Date(v.changed_at).toLocaleString('zh-CN')}</span>
            </div>
            <div className="text-sm">{v.summary}</div>
          </div>
        ))}
      </div>

      <div className="detail-section">
        <h5 className="detail-section-title">操作回放</h5>
        {replay && <ReplayTimeline entries={replay} />}
      </div>
    </div>
  );
}
