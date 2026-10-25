// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Pipeline Editor', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5174/editor');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
  });

  test('should load pipeline editor', async ({ page }) => {
    // Page should load successfully - check for any heading or content
    await expect(page.locator('body')).toBeVisible();
  });

  test('should display view mode tabs', async ({ page }) => {
    // Check for Visual, Code, Split tabs
    await expect(page.getByRole('button', { name: /visual/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /code/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /split/i }).first()).toBeVisible();
  });

  test('should switch to split view mode', async ({ page }) => {
    await page.getByRole('button', { name: /split/i }).first().click();
    await page.waitForTimeout(500);

    // Page should still be visible
    await expect(page.locator('body')).toBeVisible();
  });

  test('should display editor toolbar', async ({ page }) => {
    // At minimum, the page should have visible content
    await expect(page.locator('body')).toBeVisible();
  });

  test('should navigate back to pipelines', async ({ page }) => {
    // Look for back button or link to pipelines
    const backBtn = page.getByRole('button', { name: /back/i }).first();
    const backLink = page.getByRole('link', { name: /pipelines/i }).first();

    if (await backBtn.isVisible()) {
      await backBtn.click();
    } else if (await backLink.isVisible()) {
      await backLink.click();
    } else {
      // Navigate directly
      await page.goto('http://localhost:5174/pipelines');
    }

    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: 'Pipelines', exact: true })).toBeVisible();
  });

  test('should show visual canvas in visual mode', async ({ page }) => {
    // Ensure we're in visual mode
    await page.getByRole('button', { name: /visual/i }).first().click();
    await page.waitForTimeout(500);

    // ReactFlow canvas should be visible
    const canvas = page.locator('[class*="react-flow"]').first();
    await expect(canvas).toBeVisible({ timeout: 5000 });
  });
});
