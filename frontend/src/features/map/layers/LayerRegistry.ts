/* ============================================================
   山水智鉴 V0 — Layer Registry
   图层注册中心，新增图层无需修改核心 Map 实现
   ============================================================ */

import type { WorkbenchLayer } from '@/shared/types';

export class LayerRegistry {
  private layers = new Map<string, WorkbenchLayer>();

  register(layer: WorkbenchLayer): void {
    this.layers.set(layer.id, layer);
  }

  deregister(id: string): void {
    this.layers.delete(id);
  }

  get(id: string): WorkbenchLayer | undefined {
    return this.layers.get(id);
  }

  getAll(): WorkbenchLayer[] {
    return Array.from(this.layers.values()).sort((a, b) => a.zIndex - b.zIndex);
  }

  getByGroup(group: string): WorkbenchLayer[] {
    return this.getAll().filter((l) => l.group === group);
  }

  getVisible(): WorkbenchLayer[] {
    return this.getAll().filter((l) => l.visibleByDefault);
  }
}

// Singleton instance
export const layerRegistry = new LayerRegistry();

// Default layers
export function registerDefaultLayers(): void {
  const layers: WorkbenchLayer[] = [
    {
      id: 'sentinel2_recent',
      title: '最新 Sentinel-2',
      group: 'basemap',
      layerType: 'raster',
      sourceType: 'tilejson',
      sourceUrl: '/api/v2/artifacts/sentinel2_recent/tilejson',
      visibleByDefault: true,
      opacity: 1,
      zIndex: 0,
      legend: { type: 'single', items: [{ label: '真彩色影像', color: '#transparent' }] },
    },
    {
      id: 'sentinel2_median',
      title: '中位数参考',
      group: 'basemap',
      layerType: 'raster',
      sourceType: 'tilejson',
      sourceUrl: '/api/v2/artifacts/sentinel2_median/tilejson',
      visibleByDefault: false,
      opacity: 0.7,
      zIndex: 1,
    },
    {
      id: 'sar_recent',
      title: '当前 SAR',
      group: 'sar',
      layerType: 'raster',
      sourceType: 'tilejson',
      sourceUrl: '/api/v2/artifacts/sar_recent/tilejson',
      visibleByDefault: false,
      opacity: 0.8,
      zIndex: 2,
    },
    {
      id: 'sar_historical',
      title: '历史 SAR',
      group: 'sar',
      layerType: 'raster',
      sourceType: 'tilejson',
      sourceUrl: '/api/v2/artifacts/sar_historical/tilejson',
      visibleByDefault: false,
      opacity: 0.6,
      zIndex: 3,
    },
    {
      id: 'water_gain',
      title: '水面增加',
      group: 'change',
      layerType: 'raster',
      sourceType: 'tilejson',
      sourceUrl: '/api/v2/artifacts/water_gain/tilejson',
      visibleByDefault: true,
      opacity: 0.5,
      zIndex: 4,
      legend: {
        type: 'single',
        items: [{ label: '水面增加', color: 'var(--color-water-gain)' }],
      },
    },
    {
      id: 'water_loss',
      title: '水面减少',
      group: 'change',
      layerType: 'raster',
      sourceType: 'tilejson',
      sourceUrl: '/api/v2/artifacts/water_loss/tilejson',
      visibleByDefault: true,
      opacity: 0.5,
      zIndex: 5,
      legend: {
        type: 'single',
        items: [{ label: '水面减少', color: 'var(--color-water-loss)' }],
      },
    },
    {
      id: 'sar_anomaly',
      title: 'SAR 异常',
      group: 'change',
      layerType: 'raster',
      sourceType: 'tilejson',
      sourceUrl: '/api/v2/artifacts/sar_anomaly/tilejson',
      visibleByDefault: false,
      opacity: 0.6,
      zIndex: 6,
      legend: {
        type: 'single',
        items: [{ label: 'SAR 异常', color: 'var(--color-sar-anomaly)' }],
      },
    },
    {
      id: 'persistent_mask',
      title: '持久性掩膜',
      group: 'mask',
      layerType: 'mask',
      sourceType: 'tilejson',
      sourceUrl: '/api/v2/artifacts/persistent_mask/tilejson',
      visibleByDefault: false,
      opacity: 0.4,
      zIndex: 7,
    },
    {
      id: 'transient_mask',
      title: '瞬态掩膜',
      group: 'mask',
      layerType: 'mask',
      sourceType: 'tilejson',
      sourceUrl: '/api/v2/artifacts/transient_mask/tilejson',
      visibleByDefault: false,
      opacity: 0.3,
      zIndex: 8,
    },
    {
      id: 'candidates',
      title: '异常候选',
      group: 'vector',
      layerType: 'candidate',
      sourceType: 'geojson',
      sourceUrl: '/api/v2/map/candidates.geojson',
      visibleByDefault: true,
      opacity: 1,
      zIndex: 10,
      legend: {
        type: 'categorical',
        items: [
          { label: '持久性', color: 'var(--color-candidate-persistent)' },
          { label: '不确定', color: 'var(--color-candidate-uncertain)' },
          { label: '瞬态', color: 'var(--color-candidate-transient)' },
        ],
      },
    },
    {
      id: 'events',
      title: '异常事件',
      group: 'vector',
      layerType: 'event',
      sourceType: 'geojson',
      sourceUrl: '/api/v2/map/events.geojson',
      visibleByDefault: true,
      opacity: 1,
      zIndex: 11,
      legend: {
        type: 'categorical',
        items: [
          { label: '已确认', color: 'var(--color-event-confirmed)' },
          { label: '研判中', color: 'var(--color-event-review)' },
        ],
      },
    },
  ];

  layers.forEach((layer) => layerRegistry.register(layer));
}
