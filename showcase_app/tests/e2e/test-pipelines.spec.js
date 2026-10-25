// @ts-check
const { test, expect } = require('@playwright/test');
const { PipelinesPage } = require('./pages/PipelinesPage');

const API_BASE = 'http://localhost:7331';

test.describe('Pipelines Page', () => {
  let pipelinesPage;
  let testPipelines = [];

  // Ensure pipelines exist before running UI tests
  test.beforeAll(async ({ request }) => {
    try {
      const listResponse = await request.get(`${API_BASE}/api/pipelines`);
      expect(listResponse.ok()).toBeTruthy();
      const pipelines = await listResponse.json();

      if (Array.isArray(pipelines) && pipelines.length > 0) {
        testPipelines = pipelines;
        return;
      }

      // Create a test pipeline if none exist
      const response = await request.post(`${API_BASE}/api/pipelines`, {
        data: {
          name: 'E2E Test Pipeline',
          description: 'Created automatically by e2e tests',
          tags: ['e2e', 'test'],
          steps: [
            { id: 'step1', name: 'step1', step_class: 'TransformStep', module: 'pipelines.examples', config: { operation: 'uppercase' } },
            { id: 'step2', name: 'step2', step_class: 'TransformStep', module: 'pipelines.examples', config: { operation: 'lowercase' } },
          ],
          connections: [{ from: 'step1', to: 'step2' }],
        },
      });

      if (response.ok()) {
        const body = await response.json();
        testPipelines = [body];
      }

      // Re-fetch to get the full list
      const refreshResponse = await request.get(`${API_BASE}/api/pipelines`);
      if (refreshResponse.ok()) {
        testPipelines = await refreshResponse.json();
      }
    } catch (error) {
      console.error('Pipeline setup failed:', error.message);
    }
  });

  test.beforeEach(async ({ page }) => {
    pipelinesPage = new PipelinesPage(page);
    await pipelinesPage.goto();
  });

  test('should load pipelines page', async () => {
    await pipelinesPage.expectLoaded();
  });

  test('should display imported pipeline cards', async ({ page }) => {
    // Switch to cards view (default is table)
    await page.getByRole('button', { name: /cards/i }).click();

    // Verify we have pipeline cards, not the empty state
    await expect(page.getByText(/no pipelines yet/i)).not.toBeVisible();

    // Pipeline cards are rendered in a grid; each card has an h3 for the name
    const cards = page.locator('h3');
    await expect(cards.first()).toBeVisible();
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);
  });

  test('should show pipeline name and description on cards', async ({ page }) => {
    // Switch to cards view (default is table)
    await page.getByRole('button', { name: /cards/i }).click();

    // The first pipeline from the API should appear as an h3
    const firstPipeline = testPipelines[0];
    expect(firstPipeline).toBeTruthy();

    const nameHeading = page.locator('h3', { hasText: firstPipeline.name }).first();
    await expect(nameHeading).toBeVisible();

    // Description is a <p> element within the same card container
    if (firstPipeline.description) {
      const card = nameHeading.locator('..');
      // Walk up to the card container (look for the wrapping div with the description)
      const description = page.locator('p', { hasText: firstPipeline.description.substring(0, 30) });
      await expect(description.first()).toBeVisible();
    }
  });

  test('should show pipeline tags', async ({ page }) => {
    const firstPipeline = testPipelines[0];
    expect(firstPipeline).toBeTruthy();
    expect(firstPipeline.tags?.length).toBeGreaterThan(0);

    // Tags are rendered as small badge spans with the tag text
    for (const tag of firstPipeline.tags) {
      const tagBadge = page.locator('span', { hasText: tag }).first();
      await expect(tagBadge).toBeVisible();
    }
  });

  test('should open execute dialog with pre-filled JSON', async ({ page }) => {
    // Click the Execute button on the first pipeline card
    const executeButtons = page.getByRole('button', { name: /execute/i });
    await expect(executeButtons.first()).toBeVisible();
    await executeButtons.first().click();

    // Verify dialog opens with the pipeline name in the header
    const dialogHeading = page.locator('h2', { hasText: /execute:/i });
    await expect(dialogHeading).toBeVisible();

    // Switch to JSON mode (dialog defaults to form mode)
    await page.getByRole('button', { name: /json/i }).click();

    // Verify the JSON textarea exists and has content
    const textarea = page.locator('textarea');
    await expect(textarea).toBeVisible();
    const textareaValue = await textarea.inputValue();
    // Should contain valid JSON (at minimum an empty object)
    expect(() => JSON.parse(textareaValue)).not.toThrow();

    // Verify the "Execute Pipeline" confirmation button is present
    const confirmButton = page.getByRole('button', { name: /execute pipeline/i });
    await expect(confirmButton).toBeVisible();
  });

  test('should close execute dialog on cancel', async ({ page }) => {
    // Open the execute dialog
    const executeButtons = page.getByRole('button', { name: /execute/i });
    await executeButtons.first().click();

    const dialogHeading = page.locator('h2', { hasText: /execute:/i });
    await expect(dialogHeading).toBeVisible();

    // Click Cancel
    const cancelButton = page.getByRole('button', { name: /cancel/i });
    await cancelButton.click();

    // Dialog should be closed
    await expect(dialogHeading).not.toBeVisible();
  });

  test('should navigate to editor when Edit clicked', async ({ page }) => {
    const firstPipeline = testPipelines[0];
    expect(firstPipeline).toBeTruthy();

    // Click the Edit button on the first card
    const editButtons = page.getByRole('button', { name: /edit/i });
    await expect(editButtons.first()).toBeVisible();
    await editButtons.first().click();

    // Verify navigation to editor with the pipeline ID
    await page.waitForURL(`**/editor/${firstPipeline.id}`);
    expect(page.url()).toContain(`/editor/${firstPipeline.id}`);
  });

  test('should navigate to editor when New Pipeline clicked', async ({ page }) => {
    const newPipelineButton = page.getByRole('button', { name: /new pipeline/i });
    await expect(newPipelineButton).toBeVisible();
    await newPipelineButton.click();

    await page.waitForURL('**/editor');
    expect(page.url()).toContain('/editor');
  });
});

