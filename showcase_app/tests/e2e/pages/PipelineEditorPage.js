// @ts-check
const { expect } = require('@playwright/test');
const { BasePage } = require('./BasePage');

/**
 * Pipeline Editor page object model
 */
class PipelineEditorPage extends BasePage {
  /**
   * @param {import('@playwright/test').Page} page
   */
  constructor(page) {
    super(page);
    
    // Selectors
    this.pageTitle = page.getByRole('heading', { name: /pipeline editor/i });
    
    // View mode tabs
    this.visualTab = page.getByRole('button', { name: /visual/i });
    this.codeTab = page.getByRole('button', { name: /code/i });
    this.splitTab = page.getByRole('button', { name: /split/i });
    
    // Toolbar buttons - scope to toolbar and use .first() to avoid matching ReactFlow buttons
    this.saveButton = page.locator('[class*="toolbar"]').getByRole('button', { name: /save/i }).first();
    this.runButton = page.locator('[class*="toolbar"]').getByRole('button', { name: /run/i }).first();
    this.loadButton = page.locator('[class*="toolbar"]').getByRole('button', { name: /load/i }).first();
    this.backButton = page.locator('[class*="toolbar"]').getByRole('button', { name: /back/i }).first();

    // Code editor
    this.codeEditor = page.getByRole('code').first();
    this.jsonValidation = page.locator('[class*="validation"], [class*="error"]').first();

    // Load pipeline dialog - be flexible with dialog text
    this.loadDialog = page.getByRole('dialog');
    this.loadDialogPipelineList = page.locator('[class*="pipeline-item"], [class*="list-item"]');
    
    // Execution results
    this.executionResults = page.locator('[class*="execution-result"], [class*="results"]');
    this.executionsTable = page.locator('table').first();
    
    // HITL modal
    this.hitlModal = page.getByRole('dialog').filter({ hasText: /human.*approval|hitl/i });
  }

  /**
   * Navigate to editor page
   */
  async goto() {
    await this.navigate('/editor');
    await this.waitForNetworkIdle();
  }

  /**
   * Verify editor page is loaded
   */
  async expectLoaded() {
    await expect(this.pageTitle).toBeVisible();
  }

  /**
   * Switch to visual view mode
   */
  async switchToVisualMode() {
    await this.visualTab.click();
  }

  /**
   * Switch to code view mode
   */
  async switchToCodeMode() {
    await this.codeTab.click();
  }

  /**
   * Switch to split view mode
   */
  async switchToSplitMode() {
    await this.splitTab.click();
  }

  /**
   * Save current pipeline
   */
  async savePipeline() {
    await this.saveButton.click();
  }

  /**
   * Run the pipeline
   */
  async runPipeline() {
    await this.runButton.click();
  }

  /**
   * Open load pipeline dialog
   */
  async openLoadDialog() {
    await this.loadButton.click();
    await expect(this.loadDialog).toBeVisible();
  }

  /**
   * Load a pipeline by name
   * @param {string} pipelineName
   */
  async loadPipeline(pipelineName) {
    await this.openLoadDialog();
    const pipelineItem = this.loadDialogPipelineList.filter({ hasText: pipelineName });
    await pipelineItem.click();
  }
}

module.exports = { PipelineEditorPage };
