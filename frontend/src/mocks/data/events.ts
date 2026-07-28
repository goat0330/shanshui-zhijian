/* ============================================================
   山水智鉴 V0 — Mock Event Data
   ============================================================ */

import type { EventDTO, ReplayEntry } from '@/shared/types';

const mockEvents: EventDTO[] = [
  {
    event_id: 'EVT-2026-001',
    candidate_id: 'CAND-0001',
    event_type: 'water_extent_increase',
    status: 'confirmed',
    title: '长江支流 A 段水面异常扩展',
    created_at: '2026-06-01T10:00:00Z',
    updated_at: '2026-06-05T14:30:00Z',
    versions: [
      { version: 1, status: 'under_review', changed_by: 'system', changed_at: '2026-06-01T10:00:00Z', summary: 'Candidate 创建' },
      { version: 2, status: 'confirmed', changed_by: 'user-001', changed_at: '2026-06-05T14:30:00Z', summary: '人工确认 — 证据充分' },
    ],
    timeline: [
      { replay_id: 'RPL-001', event_id: 'EVT-2026-001', operation_type: 'candidate_created', timestamp: '2026-06-01T10:00:00Z', actor: 'system', before_state: {}, after_state: { status: 'under_review' }, details: { run_id: 'RUN-2026-001' } },
      { replay_id: 'RPL-002', event_id: 'EVT-2026-001', operation_type: 'evidence_collected', timestamp: '2026-06-02T08:00:00Z', actor: 'system', before_state: {}, after_state: { evidence_count: 3 }, details: { modalities: ['optical', 'sar'] } },
      { replay_id: 'RPL-003', event_id: 'EVT-2026-001', operation_type: 'review_confirm', timestamp: '2026-06-05T14:30:00Z', actor: 'user-001', before_state: { status: 'under_review' }, after_state: { status: 'confirmed' }, details: { comment: '光学和 SAR 证据一致，确认为水体扩展' } },
    ],
  },
  {
    event_id: 'EVT-2026-002',
    candidate_id: 'CAND-0003',
    event_type: 'turbidity_anomaly',
    status: 'under_review',
    title: 'B 河流域浑浊度异常',
    created_at: '2026-06-10T09:00:00Z',
    updated_at: '2026-06-10T09:00:00Z',
    versions: [
      { version: 1, status: 'under_review', changed_by: 'system', changed_at: '2026-06-10T09:00:00Z', summary: 'Candidate 创建 — 等待人工研判' },
    ],
    timeline: [
      { replay_id: 'RPL-004', event_id: 'EVT-2026-002', operation_type: 'candidate_created', timestamp: '2026-06-10T09:00:00Z', actor: 'system', before_state: {}, after_state: { status: 'under_review' }, details: { run_id: 'RUN-2026-001' } },
    ],
  },
  {
    event_id: 'EVT-2026-003',
    candidate_id: 'CAND-0005',
    event_type: 'algae_bloom',
    status: 'needs_more_evidence',
    title: 'C 水库疑似藻类爆发',
    created_at: '2026-06-15T11:00:00Z',
    updated_at: '2026-06-18T16:00:00Z',
    versions: [
      { version: 1, status: 'under_review', changed_by: 'system', changed_at: '2026-06-15T11:00:00Z', summary: 'Candidate 创建' },
      { version: 2, status: 'needs_more_evidence', changed_by: 'user-001', changed_at: '2026-06-18T16:00:00Z', summary: '需要补充高分辨率光学证据确认' },
    ],
    timeline: [
      { replay_id: 'RPL-005', event_id: 'EVT-2026-003', operation_type: 'candidate_created', timestamp: '2026-06-15T11:00:00Z', actor: 'system', before_state: {}, after_state: { status: 'under_review' }, details: { run_id: 'RUN-2026-002' } },
      { replay_id: 'RPL-006', event_id: 'EVT-2026-003', operation_type: 'review_needs_more_evidence', timestamp: '2026-06-18T16:00:00Z', actor: 'user-001', before_state: { status: 'under_review' }, after_state: { status: 'needs_more_evidence' }, details: { comment: '光谱特征与藻类相似，但分辨率不足以确认' } },
    ],
  },
];

export function getMockEvents(): EventDTO[] {
  return mockEvents;
}

export function getMockEvent(id: string): EventDTO | undefined {
  return mockEvents.find((e) => e.event_id === id);
}

export function getMockReplay(eventId: string): ReplayEntry[] {
  const event = mockEvents.find((e) => e.event_id === eventId);
  return event?.timeline ?? [];
}

export function getEventForCandidate(candidateId: string): EventDTO | undefined {
  return mockEvents.find((e) => e.candidate_id === candidateId);
}
