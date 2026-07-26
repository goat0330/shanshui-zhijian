/* ============================================================
   山水智鉴 V0 — 事件中心
   ============================================================ */

import EventList from '@/features/events/components/EventList';
import './index.css';

export default function EventCenterPage() {
  return (
    <div className="page-container">
      <div className="page-header">
        <h3>事件中心</h3>
        <span className="text-sm text-muted">研判任务 · 异常事件 · 已驳回 · 待补证</span>
      </div>
      <div className="page-content">
        <EventList />
      </div>
    </div>
  );
}
