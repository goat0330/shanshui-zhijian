/* ============================================================
   山水智鉴 V0 — 运行记录
   ============================================================ */

import RunList from '@/features/runs/components/RunList';
import './index.css';

export default function RunCenterPage() {
  return (
    <div className="page-container">
      <div className="page-header">
        <h3>运行记录</h3>
        <span className="text-sm text-muted">算法运行历史、产物追溯</span>
      </div>
      <div className="page-content">
        <RunList />
      </div>
    </div>
  );
}
