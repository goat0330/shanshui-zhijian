/* ============================================================
   山水智鉴 V0 — Hook: 地图图层同步
   将 LayerRegistry 中的图层同步到 MapLibre 实例
   ============================================================ */

import { useEffect, useRef } from 'react';
import type * as maplibregl from 'maplibre-gl';
import { useWorkbenchStore } from '@/app/store/workbench';
import { layerRegistry, registerDefaultLayers } from '../layers/LayerRegistry';

// Register default layers once
let registered = false;

export function useMapLayerSync(mapRef: React.MutableRefObject<maplibregl.Map | null>) {
  const { layerVisibility, layerOpacity } = useWorkbenchStore();
  const syncRef = useRef(false);

  useEffect(() => {
    if (!registered) {
      registerDefaultLayers();
      registered = true;
    }
  }, []);

  // Sync layers when map is ready
  useEffect(() => {
    const map = mapRef.current;
    if (!map || syncRef.current) return;

    map.on('load', () => {
      const layers = layerRegistry.getAll();
      layers.forEach((layer) => {
        const visible = layerVisibility[layer.id] ?? layer.visibleByDefault;
        const opacity = layerOpacity[layer.id] ?? layer.opacity;

        if (layer.sourceType === 'geojson' && layer.layerType === 'candidate') {
          // Add GeoJSON source for candidates
          map.addSource(layer.id, {
            type: 'geojson',
            data: layer.sourceUrl,
          });

          // Add fill layer
          map.addLayer({
            id: `${layer.id}-layer`,
            type: 'fill',
            source: layer.id,
            paint: {
              'fill-color': [
                'match',
                ['get', 'persistence_status'],
                'persistent', '#e53935',
                'uncertain', '#9e9e9e',
                'transient', '#ff9800',
                '#888888',
              ],
              'fill-opacity': opacity * 0.3,
            },
          });

          // Add outline layer
          map.addLayer({
            id: `${layer.id}-outline`,
            type: 'line',
            source: layer.id,
            paint: {
              'line-color': [
                'match',
                ['get', 'persistence_status'],
                'persistent', '#e53935',
                'uncertain', '#9e9e9e',
                'transient', '#ff9800',
                '#888888',
              ],
              'line-width': 2,
            },
          });

          if (!visible) {
            map.setLayoutProperty(`${layer.id}-layer`, 'visibility', 'none');
            map.setLayoutProperty(`${layer.id}-outline`, 'visibility', 'none');
          }
        }

        if (layer.sourceType === 'geojson' && layer.layerType === 'event') {
          map.addSource(layer.id, {
            type: 'geojson',
            data: layer.sourceUrl,
          });

          map.addLayer({
            id: `${layer.id}-layer`,
            type: 'fill',
            source: layer.id,
            paint: {
              'fill-color': [
                'match',
                ['get', 'status'],
                'confirmed', '#2e7d32',
                'under_review', '#1565c0',
                '#888888',
              ],
              'fill-opacity': opacity * 0.3,
            },
          });
        }
      });

      syncRef.current = true;
    });
  }, [mapRef, layerVisibility, layerOpacity]);
}
