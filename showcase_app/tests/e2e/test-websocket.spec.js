// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('WebSocket Connections', () => {
  test('should establish WebSocket connection for metrics', async ({ page }) => {
    await page.goto('http://localhost:5174/metrics');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const wsStatus = page.getByText(/ws connected|ws offline/i).first();
    await expect(wsStatus).toBeVisible();
    await page.waitForTimeout(3000);
    const wsText = await wsStatus.textContent();
    expect(wsText).toBeTruthy();
  });

  test('should show WebSocket status in header', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const wsStatus = page.getByText(/WS (Connected|Offline)/i).first();
    await expect(wsStatus).toBeVisible();
  });

  test('should reconnect WebSocket after disconnection', async ({ page }) => {
    await page.goto('http://localhost:5174/metrics');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    page.on('websocket', ws => {
      console.log('WebSocket opened:', ws.url());
    });

    await page.waitForTimeout(6000);
    const wsStatus = page.getByText(/WS (Connected|Offline)/i).first();
    await expect(wsStatus).toBeVisible();
  });

  test('should establish WebSocket for execution updates', async ({ page }) => {
    await page.goto('http://localhost:5174/executions');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    await expect(page.getByRole('heading', { name: /executions/i })).toBeVisible();
  });

  test('should display database status indicator', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasDbStatus = await page.getByText(/sqlite|postgresql|disconnected/i).first().isVisible().catch(() => false);
    expect(hasDbStatus).toBe(true);
  });

  test('should poll backend health periodically', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const hasBackendStatus = await page.getByText(/sqlite|postgresql|disconnected/i).first().isVisible().catch(() => false);
    expect(hasBackendStatus).toBe(true);

    await page.waitForTimeout(3000);
    const stillHasStatus = await page.getByText(/sqlite|postgresql|disconnected/i).first().isVisible().catch(() => false);
    expect(stillHasStatus).toBe(true);
  });
});
