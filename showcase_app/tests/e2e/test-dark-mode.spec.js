// @ts-check
const { test, expect } = require('@playwright/test');

test.describe('Dark Mode & Theme', () => {
  test('should default to light theme', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    
    // HTML should not have dark class initially
    const htmlElement = page.locator('html');
    const hasDarkClass = await htmlElement.evaluate(el => el.classList.contains('dark'));
    expect(hasDarkClass).toBe(false);
  });

  test('should toggle dark mode with button', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    
    // Find and click theme toggle button
    const themeToggle = page.getByRole('button', { name: /toggle dark mode/i });
    await themeToggle.click();
    
    // HTML should now have dark class
    const htmlElement = page.locator('html');
    const hasDarkClass = await htmlElement.evaluate(el => el.classList.contains('dark'));
    expect(hasDarkClass).toBe(true);
  });

  test('should persist theme to localStorage', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    
    // Toggle to dark mode
    const themeToggle = page.getByRole('button', { name: /toggle dark mode/i });
    await themeToggle.click();
    
    // Check localStorage
    const savedTheme = await page.evaluate(() => localStorage.getItem('theme'));
    expect(savedTheme).toBe('dark');
  });

  test('should load saved theme from localStorage', async ({ page }) => {
    // Set theme to dark before loading page
    await page.addInitScript(() => {
      localStorage.setItem('theme', 'dark');
    });
    
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    
    // Should have dark class
    const htmlElement = page.locator('html');
    const hasDarkClass = await htmlElement.evaluate(el => el.classList.contains('dark'));
    expect(hasDarkClass).toBe(true);
  });

  test('should apply dark theme styles', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');

    // Toggle to dark mode
    const themeToggle = page.getByRole('button', { name: /toggle dark mode/i });
    await themeToggle.click();

    // Check that the dark class exists on the html element
    await expect(page.locator('html')).toHaveClass(/dark/);
  });

  test('should toggle theme with keyboard shortcut cmd+d', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    
    // Use keyboard shortcut (Meta+D for Mac, or we can simulate with Ctrl+D)
    await page.keyboard.press('Meta+d');
    
    // Wait a moment for the shortcut to trigger
    await page.waitForTimeout(500);
    
    // HTML should now have dark class
    const htmlElement = page.locator('html');
    const hasDarkClass = await htmlElement.evaluate(el => el.classList.contains('dark'));
    expect(hasDarkClass).toBe(true);
  });

  test('should maintain theme across page navigations', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    
    // Toggle to dark mode
    const themeToggle = page.getByRole('button', { name: /toggle dark mode/i });
    await themeToggle.click();
    
    // Navigate to different pages
    await page.goto('http://localhost:5174/pipelines');
    await page.waitForLoadState('networkidle');
    
    // Theme should still be dark
    const htmlElement = page.locator('html');
    let hasDarkClass = await htmlElement.evaluate(el => el.classList.contains('dark'));
    expect(hasDarkClass).toBe(true);
    
    await page.goto('http://localhost:5174/metrics');
    await page.waitForLoadState('networkidle');
    
    hasDarkClass = await htmlElement.evaluate(el => el.classList.contains('dark'));
    expect(hasDarkClass).toBe(true);
  });

  test('should toggle between light and dark multiple times', async ({ page }) => {
    await page.goto('http://localhost:5174/');
    await page.waitForLoadState('networkidle');
    
    const themeToggle = page.getByRole('button', { name: /toggle dark mode/i });
    const htmlElement = page.locator('html');
    
    // Toggle to dark
    await themeToggle.click();
    expect(await htmlElement.evaluate(el => el.classList.contains('dark'))).toBe(true);
    
    // Toggle back to light
    await themeToggle.click();
    expect(await htmlElement.evaluate(el => el.classList.contains('dark'))).toBe(false);
    
    // Toggle to dark again
    await themeToggle.click();
    expect(await htmlElement.evaluate(el => el.classList.contains('dark'))).toBe(true);
  });
});
