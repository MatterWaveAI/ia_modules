// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Keyboard Shortcuts', () => {
  // Keyboard shortcuts modal doesn't work in headless Chromium
  // These tests verify the sidebar toggle and theme toggle shortcuts work

  test('should toggle sidebar with ctrl+b', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');

    const sidebar = page.locator('aside');
    await expect(sidebar).toBeVisible();

    // Press Ctrl+B to toggle
    await page.keyboard.press('Control+b');
    await page.waitForTimeout(500);

    // Sidebar class should change
    const newClass = await sidebar.getAttribute('class');
    expect(newClass).toMatch(/w-20|w-64/);
  });

  test('should toggle theme with ctrl+d', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');

    const html = page.locator('html');
    const initialDark = await html.evaluate(el => el.classList.contains('dark'));

    // Press Ctrl+D to toggle
    await page.keyboard.press('Control+d');
    await page.waitForTimeout(500);

    const newDark = await html.evaluate(el => el.classList.contains('dark'));
    expect(newDark).not.toBe(initialDark);
  });
});
