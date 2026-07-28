import SituationCards from '@/features/dashboard/components/SituationCards';
import SpatialDistribution from '@/features/dashboard/components/SpatialDistribution';
import TrendChart from '@/features/dashboard/components/TrendChart';
import ReviewFunnel from '@/features/dashboard/components/ReviewFunnel';
import TypicalCases from '@/features/dashboard/components/TypicalCases';
import GovernanceMap from '@/features/map/components/GovernanceMap';
import DataSourceBadge from '@/shared/ui/DataSourceBadge';
import './index.css';

export default function DashboardPage() {
  return (
    <div className="d-b2">
      {/* Top header */}
      <div className="d-b2-header">
        <h2 className="d-b2-title">研判驾驶舱</h2>
        <DataSourceBadge mode="MOCK" />
      </div>

      {/* KPI row */}
      <div className="d-b2-kpi">
        <SituationCards />
      </div>

      {/* Three-column B2 layout */}
      <div className="d-b2-body">
        {/* Left: trend + funnel */}
        <aside className="d-b2-left">
          <section className="d-b2-section">
            <h4 className="d-b2-section-title">月度趋势</h4>
            <TrendChart />
          </section>
          <section className="d-b2-section">
            <h4 className="d-b2-section-title">研判链</h4>
            <ReviewFunnel />
          </section>
        </aside>

        {/* Center: map */}
        <main className="d-b2-center">
          <GovernanceMap />
        </main>

        {/* Right: distribution + cases */}
        <aside className="d-b2-right">
          <section className="d-b2-section">
            <h4 className="d-b2-section-title">类型分布</h4>
            <SpatialDistribution />
          </section>
          <section className="d-b2-section">
            <h4 className="d-b2-section-title">典型案例</h4>
            <TypicalCases />
          </section>
        </aside>
      </div>
    </div>
  );
}
