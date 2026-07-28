/* ============================================================
   山水智鉴 V0 — 对比模式面板
   ============================================================ */

import { useWorkbenchStore } from '@/app/store/workbench';
import { layerRegistry } from '../layers/LayerRegistry';

export default function ComparePanel() {
  const { compareMode } = useWorkbenchStore();
  const layers = layerRegistry.getAll().filter((l) => l.group === 'change' || l.group === 'sar' || l.group === 'mask');

  if (compareMode === 'none') return null;

  return (
    <div className="compare-panel" style={{
      position: 'absolute',
      bottom: 40,
      left: 8,
      background: 'var(--color-surface)',
      border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-md)',
      padding: 'var(--spacing-sm)',
      fontSize: 'var(--font-size-sm)',
      boxShadow: 'var(--shadow-md)',
      zIndex: 100,
      pointerEvents: 'auto',
    }}>
      <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 11 }}>
        {compareMode === 'opacity' ? '透明度叠加' : '左右分屏'}
      </div>
      {layers.map((layer) => (
        <div key={layer.id} style={{ color: 'var(--color-text-secondary)', padding: '2px 0' }}>
          • {layer.title}
        </div>
      ))}
    </div>
  );
}
