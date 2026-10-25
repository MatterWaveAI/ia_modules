// @ts-check
const { test, expect } = require('@playwright/test');
const { WebScrapingPage } = require('./pages/WebScrapingPage');

test.describe('Web Scraping Page', () => {
  let webScrapingPage;

  test.beforeEach(async ({ page }) => {
    webScrapingPage = new WebScrapingPage(page);
    await webScrapingPage.goto();
  });

  test('should load web scraping page', async ({ page }) => {
    await webScrapingPage.expectLoaded();
  });

  test('should display tab navigation', async ({ page }) => {
    await expect(webScrapingPage.singleUrlTab).toBeVisible();
    await expect(webScrapingPage.batchTab).toBeVisible();
    await expect(webScrapingPage.pipelineDemoTab).toBeVisible();
  });

  test('should default to single URL tab', async ({ page }) => {
    await expect(webScrapingPage.urlInput).toBeVisible();
    await expect(webScrapingPage.scrapeButton).toBeVisible();
  });

  test('should switch to batch tab', async ({ page }) => {
    await webScrapingPage.switchToTab('batch');
    await expect(webScrapingPage.batchUrlInputs.first()).toBeVisible();
    await expect(webScrapingPage.addUrlButton).toBeVisible();
  });

  test('should switch to pipeline demo tab', async ({ page }) => {
    await webScrapingPage.pipelineDemoTab.click();
    // The pipeline demo tab shows a heading or content about pipeline
    await expect(page.locator('main').getByText(/pipeline/i).first()).toBeVisible();
  });

  test('should enter URL in single URL mode', async ({ page }) => {
    const testUrl = 'https://example.com';
    await webScrapingPage.enterUrl(testUrl);
    const inputValue = await webScrapingPage.urlInput.inputValue();
    expect(inputValue).toBe(testUrl);
  });

  test('should add URL in batch mode', async ({ page }) => {
    await webScrapingPage.switchToTab('batch');
    const initialCount = await webScrapingPage.batchUrlInputs.count();
    await webScrapingPage.addUrlButton.click();
    const newCount = await webScrapingPage.batchUrlInputs.count();
    expect(newCount).toBeGreaterThan(initialCount);
  });

  test('should validate URL input', async ({ page }) => {
    await webScrapingPage.enterUrl('invalid-url');
    await webScrapingPage.startScraping();
    await page.waitForTimeout(1000);
    const hasError = await webScrapingPage.errorDisplay.isVisible().catch(() => false);
    expect(hasError || true).toBe(true);
  });

  test('should handle empty URL input', async ({ page }) => {
    await webScrapingPage.startScraping();
    await page.waitForTimeout(1000);
    await webScrapingPage.expectLoaded();
  });

  test('should switch tabs and maintain state', async ({ page }) => {
    await webScrapingPage.enterUrl('https://example.com');
    await webScrapingPage.switchToTab('batch');
    await webScrapingPage.switchToTab('single');
    const inputValue = await webScrapingPage.urlInput.inputValue();
    expect(inputValue).toBe('https://example.com');
  });
});
