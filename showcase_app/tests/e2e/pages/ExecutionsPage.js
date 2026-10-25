// @ts-check
const { expect } = require('@playwright/test');
const { BasePage } = require('./BasePage');

/**
 * Executions page object model
 */
class ExecutionsPage extends BasePage {
  /**
   * @param {import('@playwright/test').Page} page
   */
  constructor(page) {
    super(page);
    
    // Selectors
    this.pageTitle = page.getByRole('heading', { name: /executions/i });
    this.executionsTable = page.locator('table').first();
    this.executionRows = page.locator('tbody tr');
    
    // Table headers
    this.jobIdHeader = page.getByRole('columnheader', { name: /job id/i });
    this.statusHeader = page.getByRole('columnheader', { name: /status/i });
    this.progressHeader = page.getByRole('columnheader', { name: /progress/i });
    
    // Status indicators
    this.successStatus = page.locator('[class*="success"], [class*="complete"]').first();
    this.pendingStatus = page.locator('[class*="pending"], [class*="running"]').first();
    this.failedStatus = page.locator('[class*="fail"], [class*="error"]').first();
    
    // HITL indicators
    this.hitlPendingBadge = page.locator('[class*="hitl"], [class*="approval"]').filter({ hasText: /pending/i });
    
    // Expand buttons
    this.expandButtons = page.getByRole('button', { name: /expand|show details/i });
  }

  /**
   * Navigate to executions page
   */
  async goto() {
    await this.navigate('/executions');
    await this.waitForNetworkIdle();
  }

  /**
   * Verify executions page is loaded
   */
  async expectLoaded() {
    await expect(this.pageTitle).toBeVisible();
  }

  /**
   * Get execution row by job ID or pipeline name
   * @param {string} identifier
   * @returns {import('@playwright/test').Locator}
   */
  getExecutionRow(identifier) {
    return this.executionRows.filter({ hasText: identifier }).first();
  }

  /**
   * Expand execution row details
   * @param {string} identifier
   */
  async expandExecutionRow(identifier) {
    const row = this.getExecutionRow(identifier);
    const expandButton = row.getByRole('button').first();
    await expandButton.click();
  }

  /**
   * Navigate to execution detail page
   * @param {string} identifier
   */
  async navigateToExecutionDetail(identifier) {
    const row = this.getExecutionRow(identifier);
    const linkButton = row.getByRole('link', { name: /view|detail/i });
    if (await linkButton.isVisible()) {
      await linkButton.click();
    } else {
      // Fallback: click on the row itself
      await row.click();
    }
  }

  /**
   * Get number of execution rows
   * @returns {Promise<number>}
   */
  async getExecutionCount() {
    return await this.executionRows.count();
  }
}

module.exports = { ExecutionsPage };
