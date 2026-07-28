/* ============================================================
   山水智鉴 V0 — Replay 时间线
   ============================================================ */

import type { ReplayEntry } from '@/shared/types';
import './ReplayTimeline.css';

interface ReplayTimelineProps {
  entries: ReplayEntry[];
}

const operationLabels: Record<string, string> = {
  candidate_created: 'Candidate 创建',
  evidence_collected: '证据收集',
  review_confirm: '研判确认',
  review_reject: '研判驳回',
  review_needs_more_evidence: '研判需补证',
  event_status_changed: '事件状态变更',
};

export default function ReplayTimeline({ entries }: ReplayTimelineProps) {
  if (!entries || entries.length === 0) {
    return <div className="text-sm text-muted">无操作记录</div>;
  }

  return (
    <div className="replay-timeline">
      {entries.map((entry, i) => (
        <div key={entry.replay_id} className="replay-entry">
          <div className="replay-dot" />
          {i < entries.length - 1 && <div className="replay-line" />}
          <div className="replay-content">
            <div className="replay-header">
              <span className="replay-operation">{operationLabels[entry.operation_type] || entry.operation_type}</span>
              <span className="text-xs text-muted">
                {new Date(entry.timestamp).toLocaleString('zh-CN')}
              </span>
            </div>
            <div className="text-xs text-muted">操作人: {entry.actor}</div>
            {(entry.details?.comment as string | undefined) && (
              <div className="replay-comment">{String(entry.details.comment as string)}</div>
            )}
            {entry.after_state && Object.keys(entry.after_state).length > 0 && (
              <div className="replay-state-change text-xs">
                状态变更: {Object.entries(entry.after_state).map(([k, v]) => `${k}=${String(v)}`).join(', ')}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
