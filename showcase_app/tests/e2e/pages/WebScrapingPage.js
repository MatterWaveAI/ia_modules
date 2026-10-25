// @ts-check
const { expect } = require('@playwright/test');
const { BasePage } = require('./BasePage');

/**
 * Web Scraping page object model
 */
class WebScrapingPage extends BasePage {
  /**
   * @param {import('@playwright/test').Page} page
   */
  constructor(page) {
    super(page);
    
    // Selectors
    this.pageTitle = page.getByRole('heading', { name: /web scraping tools/i });

    // Tabs - these are regular buttons, not role='tab'
    this.singleUrlTab = page.getByRole('button', { name: /single url/i });
    this.batchTab = page.getByRole('button', { name: /batch urls/i });
    this.pipelineDemoTab = page.getByRole('button', { name: /pipeline demo/i });

    // Single URL tab
    this.urlInput = page.locator('input[type="url"]').first();
    this.scrapeButton = page.getByRole('button', { name: /scrape url/i });

    // Batch tab
    this.batchUrlInputs = page.locator('input[type="url"]');
    this.addUrlButton = page.getByRole('button', { name: /\+ add url/i });
    this.removeUrlButtons = page.getByRole('button', { name: /remove/i });

    // Results
    this.resultsSection = page.locator('[class*="results"], [class*="scrape-result"]');
    this.successBadge = page.locator('[class*="green"]').filter({ hasText: /success/i }).first();
    this.errorBadge = page.locator('[class*="red"]').filter({ hasText: /fail/i }).first();

    // Export
    this.exportButton = page.getByRole('button', { name: /export/i });

    // Error display
    this.errorDisplay = page.locator('[class*="red"]').filter({ hasText: /error/i }).first();
  }

  /**
   * Navigate to web scraping page
   */
  async goto() {
    await this.navigate('/web-scraping');
    await this.waitForNetworkIdle();
  }

  /**
   * Verify web scraping page is loaded
   */
  async expectLoaded() {
    await expect(this.pageTitle).toBeVisible();
  }

  /**
   * Switch to a specific tab
   * @param {string} tabName - 'single', 'batch', or 'pipeline'
   */
  async switchToTab(tabName) {
    switch(tabName) {
      case 'single':
        await this.singleUrlTab.click();
        break;
      case 'batch':
        await this.batchTab.click();
        break;
      case 'pipeline':
        await this.pipelineDemoTab.click();
        break;
      default:
        throw new Error(`Unknown tab: ${tabName}. Use 'single', 'batch', or 'pipeline'.`);
    }
  }

  /**
   * Enter URL for single scraping
   * @param {string} url
   */
  async enterUrl(url) {
    await this.urlInput.fill(url);
  }

  /**
   * Start scraping
   */
  async startScraping() {
    await this.scrapeButton.click();
  }
}

module.exports = { WebScrapingPage };
