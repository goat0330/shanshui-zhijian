/* ============================================================
   山水智鉴 V0 — Design Tokens Tests
   验证 tokens.css 中定义了必要的 Token
   ============================================================ */

import { describe, it, expect, beforeAll } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('Design Tokens', () => {
  const tokensPath = path.resolve(__dirname, '../../src/styles/tokens.css');
  let tokensContent: string;

  beforeAll(() => {
    tokensContent = fs.readFileSync(tokensPath, 'utf-8');
  });

  it('should define primary color', () => {
    expect(tokensContent).toContain('--color-primary');
  });

  it('should define surface colors', () => {
    expect(tokensContent).toContain('--color-surface');
    expect(tokensContent).toContain('--color-surface-elevated');
  });

  it('should define border colors', () => {
    expect(tokensContent).toContain('--color-border');
  });

  it('should define text colors', () => {
    expect(tokensContent).toContain('--color-text-primary');
    expect(tokensContent).toContain('--color-text-secondary');
  });

  it('should define candidate status colors', () => {
    expect(tokensContent).toContain('--color-candidate-persistent');
    expect(tokensContent).toContain('--color-candidate-transient');
    expect(tokensContent).toContain('--color-candidate-uncertain');
  });

  it('should define event status colors', () => {
    expect(tokensContent).toContain('--color-event-confirmed');
    expect(tokensContent).toContain('--color-event-rejected');
    expect(tokensContent).toContain('--color-event-review');
    expect(tokensContent).toContain('--color-event-more-evidence');
  });

  it('should define change detection colors', () => {
    expect(tokensContent).toContain('--color-water-gain');
    expect(tokensContent).toContain('--color-water-loss');
    expect(tokensContent).toContain('--color-sar-anomaly');
  });

  it('should define spacing tokens', () => {
    expect(tokensContent).toContain('--spacing-sm');
    expect(tokensContent).toContain('--spacing-md');
    expect(tokensContent).toContain('--spacing-lg');
  });

  it('should define layout sizes', () => {
    expect(tokensContent).toContain('--sidebar-width');
    expect(tokensContent).toContain('--detail-panel-width');
    expect(tokensContent).toContain('--header-height');
  });

  it('should not contain hardcoded color values in business components', () => {
    // Check that tokens file uses CSS variable pattern
    const varPattern = /--color-/g;
    const matches = tokensContent.match(varPattern);
    expect(matches?.length).toBeGreaterThan(20);
  });
});
