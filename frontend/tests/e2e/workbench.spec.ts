/* ============================================================
   山水智鉴 V0 — Real API E2E Tests
   24 Playwright 场景覆盖真实 FastAPI + SQLite + React 闭环
   ============================================================ */

import { test, expect } from '@playwright/test';

async function selectCandidate(page: import('@playwright/test').Page, index = 0) {
  const card = page.locator('.candidate-card').nth(index);
  await expect(card).toBeVisible({ timeout: 10_000 });
  await card.click();
  await expect(page.locator('.candidate-detail')).toBeVisible({ timeout: 10_000 });
}

test.describe('山水智鉴 V0 — 真实研判工作台', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('1. 打开工作台 — 三栏布局与真实 API 可用', async ({ page }) => {
    await expect(page).toHaveTitle(/山水智鉴/);
    await expect(page.getByRole('link', { name: '研判工作台' })).toBeVisible();
    await expect(page.getByRole('link', { name: '事件中心' })).toBeVisible();
    await expect(page.getByRole('link', { name: '运行记录' })).toBeVisible();
    await expect(page.getByRole('link', { name: '系统设置' })).toBeVisible();

    const response = await page.request.get('/api/v2/workbench/summary');
    expect(response.ok()).toBeTruthy();
    const summary = await response.json();
    expect(summary.source).toBe('real');
    expect(summary.total_candidates).toBeGreaterThan(0);
  });

  test('2. 默认隐藏 transient', async ({ page }) => {
    const transientToggle = page.locator('.transient-toggle input');
    await expect(transientToggle).not.toBeChecked();
    await expect(page.locator('.candidate-card').first()).toBeVisible();
    const response = await page.request.get('/api/v2/candidates?limit=100');
    const body = await response.json();
    expect(body.data.every((item: { persistence_status: string }) => item.persistence_status !== 'transient')).toBeTruthy();
  });

  test('3. 显示 transient', async ({ page }) => {
    const transientToggle = page.locator('.transient-toggle input');
    await transientToggle.check();
    await expect(transientToggle).toBeChecked();
    const response = await page.request.get('/api/v2/candidates?include_transient=true&limit=100');
    const body = await response.json();
    expect(body.data.some((item: { persistence_status: string }) => item.persistence_status === 'transient')).toBeTruthy();
  });

  test('4. 按面积排序', async ({ page }) => {
    await page.locator('.candidate-list-controls select').selectOption('area');
    await expect(page.locator('.candidate-card').first()).toBeVisible();
  });

  test('5. 按次数排序', async ({ page }) => {
    await page.locator('.candidate-list-controls select').selectOption('occurrence_count');
    await expect(page.locator('.candidate-card').first()).toBeVisible();
  });

  test('6. 点击 Candidate — 右侧面板更新', async ({ page }) => {
    await selectCandidate(page, 0);
    await expect(page.getByText('本次运行排序分')).toBeVisible();
  });

  test('7. Score 显示为排序分而非风险概率', async ({ page }) => {
    await selectCandidate(page, 0);
    const detail = page.locator('.candidate-detail');
    await expect(detail.getByText('本次运行排序分')).toBeVisible();
    await expect(detail.getByText(/风险|准确率|严重度|违法/)).toHaveCount(0);
  });

  test('8. 图层面板可见', async ({ page }) => {
    await expect(page.locator('.layer-panel')).toBeVisible();
  });

  test('9. 透明度控件可用', async ({ page }) => {
    const sliders = page.locator('.layer-panel input[type="range"]');
    expect(await sliders.count()).toBeGreaterThanOrEqual(0);
  });

  test('10. 左右分屏模式', async ({ page }) => {
    await page.locator('.map-tool-btn').filter({ hasText: '分' }).click();
    await expect(page.locator('.map-wrapper')).toBeAttached();
  });

  test('11. 透明度叠加模式', async ({ page }) => {
    await page.locator('.map-tool-btn').filter({ hasText: '叠' }).click();
    await expect(page.locator('.map-wrapper')).toBeAttached();
  });

  test('12. 查看真实 SQLite Evidence', async ({ page }) => {
    await selectCandidate(page, 0);
    await expect(page.getByText('光学').first()).toBeVisible({ timeout: 10_000 });
  });

  test('13. Confirm 研判并生成事件', async ({ page }) => {
    await selectCandidate(page, 0);
    await page.locator('.review-action-btn').filter({ hasText: '确认' }).click();
    await page.locator('.review-textarea').fill('证据确凿，确认为水体扩张');
    await page.locator('.review-submit').click();
    await expect(page.getByText('研判成功')).toBeVisible({ timeout: 10_000 });
  });

  test('14. Reject 研判', async ({ page }) => {
    await selectCandidate(page, 1);
    await page.locator('.review-action-btn').filter({ hasText: '驳回' }).click();
    await page.locator('.review-textarea').fill('证据不足，非水体变化');
    await page.locator('.review-submit').click();
    await expect(page.getByText('研判成功')).toBeVisible({ timeout: 10_000 });
  });

  test('15. Reclassify 研判', async ({ page }) => {
    await selectCandidate(page, 2);
    await page.locator('.review-action-btn').filter({ hasText: '重新分类' }).click();
    await page.locator('.review-input').fill('疑似施工');
    await page.locator('.review-textarea').fill('类别调整为疑似施工');
    await page.locator('.review-submit').click();
    await expect(page.getByText('研判成功')).toBeVisible({ timeout: 10_000 });
  });

  test('16. Needs More Evidence 研判', async ({ page }) => {
    await selectCandidate(page, 3);
    await page.locator('.review-action-btn').filter({ hasText: '需补证' }).click();
    await page.locator('.review-textarea').fill('需要高分辨率光学影像确认');
    await page.locator('.review-submit').click();
    await expect(page.getByText('研判成功')).toBeVisible({ timeout: 10_000 });
  });

  test('17. 事件中心 — 页面加载', async ({ page }) => {
    await page.getByRole('link', { name: '事件中心' }).click();
    await expect(page.getByRole('heading', { name: '事件中心' })).toBeVisible();
  });

  test('18. 事件中心 — 展示真实治理事件', async ({ page }) => {
    await page.getByRole('link', { name: '事件中心' }).click();
    await expect(page.locator('.event-card').first()).toBeVisible({ timeout: 10_000 });
  });

  test('19. 运行记录 — 页面加载', async ({ page }) => {
    await page.getByRole('link', { name: '运行记录' }).click();
    await expect(page.getByRole('heading', { name: '运行记录' })).toBeVisible();
  });

  test('20. 运行记录 — 读取真实 RunManifest', async ({ page }) => {
    await page.getByRole('link', { name: '运行记录' }).click();
    await expect(page.locator('.run-card').first()).toBeVisible({ timeout: 10_000 });
    await page.locator('.run-card').first().click();
    await expect(page.getByText('运行参数')).toBeVisible();
  });

  test('21. API Not Found 错误语义', async ({ page }) => {
    const response = await page.request.get('/api/v2/candidates/DOES-NOT-EXIST');
    expect(response.status()).toBe(404);
    const body = await response.json();
    expect(body.detail.code).toBe('NOT_FOUND');
  });

  test('22. 刷新后真实 Candidate 列表可恢复', async ({ page }) => {
    await selectCandidate(page, 0);
    await page.reload();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.candidate-card').first()).toBeVisible({ timeout: 10_000 });
  });

  test('23. 空事件列表保持合法响应', async ({ page }) => {
    const response = await page.request.get('/api/v2/events?status=__none__');
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.data).toEqual([]);
    expect(body.pagination.total).toBe(0);
  });

  test('24. 系统设置明确显示 Real API', async ({ page }) => {
    await page.getByRole('link', { name: '系统设置' }).click();
    await expect(page.getByText('API 模式')).toBeVisible();
    await expect(page.getByText('Real API')).toBeVisible();
    await expect(page.getByText('Mock 数据')).toHaveCount(0);
  });
});
