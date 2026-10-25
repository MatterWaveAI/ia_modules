// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Plugins Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/plugins');
    await page.waitForLoadState('networkidle');
  });

  test('should load plugins page', async ({ page }) => {
    await expect(page.locator('main h1').first()).toContainText('Plugins');
  });

  test('should display plugin cards or loading state', async ({ page }) => {
    // Wait for content to load
    await page.waitForTimeout(1000);
    const hasPlugins = await page.getByText(/loaded|active/i).first().isVisible().catch(() => false);
    const hasEmpty = await page.getByText(/no plugins/i).first().isVisible().catch(() => false);
    expect(hasPlugins || hasEmpty).toBeTruthy();
  });

  test('should have filter buttons', async ({ page }) => {
    await expect(page.getByRole('button', { name: /all/i }).first()).toBeVisible();
  });

  test('should show plugin details when card clicked', async ({ page }) => {
    await page.waitForTimeout(1000);
    const firstPlugin = page.locator('[class*="card"], [class*="plugin"]').first();
    if (await firstPlugin.isVisible().catch(() => false)) {
      await firstPlugin.click();
      // Detail panel should appear
      await expect(page.getByText(/version|type|author/i).first()).toBeVisible();
    }
  });
});

test.describe('Plugins API', () => {
  const API_BASE = 'http://localhost:7331';

  test('should list plugins via API', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/plugins`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
  });

  test('should get plugin details via API', async ({ request }) => {
    const listResponse = await request.get(`${API_BASE}/api/plugins`);
    const plugins = await listResponse.json();
    if (plugins.length > 0) {
      const response = await request.get(`${API_BASE}/api/plugins/${plugins[0].name}`);
      expect(response.ok()).toBeTruthy();
      const detail = await response.json();
      expect(detail).toHaveProperty('name');
      expect(detail).toHaveProperty('version');
    }
  });
});
