import { chromium } from 'playwright';

const BASE = 'http://localhost:5173';

async function capture() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ deviceScaleFactor: 1 });

  // 1920×1080
  const page1920 = await context.newPage();
  await page1920.setViewportSize({ width: 1920, height: 1080 });
  await page1920.goto(`${BASE}/dashboard`, { waitUntil: 'networkidle' });
  await page1920.waitForTimeout(2000);
  await page1920.screenshot({ path: 'tests/screenshots/dashboard-1920x1080.png', fullPage: false });
  console.log('✓ Captured 1920×1080');

  // 1366×768
  const page1366 = await context.newPage();
  await page1366.setViewportSize({ width: 1366, height: 768 });
  await page1366.goto(`${BASE}/dashboard`, { waitUntil: 'networkidle' });
  await page1366.waitForTimeout(2000);
  await page1366.screenshot({ path: 'tests/screenshots/dashboard-1366x768.png', fullPage: false });
  console.log('✓ Captured 1366×768');

  await browser.close();
  console.log('Done');
}

capture().catch(console.error);
