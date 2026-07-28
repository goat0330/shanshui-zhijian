/* ============================================================
   山水智鉴 V0 — Zustand Workbench Store
   只保存运行时 UI 状态，不保存服务端数据
   ============================================================ */

import { create } from 'zustand';
import type { MapViewport, CompareMode, WorkbenchState } from '@/shared/types';

interface WorkbenchActions {
  setSelectedCandidateId: (id: string | null) => void;
  setViewport: (viewport: MapViewport) => void;
  setCompareMode: (mode: CompareMode) => void;
  setLayerVisibility: (id: string, visible: boolean) => void;
  setLayerOpacity: (id: string, opacity: number) => void;
  toggleLeftPanel: () => void;
  toggleRightPanel: () => void;
  reset: () => void;
}

type WorkbenchStore = WorkbenchState & WorkbenchActions;

const initialState: WorkbenchState = {
  selectedCandidateId: null,
  viewport: {
    center: [106.57, 29.565],
    zoom: 12,
  },
  compareMode: 'none',
  layerVisibility: {},
  layerOpacity: {},
  leftPanelOpen: true,
  rightPanelOpen: true,
};

export const useWorkbenchStore = create<WorkbenchStore>((set) => ({
  ...initialState,

  setSelectedCandidateId: (id) => set({ selectedCandidateId: id }),

  setViewport: (viewport) => set({ viewport }),

  setCompareMode: (mode) => set({ compareMode: mode }),

  setLayerVisibility: (id, visible) =>
    set((state) => ({
      layerVisibility: { ...state.layerVisibility, [id]: visible },
    })),

  setLayerOpacity: (id, opacity) =>
    set((state) => ({
      layerOpacity: { ...state.layerOpacity, [id]: opacity },
    })),

  toggleLeftPanel: () =>
    set((state) => ({ leftPanelOpen: !state.leftPanelOpen })),

  toggleRightPanel: () =>
    set((state) => ({ rightPanelOpen: !state.rightPanelOpen })),

  reset: () => set(initialState),
}));
