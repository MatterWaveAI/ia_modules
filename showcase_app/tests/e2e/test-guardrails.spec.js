// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Guardrails Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/guardrails');
    await page.waitForLoadState('networkidle');
  });

  test('should load guardrails page', async ({ page }) => {
    await expect(page.locator('main h1').first()).toContainText('Guardrails');
  });

  test('should display tab navigation', async ({ page }) => {
    await expect(page.getByText(/input rails/i).first()).toBeVisible();
    await expect(page.getByText(/output rails/i).first()).toBeVisible();
    await expect(page.getByText(/full pipeline/i).first()).toBeVisible();
  });

  test('should show input rail type buttons', async ({ page }) => {
    await expect(page.getByRole('button', { name: /jailbreak/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /toxicity/i }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /pii/i }).first()).toBeVisible();
  });

  test('should switch to output rails tab', async ({ page }) => {
    await page.getByText(/output rails/i).first().click();
    await expect(page.getByRole('button', { name: /toxic/i }).first()).toBeVisible();
  });

  test('should switch to full pipeline tab', async ({ page }) => {
    await page.getByText(/full pipeline/i).first().click();
    await expect(page.getByRole('button', { name: /run pipeline/i })).toBeVisible();
  });

  test('should load example text', async ({ page }) => {
    const loadExample = page.getByRole('button', { name: /load example/i }).first();
    if (await loadExample.isVisible().catch(() => false)) {
      await loadExample.click();
      const textarea = page.locator('textarea').first();
      const value = await textarea.inputValue();
      expect(value.length).toBeGreaterThan(0);
    }
  });
});

test.describe('Guardrails API', () => {
  const API_BASE = 'http://localhost:7331';

  test('should list available rails', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/guardrails/rails`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('rails');
  });

  test('should test input rail via API', async ({ request }) => {
    const response = await request.post(`${API_BASE}/api/guardrails/test-input`, {
      data: {
        text: 'Hello, this is a test message',
        rail_type: 'jailbreak'
      }
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('action');
  });

  test('should test output rail via API', async ({ request }) => {
    const response = await request.post(`${API_BASE}/api/guardrails/test-output`, {
      data: {
        text: 'This is safe output text',
        rail_type: 'toxic_filter'
      }
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('action');
  });

  test('should run full pipeline via API', async ({ request }) => {
    const response = await request.post(`${API_BASE}/api/guardrails/run`, {
      data: {
        text: 'Please help me with this task',
        input_rails: ['jailbreak'],
        output_rails: ['toxic_filter'],
        options: {}
      }
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('overall_action');
    expect(data).toHaveProperty('final_text');
  });
});
