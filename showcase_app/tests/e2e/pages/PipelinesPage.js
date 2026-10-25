// @ts-check
const { expect } = require('@playwright/test');
const { BasePage } = require('./BasePage');

/**
 * Pipelines page page object model
 */
class PipelinesPage extends BasePage {
  /**
   * @param {import('@playwright/test').Page} page
   */
  constructor(page) {
    super(page);

    // Selectors
    this.pageTitle = page.getByRole('heading', { name: 'Pipelines', exact: true });
    this.pipelineList = page.locator('[class*="pipeline"], [class*="card"]').first();
    this.executeButton = page.getByRole('button', { name: /execute|run/i });
    
    // Pipeline execution
    this.executionStatus = page.locator('[class*="status"], [class*="execution"]');
    this.stepList = page.locator('[class*="step"]');
    this.outputSection = page.locator('[class*="output"], [class*="result"]');
    
    // Pipeline types
    this.simplePipeline = page.getByText(/simple.*pipeline/i);
    this.conditionalPipeline = page.getByText(/conditional/i);
    this.parallelPipeline = page.getByText(/parallel/i);
    this.humanInLoopPipeline = page.getByText(/human.*loop|hitl/i);
  }

  /**
   * Navigate to pipelines page
   */
  async goto() {
    await this.navigate('/pipelines');
    await this.waitForNetworkIdle();
  }

  /**
   * Verify pipelines page is loaded
   */
  async expectLoaded() {
    await expect(this.pageTitle).toBeVisible();
  }

  /**
   * Execute a pipeline by name
   * @param {string} pipelineName
   */
  async executePipeline(pipelineName) {
    const pipelineCard = this.page.getByRole('button').filter({ hasText: pipelineName });
    await pipelineCard.click();
    await this.executeButton.click();
  }

  /**
   * Wait for execution to complete
   */
  async waitForExecutionComplete() {
    await expect(this.executionStatus).toContainText(/complete|success/i, { timeout: 30000 });
  }
}

module.exports = { PipelinesPage };
