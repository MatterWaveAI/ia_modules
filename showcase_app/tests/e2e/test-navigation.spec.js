// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Navigation & Routing', () => {
  test('should navigate through all main pages', async ({ page }) => {
    // Start at home
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /ia modules showcase/i }).first()).toBeVisible();

    // Navigate to pipelines
    await page.locator('aside a').filter({ hasText: 'Pipelines' }).first().click();
    await page.waitForURL('**/pipelines');
    await expect(page.getByRole('heading', { name: /pipelines/i }).first()).toBeVisible();

    // Navigate to metrics
    await page.locator('aside a').filter({ hasText: 'Metrics' }).first().click();
    await page.waitForURL('**/metrics');
    await expect(page.getByRole('heading', { name: /metrics/i }).first()).toBeVisible();

    // Navigate to patterns
    await page.locator('aside a').filter({ hasText: 'Patterns' }).first().click();
    await page.waitForURL('**/patterns');
    await expect(page.getByRole('heading', { name: /patterns/i }).first()).toBeVisible();
  });

  test('should handle direct URL navigation', async ({ page }) => {
    // Direct navigation to pipelines
    await page.goto('http://localhost:5174/pipelines');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /pipelines/i }).first()).toBeVisible();

    // Direct navigation to metrics
    await page.goto('http://localhost:5174/metrics');
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /metrics/i }).first()).toBeVisible();
  });

  test('should maintain navigation state', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');

    // Navigate to pipelines
    await page.locator('aside a').filter({ hasText: 'Pipelines' }).first().click();
    await page.waitForURL('**/pipelines');

    // Go back home
    await page.locator('aside a').filter({ hasText: 'Home' }).first().click();
    await page.waitForURL('**/');
    await expect(page.getByRole('heading', { name: /ia modules showcase/i }).first()).toBeVisible();
  });
});
