// @ts-check
const { expect } = require('@playwright/test');
const { BasePage } = require('./BasePage');

/**
 * Metrics page page object model
 */
class MetricsPage extends BasePage {
  /**
   * @param {import('@playwright/test').Page} page
   */
  constructor(page) {
    super(page);

    // Selectors - look for section and div elements with metric content
    this.pageTitle = page.getByRole('heading', { name: 'Reliability Metrics', exact: true }).first();
    this.successRateChart = page.locator('[class*="chart"]').first();
    this.metricsCards = page.locator('section, div[class*="card"], div[class*="metric"]').filter({ hasText: /\d+/ });

    // Metric values
    this.successRate = page.getByText('Success Rate').first();
    this.checkpointRecovery = page.getByText(/CR|Checkpoint/i).first();
    this.humanInterventionRate = page.getByText(/human.*intervention/i).first();
    
    // Time range filters
    this.timeRangeFilter = page.getByRole('button').filter({ hasText: /time range|filter/i });
    this.last24Hours = page.getByText(/last 24 hours|24h/i);
    this.last7Days = page.getByText(/last 7 days|7d/i);
  }

  /**
   * Navigate to metrics page
   */
  async goto() {
    await this.navigate('/metrics');
    await this.waitForNetworkIdle();
  }

  /**
   * Verify metrics page is loaded
   */
  async expectLoaded() {
    await expect(this.pageTitle).toBeVisible();
  }

  /**
   * Get current metric value
   * @param {string} metricName
   * @returns {Promise<string>}
   */
  async getMetricValue(metricName) {
    const metricCard = this.page.locator('[class*="card"]').filter({ hasText: metricName });
    const valueElement = metricCard.locator('[class*="value"], [class*="number"]').first();
    return await valueElement.textContent();
  }
}

module.exports = { MetricsPage };
