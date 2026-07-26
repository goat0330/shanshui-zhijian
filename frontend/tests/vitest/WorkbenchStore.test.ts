/* ============================================================
   山水智鉴 V0 — Zustand Store Tests
   ============================================================ */

import { describe, it, expect, beforeEach } from 'vitest';
import { useWorkbenchStore } from '../../src/app/store/workbench';

describe('Workbench Store', () => {
  beforeEach(() => {
    useWorkbenchStore.getState().reset();
  });

  it('should initialize with default state', () => {
    const state = useWorkbenchStore.getState();
    expect(state.selectedCandidateId).toBeNull();
    expect(state.compareMode).toBe('none');
    expect(state.leftPanelOpen).toBe(true);
    expect(state.rightPanelOpen).toBe(true);
  });

  it('should set selectedCandidateId', () => {
    useWorkbenchStore.getState().setSelectedCandidateId('CAND-001');
    expect(useWorkbenchStore.getState().selectedCandidateId).toBe('CAND-001');
  });

  it('should clear selectedCandidateId', () => {
    useWorkbenchStore.getState().setSelectedCandidateId('CAND-001');
    useWorkbenchStore.getState().setSelectedCandidateId(null);
    expect(useWorkbenchStore.getState().selectedCandidateId).toBeNull();
  });

  it('should set compare mode', () => {
    useWorkbenchStore.getState().setCompareMode('split');
    expect(useWorkbenchStore.getState().compareMode).toBe('split');

    useWorkbenchStore.getState().setCompareMode('opacity');
    expect(useWorkbenchStore.getState().compareMode).toBe('opacity');

    useWorkbenchStore.getState().setCompareMode('none');
    expect(useWorkbenchStore.getState().compareMode).toBe('none');
  });

  it('should set layer visibility', () => {
    useWorkbenchStore.getState().setLayerVisibility('candidates', false);
    expect(useWorkbenchStore.getState().layerVisibility['candidates']).toBe(false);

    useWorkbenchStore.getState().setLayerVisibility('candidates', true);
    expect(useWorkbenchStore.getState().layerVisibility['candidates']).toBe(true);
  });

  it('should set layer opacity', () => {
    useWorkbenchStore.getState().setLayerOpacity('water_gain', 0.5);
    expect(useWorkbenchStore.getState().layerOpacity['water_gain']).toBe(0.5);
  });

  it('should toggle panels', () => {
    useWorkbenchStore.getState().toggleLeftPanel();
    expect(useWorkbenchStore.getState().leftPanelOpen).toBe(false);

    useWorkbenchStore.getState().toggleRightPanel();
    expect(useWorkbenchStore.getState().rightPanelOpen).toBe(false);
  });

  it('should set viewport', () => {
    useWorkbenchStore.getState().setViewport({ center: [100, 30], zoom: 10 });
    const { viewport } = useWorkbenchStore.getState();
    expect(viewport.center[0]).toBe(100);
    expect(viewport.center[1]).toBe(30);
    expect(viewport.zoom).toBe(10);
  });

  it('should reset to initial state', () => {
    useWorkbenchStore.getState().setSelectedCandidateId('CAND-001');
    useWorkbenchStore.getState().setCompareMode('split');
    useWorkbenchStore.getState().reset();

    const state = useWorkbenchStore.getState();
    expect(state.selectedCandidateId).toBeNull();
    expect(state.compareMode).toBe('none');
  });
});