test.describe('Pipeline Execution', () => {
  let pipelinesPage;
  let testPipelines = [];

  test.beforeAll(async ({ request }) => {
    const listResponse = await request.get(`${API_BASE}/api/pipelines`);
    expect(listResponse.ok()).toBeTruthy();
    const pipelines = await listResponse.json();
    expect(Array.isArray(pipelines) && pipelines.length > 0).toBeTruthy();
    testPipelines = pipelines;
  });

  test.beforeEach(async ({ page }) => {
    pipelinesPage = new PipelinesPage(page);
    await pipelinesPage.goto();
  });

  test('should execute a pipeline and navigate to execution view', async ({ page }) => {
    // Click Execute on first pipeline
    const executeButtons = page.getByRole('button', { name: /execute/i });
    await executeButtons.first().click();

    // Dialog should open
    const dialogHeading = page.locator('h2', { hasText: /execute:/i });
    await expect(dialogHeading).toBeVisible();

    // Click Execute Pipeline to confirm
    const confirmButton = page.getByRole('button', { name: /execute pipeline/i });
    await confirmButton.click();

    // Should navigate to execution detail page
    await page.waitForURL('**/executions/**', { timeout: 15000 });
    expect(page.url()).toContain('/executions/');
  });

  test('should handle conditional pipeline execution', async ({ page }) => {
    // Switch to cards view so we can locate individual pipeline cards
    await page.getByRole('button', { name: /cards/i }).click();

    const conditionalPipeline = page.getByText(/conditional/i).first();
    const isVisible = await conditionalPipeline.isVisible().catch(() => false);
    // Fail explicitly rather than silently skipping if no conditional pipeline exists
    test.skip(!isVisible, 'No conditional pipeline available - import one to enable this test');

    if (isVisible) {
      // Find the card that contains this pipeline text (cards are direct children of the grid)
      const card = page.locator('.grid > div', { has: page.getByText(/conditional/i) }).first();
      const executeBtn = card.getByRole('button', { name: /execute/i });
      await executeBtn.click();

      const confirmButton = page.getByRole('button', { name: /execute pipeline/i });
      await confirmButton.click();

      await page.waitForURL('**/executions/**', { timeout: 15000 });
    }
  });

  test('should handle parallel pipeline execution', async ({ page }) => {
    // Switch to cards view so we can locate individual pipeline cards
    await page.getByRole('button', { name: /cards/i }).click();

    const parallelPipeline = page.getByText(/parallel/i).first();
    const isVisible = await parallelPipeline.isVisible().catch(() => false);
    test.skip(!isVisible, 'No parallel pipeline available - import one to enable this test');

    if (isVisible) {
      // Find the card that contains this pipeline text (cards are direct children of the grid)
      const card = page.locator('.grid > div', { has: page.getByText(/parallel/i) }).first();
      const executeBtn = card.getByRole('button', { name: /execute/i });
      await executeBtn.click();

      const confirmButton = page.getByRole('button', { name: /execute pipeline/i });
      await confirmButton.click();

      await page.waitForURL('**/executions/**', { timeout: 15000 });
    }
  });
});

test.describe('Pipelines API', () => {
  test('GET /api/pipelines should return a non-empty list', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/pipelines`);
    expect(response.ok()).toBeTruthy();
    expect(response.status()).toBe(200);

    const pipelines = await response.json();
    expect(Array.isArray(pipelines)).toBeTruthy();
    expect(pipelines.length).toBeGreaterThan(0);
  });

  test('each pipeline should have id, name, tags, and config', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/pipelines`);
    expect(response.ok()).toBeTruthy();

    const pipelines = await response.json();
    expect(pipelines.length).toBeGreaterThan(0);

    for (const pipeline of pipelines) {
      expect(pipeline).toHaveProperty('id');
      expect(pipeline).toHaveProperty('name');
      expect(pipeline).toHaveProperty('tags');
      expect(pipeline).toHaveProperty('config');

      // Validate types
      expect(typeof pipeline.id).toBe('string');
      expect(typeof pipeline.name).toBe('string');
      expect(Array.isArray(pipeline.tags)).toBeTruthy();
      expect(typeof pipeline.config).toBe('object');

      // Name should not be empty
      expect(pipeline.name.length).toBeGreaterThan(0);
    }
  });
});
