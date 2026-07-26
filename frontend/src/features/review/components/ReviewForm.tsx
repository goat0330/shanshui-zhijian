/* ============================================================
   山水智鉴 V0 — 研判表单
   ============================================================ */

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { ReviewAction, ReviewRequest, ReviewDecision } from '@/shared/types';
import './ReviewForm.css';

interface ReviewFormProps {
  candidateId: string;
}

async function submitReview(candidateId: string, data: ReviewRequest): Promise<ReviewDecision> {
  const res = await fetch(`/api/v2/candidates/${candidateId}/reviews`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json();
    throw { status: res.status, ...err };
  }
  return res.json();
}

export default function ReviewForm({ candidateId }: ReviewFormProps) {
  const [action, setAction] = useState<ReviewAction>('confirm');
  const [category, setCategory] = useState('');
  const [comment, setComment] = useState('');
  const [conflictMessage, setConflictMessage] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (data: ReviewRequest) => submitReview(candidateId, data),
    onSuccess: () => {
      setComment('');
      setConflictMessage(null);
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: ['candidate', candidateId] });
      queryClient.invalidateQueries({ queryKey: ['candidates'] });
      queryClient.invalidateQueries({ queryKey: ['events'] });
    },
    onError: (error: any) => {
      if (error?.status === 409) {
        setConflictMessage(`版本冲突: ${error?.message || '该 Candidate 已被其他人更新'}`);
      }
    },
  });

  const handleSubmit = () => {
    setConflictMessage(null);
    mutation.mutate({
      action,
      category: action === 'reclassify' ? category : undefined,
      comment,
      evidence_refs: [],
      actor_ref: 'user-001',
      base_version: 1,
    });
  };

  return (
    <div className="detail-section">
      <h5 className="detail-section-title">人工研判</h5>

      {conflictMessage && (
        <div className="review-conflict">
          <div className="review-conflict-message">{conflictMessage}</div>
          <button
            className="review-conflict-reload"
            onClick={() => queryClient.invalidateQueries({ queryKey: ['candidate', candidateId] })}
          >
            重新加载最新版本
          </button>
        </div>
      )}

      <div className="review-actions">
        {(['confirm', 'reject', 'reclassify', 'needs_more_evidence'] as ReviewAction[]).map((a) => (
          <button
            key={a}
            className={`review-action-btn ${action === a ? 'review-action-btn--active' : ''}`}
            onClick={() => setAction(a)}
          >
            {actionLabel(a)}
          </button>
        ))}
      </div>

      {action === 'reclassify' && (
        <input
          type="text"
          placeholder="输入新类别"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="review-input"
        />
      )}

      <textarea
        className="review-textarea"
        placeholder="研判意见（必填）"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        rows={3}
      />

      <button
        className="review-submit"
        onClick={handleSubmit}
        disabled={mutation.isPending || (!comment.trim())}
      >
        {mutation.isPending ? '提交中...' : `提交${actionLabel(action)}`}
      </button>

      {mutation.isSuccess && (
        <div className="review-success">✓ 研判成功</div>
      )}
    </div>
  );
}

function actionLabel(action: ReviewAction): string {
  const labels: Record<ReviewAction, string> = {
    confirm: '确认',
    reject: '驳回',
    reclassify: '重新分类',
    needs_more_evidence: '需补证',
  };
  return labels[action];
}
