// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Agents Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/agents');
    await page.waitForLoadState('networkidle');
  });

  test('should load agents page', async ({ page }) => {
    await expect(page.locator('main h1').first()).toContainText(/agent/i);
  });

  test('should display summary cards', async ({ page }) => {
    await expect(page.getByText(/active agents/i).first()).toBeVisible();
    await expect(page.getByText(/total executions/i).first()).toBeVisible();
  });

  test('should show agent table or empty state', async ({ page }) => {
    const hasTable = await page.locator('table').first().isVisible().catch(() => false);
    const hasEmpty = await page.getByText(/no agent data/i).first().isVisible().catch(() => false);
    expect(hasTable || hasEmpty).toBeTruthy();
  });
});

test.describe('Agents API', () => {
  const API_BASE = 'http://localhost:7331';

  test('should get agent metrics via API', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/telemetry/agents`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toBeDefined();
  });
});
