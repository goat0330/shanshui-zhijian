/* ============================================================
   山水智鉴 V0 — Mock Review Data
   ============================================================ */

import type { ReviewDecision } from '@/shared/types';

const mockReviews: ReviewDecision[] = [
  {
    review_id: 'REV-001',
    candidate_id: 'CAND-001',
    action: 'confirm',
    category: 'water_extent_increase',
    comment: '光学和 SAR 证据一致，确认为水体扩展',
    evidence_refs: ['EVI-CAND-001-1', 'EVI-CAND-001-2', 'EVI-CAND-001-3'],
    actor_ref: 'user-001',
    base_version: 1,
    reviewed_at: '2026-06-05T14:30:00Z',
  },
  {
    review_id: 'REV-003',
    candidate_id: 'CAND-005',
    action: 'needs_more_evidence',
    category: 'algae_bloom',
    comment: '光谱特征与藻类相似，但分辨率不足以确认',
    evidence_refs: ['EVI-CAND-005-1', 'EVI-CAND-005-2'],
    actor_ref: 'user-001',
    base_version: 1,
    reviewed_at: '2026-06-18T16:00:00Z',
  },
];

export function getMockReview(candidateId: string): ReviewDecision | undefined {
  return mockReviews.find((r) => r.candidate_id === candidateId);
}

export function addMockReview(review: ReviewDecision): void {
  const idx = mockReviews.findIndex((r) => r.candidate_id === review.candidate_id);
  if (idx >= 0) {
    mockReviews[idx] = review;
  } else {
    mockReviews.push(review);
  }
}
