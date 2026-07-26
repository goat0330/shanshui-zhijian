/* ============================================================
   山水智鉴 V0 — Run 列表
   ============================================================ */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { RunDTO, RunFilters } from '@/shared/types';
import RunDetail from './RunDetail';
import './RunList.css';

async function fetchRuns(filters: RunFilters): Promise<{ data: RunDTO[] }> {
  const params = new URLSearchParams();
  if (filters.execution_status) params.set('execution_status', filters.execution_status);
  const res = await fetch(`/api/v2/runs?${params}`);
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

export default function RunList() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['runs'],
    queryFn: () => fetchRuns({}),
  });

  const statusColors: Record<string, string> = {
    completed: 'var(--color-success)',
    failed: 'var(--color-error)',
    running: 'var(--color-info)',
    cancelled: 'var(--color-text-muted)',
  };

  const selectedRun = data?.data?.find((r) => r.run_id === selectedRunId);

  return (
    <div className="run-center-layout">
      <div className="run-list-panel">
        <div className="run-list-items">
          {isLoading && <div className="run-list-empty text-muted">加载中...</div>}
          {error && <div className="run-list-empty" style={{ color: 'var(--color-error)' }}>加载失败</div>}
          {!isLoading && !error && data?.data?.length === 0 && (
            <div className="run-list-empty text-muted">无运行记录</div>
          )}
          {data?.data?.map((run) => (
            <div
              key={run.run_id}
              className={`run-card ${selectedRunId === run.run_id ? 'run-card--selected' : ''}`}
              onClick={() => setSelectedRunId(run.run_id)}
            >
              <div className="run-card-header">
                <span className="run-card-id">{run.run_id}</span>
                <span className="run-card-status" style={{ color: statusColors[run.execution_status] }}>
                  {run.execution_status}
                </span>
              </div>
              <div className="run-card-task text-xs text-muted">{run.task_spec_ref}</div>
              <div className="run-card-meta text-xs text-muted">
                <span>{run.git_branch}</span>
                <span>{new Date(run.started_at).toLocaleString('zh-CN')}</span>
              </div>
              {run.candidate_counts && (
                <div className="run-card-counts text-xs text-muted">
                  P: {run.candidate_counts.persistent} | T: {run.candidate_counts.transient} | U: {run.candidate_counts.uncertain}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {selectedRun && (
        <div className="run-detail-panel">
          <RunDetail run={selectedRun} />
        </div>
      )}
    </div>
  );
}
