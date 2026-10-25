// @ts-check
const { test, expect } = require('@playwright/test');
const { HomePage } = require('./pages/HomePage');

test.describe('Home Page', () => {
  let homePage;

  test.beforeEach(async ({ page }) => {
    homePage = new HomePage(page);
    await homePage.goto();
  });

  test('should load home page successfully @smoke', async ({ page }) => {
    await homePage.expectLoaded();
  });

  test('should display navigation menu', async ({ page }) => {
    await expect(homePage.navbar).toBeVisible();
    await expect(homePage.homeLink).toBeVisible();
    await expect(homePage.pipelinesLink).toBeVisible();
    await expect(homePage.metricsLink).toBeVisible();
    await expect(homePage.patternsLink).toBeVisible();
  });

  test('should navigate to pipelines page', async ({ page }) => {
    await homePage.pipelinesLink.click();
    await page.waitForURL('**/pipelines');
    // Scope to <main> to avoid matching the sidebar's "IA Modules" h1
    await expect(page.locator('main h1').first()).toHaveText('Pipelines');
  });

  test('should navigate to metrics page', async ({ page }) => {
    await homePage.metricsLink.click();
    await page.waitForURL('**/metrics');
    await expect(page.locator('main h1').first()).toContainText(/reliability metrics/i);
  });

  test('should navigate to patterns page', async ({ page }) => {
    await homePage.patternsLink.click();
    await page.waitForURL('**/patterns');
    await expect(page.getByRole('heading', { name: /agentic design patterns/i })).toBeVisible();
  });

  test('should display feature cards', async ({ page }) => {
    // Feature cards are in a grid layout with h3 headings
    const featureCards = homePage.featureCards;
    const count = await featureCards.count();
    expect(count).toBeGreaterThan(0);
  });

  test('should be responsive on mobile viewport', async ({ browser }) => {
    const mobilePage = await browser.newPage({
      viewport: { width: 375, height: 667 }
    });

    const mobileHomePage = new HomePage(mobilePage);
    await mobileHomePage.goto();
    await mobileHomePage.expectLoaded();

    // Verify mobile navigation exists
    await expect(mobilePage.locator('aside nav')).toBeVisible();

    await mobilePage.close();
  });
});
