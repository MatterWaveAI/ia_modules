// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Executions Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/executions');
    await page.waitForLoadState('networkidle');
  });

  test('should load executions page', async ({ page }) => {
    await expect(page.locator('main h1').first()).toHaveText('Executions');
  });

  test('should display executions table or empty state', async ({ page }) => {
    const hasEmpty = await page.getByText(/no executions yet/i).isVisible().catch(() => false);
    if (hasEmpty) {
      await expect(page.getByText(/no executions yet/i)).toBeVisible();
    } else {
      // Table should have expected headers
      await expect(page.getByText(/job id|pipeline|status/i).first()).toBeVisible();
    }
  });

  test('should have monitoring subtitle', async ({ page }) => {
    await expect(page.getByText(/monitor pipeline execution/i)).toBeVisible();
  });
});

test.describe('Executions API', () => {
  const API_BASE = 'http://localhost:7331';

  test('should list executions via API', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/execute`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
  });
});
