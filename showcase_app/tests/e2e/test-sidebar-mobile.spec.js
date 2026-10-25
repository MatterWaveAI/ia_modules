// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Sidebar & Mobile Menu', () => {
  test('should display sidebar by default', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    
    const sidebar = page.locator('aside');
    await expect(sidebar).toBeVisible();
  });

  test('should collapse sidebar to icon-only mode', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    
    // Toggle to collapse
    await page.keyboard.press('Control+b');
    await page.waitForTimeout(500);
    
    // Sidebar should be narrower (check for width class)
    const sidebar = page.locator('aside');
    const sidebarClass = await sidebar.getAttribute('class');
    expect(sidebarClass).toMatch(/w-20|w-16/);
  });

  test('should expand sidebar from collapsed state', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    
    // Collapse first
    await page.keyboard.press('Control+b');
    await page.waitForTimeout(500);
    
    // Expand again
    await page.keyboard.press('Control+b');
    await page.waitForTimeout(500);
    
    // Sidebar should show full width
    const sidebar = page.locator('aside');
    const sidebarClass = await sidebar.getAttribute('class');
    expect(sidebarClass).toMatch(/w-64|w-72/);
  });

  test('should show mobile menu button on small screens', async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 375, height: 667 }
    });
    const page = await context.newPage();
    
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    
    // Mobile menu button should be visible
    const mobileMenuButton = page.getByRole('button').first();
    await expect(mobileMenuButton).toBeVisible();
    
    await page.close();
    await context.close();
  });

  test('should open mobile menu', async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: 375, height: 667 }
    });
    const page = await context.newPage();
    
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    
    // Click mobile menu button
    const mobileMenuButton = page.getByRole('button').first();
    await mobileMenuButton.click();
    
    // Sidebar should slide in
    const sidebar = page.locator('aside');
    await expect(sidebar).toBeVisible();

    await page.close();
    await context.close();
  });

  test('should display version in sidebar', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    
    await expect(page.getByText(/showcase v/i)).toBeVisible();
  });
});
