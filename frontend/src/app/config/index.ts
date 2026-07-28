/* ============================================================
   山水智鉴 V0 — 应用配置
   ============================================================ */

export interface AppConfig {
  apiMode: 'mock' | 'real';
  apiBaseUrl: string;
  mapStyle: string;
  mapCenter: [number, number];
  mapZoom: number;
  titilerUrl: string;
  defaultLayerIds: string[];
  candidatePageSize: number;
  eventPageSize: number;
  runPageSize: number;
}

const config: AppConfig = {
  apiMode: (import.meta.env.VITE_API_MODE as 'mock' | 'real') || 'mock',
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || '/api/v2',
  mapStyle: import.meta.env.VITE_MAP_STYLE || 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  mapCenter: [106.57, 29.565] as [number, number],
  mapZoom: Number(import.meta.env.VITE_MAP_ZOOM) || 12,
  titilerUrl: import.meta.env.VITE_TITILER_URL || 'http://localhost:8001',
  defaultLayerIds: ['candidates', 'events', 'water_gain', 'water_loss'],
  candidatePageSize: 20,
  eventPageSize: 20,
  runPageSize: 20,
};

export default config;
