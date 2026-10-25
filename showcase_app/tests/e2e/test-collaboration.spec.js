// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Collaboration Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/collaboration');
    await page.waitForLoadState('networkidle');
  });

  test('should load collaboration page', async ({ page }) => {
    await expect(page.locator('main h1').first()).toContainText(/collaboration/i);
  });

  test('should display pattern cards', async ({ page }) => {
    await expect(page.getByText(/consensus/i).first()).toBeVisible();
    await expect(page.getByText(/debate/i).first()).toBeVisible();
    await expect(page.getByText(/hierarchical/i).first()).toBeVisible();
    await expect(page.getByText(/peer/i).first()).toBeVisible();
  });

  test('should show configuration when pattern selected', async ({ page }) => {
    await page.getByText(/consensus/i).first().click();
    // Configuration panel should appear with input fields
    await page.waitForTimeout(500);
    const hasConfig = await page.locator('textarea, input[type="text"], input[type="number"]').first().isVisible().catch(() => false);
    expect(hasConfig).toBeTruthy();
  });

  test('should show run button when pattern selected', async ({ page }) => {
    await page.getByText(/debate/i).first().click();
    await page.waitForTimeout(500);
    await expect(page.getByRole('button', { name: /run/i }).first()).toBeVisible();
  });
});

test.describe('Collaboration API', () => {
  const API_BASE = 'http://localhost:7331';

  test('should list collaboration patterns', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/collaboration/patterns`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('patterns');
    expect(Array.isArray(data.patterns)).toBeTruthy();
    expect(data.patterns.length).toBeGreaterThan(0);
  });

  test.skip('should run consensus pattern via API', async ({ request }) => {
    // Skipped: LLM calls exceed timeout even at 120s
    const response = await request.post(`${API_BASE}/api/collaboration/consensus`, {
      data: {
        topic: 'Should we use microservices?',
        agents: ['architect', 'developer', 'ops'],
        strategy: 'majority',
        max_iterations: 2
      }
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('pattern', 'consensus');
    expect(data).toHaveProperty('result');
  });

  test.skip('should run debate pattern via API', async ({ request }) => {
    // Skipped: LLM calls exceed timeout even at 120s
    const response = await request.post(`${API_BASE}/api/collaboration/debate`, {
      data: {
        topic: 'REST vs GraphQL',
        proponents: ['rest_advocate'],
        opponents: ['graphql_advocate'],
        moderator: 'tech_lead',
        rounds: 1
      }
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('pattern', 'debate');
  });
});
