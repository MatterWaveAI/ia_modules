// @ts-check
const { expect } = require('@playwright/test');

/**
 * Base page object model with common functionality
 */
class BasePage {
  /**
   * @param {import('@playwright/test').Page} page
   */
  constructor(page) {
    this.page = page;
    this.baseUrl = process.env.BASE_URL || 'http://localhost:5174';
  }

  /**
   * Navigate to a specific path
   * @param {string} path
   */
  async navigate(path) {
    await this.page.goto(`${this.baseUrl}${path}`);
  }

  /**
   * Wait for network to be idle
   */
  async waitForNetworkIdle() {
    await this.page.waitForLoadState('networkidle');
  }

  /**
   * Take a screenshot
   * @param {string} name
   */
  async screenshot(name) {
    await this.page.screenshot({
      path: `test-results/screenshots/${name}.png`,
      fullPage: true,
    });
  }
}

module.exports = { BasePage };
