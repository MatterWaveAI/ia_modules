// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('LLM Usage Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/llm');
    await page.waitForLoadState('networkidle');
  });

  test('should load LLM usage page', async ({ page }) => {
    await expect(page.locator('main h1').first()).toContainText(/llm/i);
  });

  test('should display summary cards', async ({ page }) => {
    await expect(page.getByText(/total requests/i).first()).toBeVisible();
    await expect(page.getByText(/total cost/i).first()).toBeVisible();
    await expect(page.getByText(/models used/i).first()).toBeVisible();
  });

  test('should have chart toggle buttons', async ({ page }) => {
    await expect(page.getByRole('button', { name: /cost/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /requests/i }).first()).toBeVisible();
  });

  test('should show model table or empty state', async ({ page }) => {
    const hasTable = await page.locator('table').first().isVisible().catch(() => false);
    const hasEmpty = await page.getByText(/no llm usage/i).first().isVisible().catch(() => false);
    expect(hasTable || hasEmpty).toBeTruthy();
  });
});

test.describe('LLM Usage API', () => {
  const API_BASE = 'http://localhost:7331';

  test('should get LLM usage metrics', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/telemetry/llm/usage`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toBeDefined();
  });
});
