/* ============================================================
   山水智鉴 V0 — 地图工具栏
   ============================================================ */

import { useWorkbenchStore } from '@/app/store/workbench';
import LayerPanel from './LayerPanel';
import ComparePanel from './ComparePanel';
import './MapToolbar.css';

export default function MapToolbar() {
  const { compareMode, setCompareMode, toggleLeftPanel, toggleRightPanel } = useWorkbenchStore();

  return (
    <div className="map-toolbar">
      <div className="map-toolbar-left">
        <LayerPanel />
      </div>
      <div className="map-toolbar-right">
        <ComparePanel />
        <button
          className={`map-tool-btn ${compareMode === 'opacity' ? 'active' : ''}`}
          onClick={() => setCompareMode(compareMode === 'opacity' ? 'none' : 'opacity')}
          title="透明度叠加"
        >
          叠
        </button>
        <button
          className={`map-tool-btn ${compareMode === 'split' ? 'active' : ''}`}
          onClick={() => setCompareMode(compareMode === 'split' ? 'none' : 'split')}
          title="左右分屏"
        >
          分
        </button>
        <div className="map-toolbar-divider" />
        <button className="map-tool-btn" onClick={toggleLeftPanel} title="切换左侧面板">
          ◀
        </button>
        <button className="map-tool-btn" onClick={toggleRightPanel} title="切换右侧面板">
          ▶
        </button>
      </div>
    </div>
  );
}
