/* ============================================================
   山水智鉴 V0 — Layer Registry Tests
   ============================================================ */

import { describe, it, expect, beforeEach } from 'vitest';
import { LayerRegistry } from '../../src/features/map/layers/LayerRegistry';
import type { WorkbenchLayer } from '../../src/shared/types';

describe('LayerRegistry', () => {
  let registry: LayerRegistry;

  beforeEach(() => {
    registry = new LayerRegistry();
  });

  const makeLayer = (id: string, group = 'basemap'): WorkbenchLayer => ({
    id,
    title: id,
    group: group as any,
    layerType: 'raster',
    sourceType: 'tilejson',
    sourceUrl: '/tiles/{z}/{x}/{y}',
    visibleByDefault: true,
    opacity: 1,
    zIndex: 0,
  });

  it('should register and retrieve a layer', () => {
    registry.register(makeLayer('test-layer'));
    expect(registry.get('test-layer')).toBeDefined();
    expect(registry.get('test-layer')?.id).toBe('test-layer');
  });

  it('should return undefined for unknown layer', () => {
    expect(registry.get('unknown')).toBeUndefined();
  });

  it('should deregister a layer', () => {
    registry.register(makeLayer('test-layer'));
    registry.deregister('test-layer');
    expect(registry.get('test-layer')).toBeUndefined();
  });

  it('should return all layers sorted by zIndex', () => {
    registry.register({ ...makeLayer('bottom'), zIndex: 0 });
    registry.register({ ...makeLayer('top'), zIndex: 10 });
    registry.register({ ...makeLayer('middle'), zIndex: 5 });

    const all = registry.getAll();
    expect(all[0].id).toBe('bottom');
    expect(all[1].id).toBe('middle');
    expect(all[2].id).toBe('top');
  });

  it('should filter layers by group', () => {
    registry.register(makeLayer('b1', 'basemap'));
    registry.register(makeLayer('b2', 'basemap'));
    registry.register(makeLayer('s1', 'sar'));

    const basemaps = registry.getByGroup('basemap');
    expect(basemaps).toHaveLength(2);

    const sars = registry.getByGroup('sar');
    expect(sars).toHaveLength(1);

    const empty = registry.getByGroup('mask');
    expect(empty).toHaveLength(0);
  });

  it('should get visible layers', () => {
    const visible = makeLayer('visible');
    const hidden = { ...makeLayer('hidden'), visibleByDefault: false };
    registry.register(visible);
    registry.register(hidden);

    const visibles = registry.getVisible();
    expect(visibles).toHaveLength(1);
    expect(visibles[0].id).toBe('visible');
  });

  it('should handle empty registry', () => {
    expect(registry.getAll()).toHaveLength(0);
    expect(registry.getByGroup('basemap')).toHaveLength(0);
    expect(registry.getVisible()).toHaveLength(0);
  });
});
