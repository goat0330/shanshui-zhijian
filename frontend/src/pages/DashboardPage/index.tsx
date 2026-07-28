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
      <div className="d-b2-header">
        <h2 className="d-b2-title">研判驾驶舱</h2>
        <DataSourceBadge />
      </div>

      <div className="d-b2-kpi">
        <SituationCards />
      </div>

      <div className="d-b2-body">
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

        <main className="d-b2-center">
          <GovernanceMap readonly />
        </main>

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
