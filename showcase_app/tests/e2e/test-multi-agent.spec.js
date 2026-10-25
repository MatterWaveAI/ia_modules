// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Multi-Agent Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/multi-agent');
    await page.waitForLoadState('networkidle');
  });

  test('should load multi-agent page', async ({ page }) => {
    const heading = page.locator('main h1, main h2').first();
    await expect(heading).toBeVisible();
  });

  test('should display page content', async ({ page }) => {
    // Page should have meaningful content
    const mainContent = page.locator('main');
    await expect(mainContent).toBeVisible();
    const text = await mainContent.textContent();
    expect(text.length).toBeGreaterThan(50);
  });
});
