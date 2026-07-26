/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_MODE: string;
  readonly VITE_API_BASE_URL: string;
  readonly VITE_MAP_STYLE: string;
  readonly VITE_MAP_CENTER: string;
  readonly VITE_MAP_ZOOM: string;
  readonly VITE_TITILER_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
