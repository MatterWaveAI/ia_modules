// @ts-check
const { expect } = require('@playwright/test');
const { BasePage } = require('./BasePage');

/**
 * Home page object model
 */
class HomePage extends BasePage {
  /**
   * @param {import('@playwright/test').Page} page
   */
  constructor(page) {
    super(page);

    // Selectors scoped to sidebar nav to avoid mobile menu duplicates
    // Using role-based selectors within the aside container
    const sidebarNav = page.locator('aside nav');
    this.navbar = sidebarNav;
    this.homeLink = sidebarNav.getByRole('link', { name: /home/i });
    this.pipelinesLink = sidebarNav.getByRole('link', { name: /pipelines/i });
    this.metricsLink = sidebarNav.getByRole('link', { name: /metrics/i });
    this.patternsLink = sidebarNav.getByRole('link', { name: /patterns/i });
    
    // Hero section - use case-insensitive regex for resilience
    this.heroSection = page.getByRole('heading', { name: /welcome to ia modules showcase/i });
    this.quickStartButton = page.getByRole('button', { name: /quick start|get started/i });
    
    // Feature cards - use the grid layout with heading children
    this.featureCards = page.locator('[class*="grid"] > div').filter({ has: page.locator('h3') });
  }

  /**
   * Navigate to home page
   */
  async goto() {
    await this.navigate('/');
    await this.waitForNetworkIdle();
  }

  /**
   * Verify home page is loaded
   */
  async expectLoaded() {
    await expect(this.heroSection).toBeVisible();
  }
}

module.exports = { HomePage };
