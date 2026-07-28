/* ============================================================
   山水智鉴 V0 — 地图核心组件
   ============================================================ */

import { useEffect, useRef } from 'react';
import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useWorkbenchStore } from '@/app/store/workbench';
import config from '@/app/config';
import { useMapLayerSync } from '../hooks/useMapLayerSync';
import MapToolbar from './MapToolbar';
import MapStatusBar from './MapStatusBar';
import FeaturePopup from './FeaturePopup';
import './GovernanceMap.css';

export default function GovernanceMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const { compareMode, viewport, setViewport } = useWorkbenchStore();

  // Initialize map once
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: config.mapStyle,
      center: viewport.center,
      zoom: viewport.zoom,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl(), 'bottom-right');
    map.addControl(new maplibregl.ScaleControl(), 'bottom-left');

    map.on('moveend', () => {
      const center = map.getCenter();
      const zoom = map.getZoom();
      setViewport({ center: [center.lng, center.lat], zoom });
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync layers
  useMapLayerSync(mapRef);

  // Handle compare mode
  useEffect(() => {
    // Compare mode changes handled via CSS class
    if (mapContainer.current) {
      mapContainer.current.classList.toggle('split-mode', compareMode === 'split');
    }
  }, [compareMode]);

  // Clear popup on candidate change
  useEffect(() => {
    if (popupRef.current) {
      popupRef.current.remove();
      popupRef.current = null;
    }
  }, []);

  return (
    <div className="map-wrapper">
      <div ref={mapContainer} className={`map-container ${compareMode === 'split' ? 'map-split' : ''}`} />
      <MapToolbar />
      <MapStatusBar />
      <FeaturePopup />
    </div>
  );
}
