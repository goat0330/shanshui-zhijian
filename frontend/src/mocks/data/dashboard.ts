export interface DashboardSnapshot {
  summary: DashboardSummary;
  change_types: ChangeTypeDistribution[];
  trend: MonthlyTrend[];
  funnel: ReviewFunnelStage[];
  typical_cases: TypicalCase[];
}

export interface DashboardSummary {
  total_candidates: number;
  persistent_count: number;
  uncertain_count: number;
  transient_count: number;
  events_under_review: number;
  events_confirmed: number;
  events_rejected: number;
  events_needs_evidence: number;
  total_runs: number;
  runs_completed: number;
  runs_failed: number;
  last_run_at: string;
  monitoring_area_km2: number;
}

export interface ChangeTypeDistribution {
  change_type: string;
  label: string;
  count: number;
  color: string;
}

export interface MonthlyTrend {
  month: string;
  label: string;
  candidates: number;
  confirmed: number;
}

export interface ReviewFunnelStage {
  stage: string;
  count: number;
  description: string;
}

export interface TypicalCase {
  id: string;
  title: string;
  change_type: string;
  change_type_label: string;
  status: string;
  status_label: string;
  area_m2: number;
  detected_at: string;
  summary: string;
  candidate_id?: string;
}

export const mockDashboardSnapshot: DashboardSnapshot = {
  summary: {
    total_candidates: 36,
    persistent_count: 12,
    uncertain_count: 4,
    transient_count: 20,
    events_under_review: 1,
    events_confirmed: 1,
    events_rejected: 0,
    events_needs_evidence: 1,
    total_runs: 2,
    runs_completed: 2,
    runs_failed: 0,
    last_run_at: '2026-06-10T08:45:00Z',
    monitoring_area_km2: 156.42,
  },
  change_types: [
    { change_type: 'water_extent_increase', label: '水面扩展', count: 10, color: '#1565c0' },
    { change_type: 'water_extent_decrease', label: '水面缩减', count: 5, color: '#e53935' },
    { change_type: 'turbidity_anomaly', label: '浑浊度异常', count: 6, color: '#f57c00' },
    { change_type: 'algae_bloom', label: '藻类爆发', count: 4, color: '#2e7d32' },
    { change_type: 'bank_collapse', label: '岸线变化', count: 3, color: '#6a1b9a' },
    { change_type: 'suspected_discharge', label: '疑似排污', count: 5, color: '#d32f2f' },
    { change_type: 'sediment_anomaly', label: '泥沙异常', count: 2, color: '#795548' },
    { change_type: 'vegetation_change', label: '植被变化', count: 1, color: '#388e3c' },
  ],
  trend: [
    { month: '2026-03', label: '3月', candidates: 8, confirmed: 0 },
    { month: '2026-04', label: '4月', candidates: 12, confirmed: 0 },
    { month: '2026-05', label: '5月', candidates: 10, confirmed: 1 },
    { month: '2026-06', label: '6月', candidates: 6, confirmed: 0 },
  ],
  funnel: [
    { stage: 'candidates_created', count: 36, description: '候选产生' },
    { stage: 'evidence_ready', count: 28, description: '证据就绪' },
    { stage: 'reviewed', count: 3, description: '已完成研判' },
    { stage: 'event_versioned', count: 1, description: '已生成事件版本' },
  ],
  typical_cases: [
    {
      id: 'EVT-2026-001',
      title: '长江支流 A 段水面异常扩展',
      change_type: 'water_extent_increase',
      change_type_label: '水面扩展',
      status: 'confirmed',
      status_label: '已确认',
      area_m2: 45200,
      detected_at: '2026-06-01',
      summary: 'Sentinel-2 多时相分析显示水面面积较上月增加约 15%，SAR 数据交叉验证一致。',
      candidate_id: 'CAND-0001',
    },
    {
      id: 'EVT-2026-003',
      title: 'C 水库疑似藻类爆发',
      change_type: 'algae_bloom',
      change_type_label: '藻类爆发',
      status: 'needs_more_evidence',
      status_label: '待补证',
      area_m2: 12800,
      detected_at: '2026-06-15',
      summary: 'NDVI 异常升高，光谱特征与藻类爆发匹配。当前光学影像分辨率不足以确认。',
      candidate_id: 'CAND-0003',
    },
    {
      id: 'CAND-0004',
      title: 'D 河段水体浑浊度持续异常',
      change_type: 'turbidity_anomaly',
      change_type_label: '浑浊度异常',
      status: 'under_review',
      status_label: '研判中',
      area_m2: 8900,
      detected_at: '2026-06-10',
      summary: '近 2 周水体浑浊度持续性偏高，疑似上游施工影响。',
      candidate_id: 'CAND-0004',
    },
    {
      id: 'CAND-0007',
      title: 'E 断面疑似夜间排污',
      change_type: 'suspected_discharge',
      change_type_label: '疑似排污',
      status: 'under_review',
      status_label: '研判中',
      area_m2: 3200,
      detected_at: '2026-06-08',
      summary: '凌晨时段 SAR 后向散射异常升高，时序变化特征与工业排放高度吻合。',
      candidate_id: 'CAND-0007',
    },
    {
      id: 'CAND-0010',
      title: 'F 河岸局部坍塌',
      change_type: 'bank_collapse',
      change_type_label: '岸线变化',
      status: 'under_review',
      status_label: '研判中',
      area_m2: 5600,
      detected_at: '2026-06-12',
      summary: '岸线位移约 3-5 米，Sentinel-1 时序 InSAR 显示该段存在持续形变。',
      candidate_id: 'CAND-0010',
    },
  ],
};

export function getDashboardSnapshot(): DashboardSnapshot {
  return {
    summary: { ...mockDashboardSnapshot.summary },
    change_types: mockDashboardSnapshot.change_types.map((d) => ({ ...d })),
    trend: mockDashboardSnapshot.trend.map((d) => ({ ...d })),
    funnel: mockDashboardSnapshot.funnel.map((d) => ({ ...d })),
    typical_cases: mockDashboardSnapshot.typical_cases.map((d) => ({ ...d })),
  };
}
