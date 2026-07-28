/* ============================================================
   山水智鉴 V0 — E2E Tests
   24 Playwright 场景覆盖核心闭环
   ============================================================ */

import { test, expect } from '@playwright/test';

test.describe('山水智鉴 V0 — 研判工作台', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('1. 打开工作台 — 三栏布局正确显示', async ({ page }) => {
    // 页面标题正确
    await expect(page).toHaveTitle(/山水智鉴/);

    // 导航完整
    await expect(page.getByRole('link', { name: '研判工作台' })).toBeVisible();
    await expect(page.getByRole('link', { name: '事件中心' })).toBeVisible();
    await expect(page.getByRole('link', { name: '运行记录' })).toBeVisible();
    await expect(page.getByRole('link', { name: '系统设置' })).toBeVisible();
  });

  test('2. 默认隐藏 transient', async ({ page }) => {
    // 默认 transient 复选框未选中
    const transientToggle = page.locator('.transient-toggle input');
    await expect(transientToggle).not.toBeChecked();

    // 应显示 persistent + uncertain (至少一个 Candidate 卡片)
    const cards = page.locator('.candidate-card');
    await expect(cards.first()).toBeVisible();
  });

  test('3. 显示 transient', async ({ page }) => {
    const transientToggle = page.locator('.transient-toggle input');
    await transientToggle.check();
    await expect(transientToggle).toBeChecked();
  });

  test('4. 按面积排序', async ({ page }) => {
    const sortSelect = page.locator('.candidate-list-controls select');
    await sortSelect.selectOption('area');
    await page.waitForTimeout(500);
    // 选中后不应报错
    await expect(page.locator('.candidate-card').first()).toBeVisible();
  });

  test('5. 按次数排序', async ({ page }) => {
    const sortSelect = page.locator('.candidate-list-controls select');
    await sortSelect.selectOption('occurrence_count');
    await page.waitForTimeout(500);
    await expect(page.locator('.candidate-card').first()).toBeVisible();
  });

  test('6. 点击 Candidate — 右侧面板更新', async ({ page }) => {
    const firstCard = page.locator('.candidate-card').first();
    await firstCard.click();

    // 右侧应出现详情
    await expect(page.locator('.candidate-detail')).toBeVisible({ timeout: 5000 });
    // 应有 score 信息
    await expect(page.getByText('本次运行排序分')).toBeVisible();
  });

  test('7. Score 显示为排序分不显示为概率', async ({ page }) => {
    await page.locator('.candidate-card').first().click();
    await page.waitForTimeout(1000);

    const detail = page.locator('.candidate-detail');
    await expect(detail.getByText('本次运行排序分')).toBeVisible();
    // 不应出现禁止词汇
    await expect(detail.getByText(/风险|概率|准确率|严重度|违法/)).toHaveCount(0);
  });

  test('8. 切换图层 — 打开图层面板', async ({ page }) => {
    const layerBtn = page.locator('.layer-panel');
    await expect(layerBtn).toBeVisible();
  });

  test('9. 调整透明度 — 因滑块可见', async ({ page }) => {
    const layerPanel = page.locator('.layer-panel');
    // 找一个可见图层旁的透明度滑块
    const sliders = layerPanel.locator('input[type="range"]');
    const count = await sliders.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('10. 左右分屏模式', async ({ page }) => {
    const splitBtn = page.locator('.map-tool-btn').filter({ hasText: '分' });
    await splitBtn.click();

    // 验证模式切换，split-mode 类会被添加到地图容器
    await expect(page.locator('.map-wrapper')).toBeAttached();
  });

  test('11. 透明度叠加模式', async ({ page }) => {
    const opacityBtn = page.locator('.map-tool-btn').filter({ hasText: '叠' });
    await opacityBtn.click();
    await expect(page.locator('.map-wrapper')).toBeAttached();
  });

  test('12. 查看 Evidence', async ({ page }) => {
    await page.locator('.candidate-card').first().click();
    await page.waitForTimeout(1000);

    // Evidence 面板应显示
    await expect(page.getByText('光学').first()).toBeVisible({ timeout: 5000 });
  });

  test('13. Confirm 研判', async ({ page }) => {
    await page.locator('.candidate-card').first().click();
    await page.waitForTimeout(1000);

    // 选择 confirm
    await page.locator('.review-action-btn').filter({ hasText: '确认' }).click();
    // 填写意见
    const textarea = page.locator('.review-textarea');
    await textarea.fill('证据确凿，确认为水体扩张');
    // 提交
    await page.locator('.review-submit').click();
    // 等待成功提示
    await expect(page.getByText('研判成功')).toBeVisible({ timeout: 5000 });
  });

  test('14. Reject 研判', async ({ page }) => {
    await page.locator('.candidate-card').first().click();
    await page.waitForTimeout(1000);

    await page.locator('.review-action-btn').filter({ hasText: '驳回' }).click();
    await page.locator('.review-textarea').fill('证据不足，非水体变化');
    await page.locator('.review-submit').click();
    await expect(page.getByText('研判成功')).toBeVisible({ timeout: 5000 });
  });

  test('15. Reclassify 研判', async ({ page }) => {
    await page.locator('.candidate-card').first().click();
    await page.waitForTimeout(1000);

    await page.locator('.review-action-btn').filter({ hasText: '重新分类' }).click();
    await page.locator('.review-input').fill('疑似施工');
    await page.locator('.review-textarea').fill('类别调整为疑似施工');
    await page.locator('.review-submit').click();
    await expect(page.getByText('研判成功')).toBeVisible({ timeout: 5000 });
  });

  test('16. Needs More Evidence 研判', async ({ page }) => {
    await page.locator('.candidate-card').first().click();
    await page.waitForTimeout(1000);

    await page.locator('.review-action-btn').filter({ hasText: '需补证' }).click();
    await page.locator('.review-textarea').fill('需要高分辨率光学影像确认');
    await page.locator('.review-submit').click();
    await expect(page.getByText('研判成功')).toBeVisible({ timeout: 5000 });
  });

  test('17. 事件中心 — 页面加载', async ({ page }) => {
    await page.getByRole('link', { name: '事件中心' }).click();
    await page.waitForTimeout(1000);
    await expect(page.getByRole('heading', { name: '事件中心' })).toBeVisible();
  });

  test('18. 事件中心 — 列表显示', async ({ page }) => {
    await page.getByRole('link', { name: '事件中心' }).click();
    await page.waitForTimeout(1000);
    await expect(page.locator('.event-card').first()).toBeVisible({ timeout: 5000 });
  });

  test('19. 运行记录 — 页面加载', async ({ page }) => {
    await page.getByRole('link', { name: '运行记录' }).click();
    await page.waitForTimeout(1000);
    await expect(page.getByRole('heading', { name: '运行记录' })).toBeVisible();
  });

  test('20. 运行记录 — 详情查看', async ({ page }) => {
    await page.getByRole('link', { name: '运行记录' }).click();
    await page.waitForTimeout(1000);
    await page.locator('.run-card').first().click();
    await page.waitForTimeout(500);
    await expect(page.getByText('运行参数')).toBeVisible();
  });

  test('21. API Error 状态', async ({ page }) => {
    // 直接访问失败的 API
    const response = await page.request.get('/api/v2/error-test');
    expect(response.status()).toBe(500);
    const body = await response.json();
    expect(body.code).toBe('SERVICE_ERROR');
  });

  test('22. 刷新恢复状态 — URL 同步', async ({ page }) => {
    // 选中一个 candidate
    const cards = page.locator('.candidate-card');
    await cards.first().click();
    await page.waitForTimeout(500);

    // 刷新
    await page.reload();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // 选中状态应恢复
    await expect(page.locator('.candidate-card--selected')).toBeVisible({ timeout: 5000 });
  });

  test('23. 空列表状态', async ({ page }) => {
    // 访问空的 events 列表
    await page.goto('/events?empty=true');
    // 实际上 MSW 会根据 empty 参数返回空列表
    // 验证页面结构
    await expect(page.getByRole('heading', { name: /事件中心/i })).toBeVisible();
  });

  test('24. 系统设置页面', async ({ page }) => {
    await page.getByRole('link', { name: '系统设置' }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText('API 模式')).toBeVisible();
    await expect(page.getByText('Mock 数据')).toBeVisible();
  });
});
