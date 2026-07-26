/* ============================================================
   山水智鉴 V0 — Candidate 列表
   ============================================================ */

import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useWorkbenchStore } from '@/app/store/workbench';
import type { CandidateListItem, CandidateFilters } from '@/shared/types';
import CandidateCard from './CandidateCard';
import './CandidateList.css';

async function fetchCandidates(filters: CandidateFilters): Promise<{ data: CandidateListItem[] }> {
  const params = new URLSearchParams();
  if (filters.include_transient) params.set('include_transient', 'true');
  if (filters.persistence_status) params.set('persistence_status', filters.persistence_status);
  if (filters.change_type) params.set('change_type', filters.change_type);
  if (filters.sort) params.set('sort', filters.sort);
  if (filters.limit) params.set('limit', String(filters.limit));

  const res = await fetch(`/api/v2/candidates?${params}`);
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

export default function CandidateList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedCandidateId = useWorkbenchStore((s) => s.selectedCandidateId);
  const [includeTransient, setIncludeTransient] = useState(searchParams.get('include_transient') === 'true');
  const [sort, setSort] = useState(searchParams.get('sort') || 'score');

  const filters: CandidateFilters = {
    include_transient: includeTransient,
    sort,
    limit: 20,
  };

  const { data, isLoading, error } = useQuery({
    queryKey: ['candidates', filters],
    queryFn: () => fetchCandidates(filters),
  });

  const handleToggleTransient = () => {
    const next = !includeTransient;
    setIncludeTransient(next);
    setSearchParams((prev) => {
      if (next) prev.set('include_transient', 'true');
      else prev.delete('include_transient');
      return prev;
    });
  };

  return (
    <div className="candidate-list">
      <div className="candidate-list-header">
        <h4 className="candidate-list-title">Candidate 队列</h4>
        <span className="text-xs text-muted">{data?.data?.length ?? 0} 个</span>
      </div>

      <div className="candidate-list-controls">
        <label className="transient-toggle" style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer', fontSize: 'var(--font-size-sm)' }}>
          <input type="checkbox" checked={includeTransient} onChange={handleToggleTransient} />
          显示瞬态
        </label>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          style={{ fontSize: 'var(--font-size-sm)', padding: '2px 4px', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)' }}
        >
          <option value="score">按排序分</option>
          <option value="area">按面积</option>
          <option value="occurrence_count">按次数</option>
        </select>
      </div>

      <div className="candidate-list-items">
        {isLoading && (
          <div className="candidate-list-empty">
            <span className="text-muted">加载中...</span>
          </div>
        )}
        {error && (
          <div className="candidate-list-empty">
            <span style={{ color: 'var(--color-error)' }}>加载失败: {(error as Error).message}</span>
          </div>
        )}
        {!isLoading && !error && data?.data?.length === 0 && (
          <div className="candidate-list-empty">
            <span className="text-muted">无待核验 Candidate</span>
          </div>
        )}
        {!isLoading && !error && data?.data?.map((candidate) => (
          <CandidateCard
            key={candidate.candidate_id}
            candidate={candidate}
            isSelected={selectedCandidateId === candidate.candidate_id}
          />
        ))}
      </div>
    </div>
  );
}
