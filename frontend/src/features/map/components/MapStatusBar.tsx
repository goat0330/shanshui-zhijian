/* ============================================================
   山水智鉴 V0 — 地图状态栏
   ============================================================ */

import { useWorkbenchStore } from '@/app/store/workbench';

export default function MapStatusBar() {
  const { viewport } = useWorkbenchStore();

  return (
    <div className="map-status-bar" style={{
      position: 'absolute',
      bottom: 0,
      left: 0,
      right: 0,
      height: 'var(--status-bar-height)',
      background: 'var(--color-surface-elevated)',
      borderTop: '1px solid var(--color-border)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 var(--spacing-md)',
      fontSize: 'var(--font-size-xs)',
      color: 'var(--color-text-muted)',
      zIndex: 10,
      gap: 'var(--spacing-lg)',
    }}>
      <span>经纬度: {viewport.center[0].toFixed(4)}, {viewport.center[1].toFixed(4)}</span>
      <span>缩放: {viewport.zoom.toFixed(1)}</span>
      <span style={{ marginLeft: 'auto' }}>EPSG:4326</span>
    </div>
  );
}
