/* ============================================================
   山水智鉴 V0 — Score Label Tests
   验证 Score 显示不违反产品规则
   ============================================================ */

import { describe, it, expect } from 'vitest';

describe('Score Label Rules', () => {
  it('should NOT contain 风险 probability or 准确率 in label', () => {
    const forbiddenTerms = ['风险', '概率', '准确率', '严重度', '违法确认', '污染确认'];
    const scoreLabels = ['本次运行排序分', '本批候选排名'];

    scoreLabels.forEach((label) => {
      forbiddenTerms.forEach((term) => {
        expect(label).not.toContain(term);
      });
    });
  });

  it('should display score as ranking not probability', () => {
    const score = 0.723;
    const formatted = `本次运行排序分：${score.toFixed(3)}`;
    expect(formatted).toContain('排序分');
    expect(formatted).not.toContain('%');
  });

  it('should display batch rank as fraction', () => {
    const rank = 5;
    const total = 20;
    const formatted = `本批候选排名：${rank} / ${total}`;
    expect(formatted).toContain('排名');
  });
});
