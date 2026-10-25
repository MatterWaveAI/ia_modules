// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Patterns Page Interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5174/patterns');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
  });

  test('should load patterns page', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Agentic Design Patterns' })).toBeVisible();
  });

  test('should display all pattern cards', async ({ page }) => {
    // Patterns are listed in the sidebar
    await expect(page.getByText('Reflection')).toBeVisible();
    await expect(page.getByText('Planning')).toBeVisible();
    await expect(page.getByText('Tool Use')).toBeVisible();
    await expect(page.getByText('Agentic RAG')).toBeVisible();
    await expect(page.getByText('Metacognition')).toBeVisible();
  });

  test('should select reflection pattern', async ({ page }) => {
    await page.getByText('Reflection').first().click();
    await page.waitForTimeout(300);
    // Description should be visible
    await expect(page.getByText(/self-critique|iterative improvement/i)).toBeVisible();
  });

  test('should select planning pattern', async ({ page }) => {
    await page.getByText('Planning').first().click();
    await page.waitForTimeout(300);
    await expect(page.getByText(/multi-step|goal decomposition/i)).toBeVisible();
  });

  test('should select tool use pattern', async ({ page }) => {
    await page.getByText('Tool Use').first().click();
    await page.waitForTimeout(300);
    await expect(page.getByText(/tool selection|dynamic/i)).toBeVisible();
  });

  test('should select agentic RAG pattern', async ({ page }) => {
    await page.getByText('Agentic RAG').first().click();
    await page.waitForTimeout(300);
    await expect(page.getByText(/query refinement|retrieval/i)).toBeVisible();
  });

  test('should select metacognition pattern', async ({ page }) => {
    await page.getByText('Metacognition').first().click();
    await page.waitForTimeout(300);
    await expect(page.getByText(/self-monitoring|adaptation/i)).toBeVisible();
  });

  test.skip('should switch between patterns and see different content', async ({ page }) => {
    // Skipped: LLM calls exceed timeout even at 120s
    // Select reflection
    await page.getByText('Reflection').first().click();
    await page.waitForTimeout(300);
    const reflectionContent = await page.locator('main').textContent();

    // Switch to planning
    await page.getByText('Planning').first().click();
    await page.waitForTimeout(300);
    const planningContent = await page.locator('main').textContent();

    expect(reflectionContent).not.toBe(planningContent);
  });

  test('should display pattern descriptions', async ({ page }) => {
    // Each pattern has a description
    await expect(page.getByText(/self-critique|iterative/i)).toBeVisible();
    await expect(page.getByText(/multi-step|goal/i)).toBeVisible();
    await expect(page.getByText(/dynamic tool/i)).toBeVisible();
  });
});
