/* ============================================================
   山水智鉴 V0 — 图层面板
   ============================================================ */

import { useWorkbenchStore } from '@/app/store/workbench';
import { layerRegistry } from '../layers/LayerRegistry';
import './LayerPanel.css';

export default function LayerPanel() {
  const { layerVisibility, layerOpacity, setLayerVisibility, setLayerOpacity } = useWorkbenchStore();

  const layers = layerRegistry.getAll();
  const groups = [...new Set(layers.map((l) => l.group))];

  return (
    <div className="layer-panel">
      <span className="layer-panel-title">图层</span>
      {groups.map((group) => (
        <div key={group} className="layer-group">
          <span className="layer-group-label">{groupLabel(group)}</span>
          {layers
            .filter((l) => l.group === group)
            .map((layer) => {
              const visible = layerVisibility[layer.id] ?? layer.visibleByDefault;
              const opacity = layerOpacity[layer.id] ?? layer.opacity;
              return (
                <div key={layer.id} className="layer-item">
                  <label className="layer-toggle">
                    <input
                      type="checkbox"
                      checked={visible}
                      onChange={(e) => setLayerVisibility(layer.id, e.target.checked)}
                    />
                    <span className="layer-name">{layer.title}</span>
                  </label>
                  {visible && (
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={opacity}
                      onChange={(e) => setLayerOpacity(layer.id, parseFloat(e.target.value))}
                      className="layer-opacity-slider"
                    />
                  )}
                </div>
              );
            })}
        </div>
      ))}
    </div>
  );
}

function groupLabel(group: string): string {
  const labels: Record<string, string> = {
    basemap: '底图',
    sar: 'SAR',
    change: '变化检测',
    mask: '掩膜',
    vector: '矢量',
  };
  return labels[group] || group;
}
