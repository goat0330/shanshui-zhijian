/* ============================================================
    山水智鉴 V0 — 研判驾驶舱 (Dashboard)
    展示全局面板：态势卡片、空间分布、趋势图、研判漏斗、典型案例
    ⚠️ 此页面使用 MOCK 数据，仅供 DEMO 演示
    ============================================================ */

import SituationCards from '@/features/dashboard/components/SituationCards';
import SpatialDistribution from '@/features/dashboard/components/SpatialDistribution';
import TrendChart from '@/features/dashboard/components/TrendChart';
import ReviewFunnel from '@/features/dashboard/components/ReviewFunnel';
import TypicalCases from '@/features/dashboard/components/TypicalCases';
import './index.css';

export default function DashboardPage() {
  return (
    <div className="dashboard-layout">
      {/* Header */}
      <div className="dashboard-header">
        <div className="dashboard-header-left">
          <h2 className="dashboard-title">研判驾驶舱</h2>
          <span className="dashboard-mock-badge">MOCK / DEMO</span>
        </div>
        <p className="dashboard-subtitle">
          数据仅用于演示，不反映真实治理成效
        </p>
      </div>

      {/* Row 1: Situation Cards */}
      <SituationCards />

      {/* Row 2: 2-column grid */}
      <div className="dashboard-grid-2col">
        <SpatialDistribution />
        <TrendChart />
      </div>

      {/* Row 3: 2-column grid */}
      <div className="dashboard-grid-2col">
        <ReviewFunnel />
        <TypicalCases />
      </div>
    </div>
  );
}
