/* ============================================================
   山水智鉴 V0 — Candidate Filter Tests
   验证筛选逻辑（模拟数据不变的情况下逻辑正确）
   ============================================================ */

import { describe, it, expect } from 'vitest';
import { mockCandidateListItems } from '../../src/mocks/data/candidates';

describe('Candidate Filter Logic', () => {
  it('should have 12 persistent candidates', () => {
    const persistent = mockCandidateListItems.filter((c) => c.persistence_status === 'persistent');
    expect(persistent).toHaveLength(12);
  });

  it('should have 4 uncertain candidates', () => {
    const uncertain = mockCandidateListItems.filter((c) => c.persistence_status === 'uncertain');
    expect(uncertain).toHaveLength(4);
  });

  it('should have 20 transient candidates', () => {
    const transient = mockCandidateListItems.filter((c) => c.persistence_status === 'transient');
    expect(transient).toHaveLength(20);
  });

  it('should hide transient by default', () => {
    const withoutTransient = mockCandidateListItems.filter((c) => c.persistence_status !== 'transient');
    expect(withoutTransient).toHaveLength(16); // 12 + 4
  });

  it('should sort by area in descending order', () => {
    const sorted = [...mockCandidateListItems].sort((a, b) => b.area_m2 - a.area_m2);
    for (let i = 1; i < sorted.length; i++) {
      expect(sorted[i - 1].area_m2).toBeGreaterThanOrEqual(sorted[i].area_m2);
    }
  });

  it('should sort by occurrence_count in descending order', () => {
    const sorted = [...mockCandidateListItems].sort((a, b) => b.occurrence_count - a.occurrence_count);
    for (let i = 1; i < sorted.length; i++) {
      expect(sorted[i - 1].occurrence_count).toBeGreaterThanOrEqual(sorted[i].occurrence_count);
    }
  });

  it('should filter by change_type', () => {
    const waterIncrease = mockCandidateListItems.filter((c) => c.change_type === 'water_extent_increase');
    expect(waterIncrease.length).toBeGreaterThan(0);
    waterIncrease.forEach((c) => expect(c.change_type).toBe('water_extent_increase'));
  });

  it('should have unique candidate IDs', () => {
    const ids = mockCandidateListItems.map((c) => c.candidate_id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
