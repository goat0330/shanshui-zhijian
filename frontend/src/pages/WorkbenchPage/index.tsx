/* ============================================================
   山水智鉴 V0 — 研判工作台
   三栏布局：Candidate 队列 | 地图 | Candidate 详情
   ============================================================ */

import { useWorkbenchStore } from '@/app/store/workbench';
import { useUrlSync } from '@/shared/hooks/useUrlSync';
import CandidateList from '@/features/candidates/components/CandidateList';
import GovernanceMap from '@/features/map/components/GovernanceMap';
import CandidateDetail from '@/features/candidates/components/CandidateDetail';
import './index.css';

export default function WorkbenchPage() {
  useUrlSync();
  const {
    selectedCandidateId,
    leftPanelOpen,
    rightPanelOpen,
  } = useWorkbenchStore();

  return (
    <div className="workbench-layout">
      {leftPanelOpen && (
        <aside className="workbench-sidebar">
          <CandidateList />
        </aside>
      )}
      <div className="workbench-map">
        <GovernanceMap />
      </div>
      {rightPanelOpen && selectedCandidateId && (
        <aside className="workbench-detail">
          <CandidateDetail candidateId={selectedCandidateId} />
        </aside>
      )}
      {rightPanelOpen && !selectedCandidateId && (
        <aside className="workbench-detail">
          <div className="detail-empty">
            <span className="text-muted">选择一个 Candidate 查看详情</span>
          </div>
        </aside>
      )}
    </div>
  );
}
