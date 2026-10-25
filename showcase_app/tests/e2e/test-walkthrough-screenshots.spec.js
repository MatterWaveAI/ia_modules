// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Walkthrough E2E test — visits every page in the showcase app and takes
 * full-page screenshots. Run with:
 *
 *   npx playwright test test-walkthrough-screenshots --project=chromium
 *
 * Individual sections:
 *   npx playwright test test-walkthrough-screenshots -g "All pages"
 *   npx playwright test test-walkthrough-screenshots -g "Dark mode"
 *   npx playwright test test-walkthrough-screenshots -g "Sidebar"
 *   npx playwright test test-walkthrough-screenshots -g "Editor"
 *   npx playwright test test-walkthrough-screenshots -g "Pipeline"
 *   npx playwright test test-walkthrough-screenshots -g "Mobile"
 *
 * Screenshots saved to: showcase_app/screenshots/
 */

const path = require('path');
const SCREENSHOT_DIR = path.join(__dirname, '..', '..', 'screenshots');

/** Helper — navigate, wait, and screenshot */
async function snap(page, urlPath, name, { waitFor, timeout = 10_000 } = {}) {
  await page.goto(urlPath);
  await page.waitForLoadState('networkidle');
  if (waitFor) {
    await expect(waitFor(page)).toBeVisible({ timeout });
  }
  await page.screenshot({ path: `${SCREENSHOT_DIR}/${name}.png`, fullPage: true });
}

/** All navigable pages. */
const PAGES = [
  { path: '/',              name: 'home',             heading: /ia modules showcase/i },
  { path: '/pipelines',     name: 'pipelines',        heading: /pipelines/i },
  { path: '/editor',        name: 'editor',           heading: /pipeline editor/i },
  { path: '/executions',    name: 'executions',       heading: /executions/i },
  { path: '/patterns',      name: 'patterns',         heading: /patterns/i },
  { path: '/web-scraping',  name: 'web-scraping',     heading: /web.?scraping/i },
  { path: '/multi-agent',   name: 'multi-agent',      heading: /multi.?agent/i },
  { path: '/collaboration', name: 'collaboration',    heading: /collaboration/i },
  { path: '/guardrails',    name: 'guardrails',       heading: /guardrails/i },
  { path: '/metrics',       name: 'metrics',          heading: /metrics/i },
  { path: '/agents',        name: 'agents',           heading: /agent/i },
  { path: '/plugins',       name: 'plugins',          heading: /plugin/i },
  { path: '/llm',           name: 'llm-usage',        heading: /llm/i },
];

// ─────────────────────────────────────────────────────────────────────────────
// 1. All pages — light mode walkthrough
// ─────────────────────────────────────────────────────────────────────────────

test.describe('All pages @walkthrough', () => {
  test('walk through every page in light mode', async ({ page }) => {
    for (const pg of PAGES) {
      await test.step(`${pg.name}`, async () => {
        await page.goto(pg.path);
        await page.waitForLoadState('networkidle');
        const heading = page.locator('main h1, main h2, [role="heading"]').first();
        await expect(heading).toBeVisible({ timeout: 10_000 });
        await page.screenshot({ path: `${SCREENSHOT_DIR}/${pg.name}.png`, fullPage: true });
      });
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 2. Dark mode — same pages in dark theme
// ─────────────────────────────────────────────────────────────────────────────

test.describe('Dark mode @walkthrough', () => {
  test('walk through every page in dark mode', async ({ page }) => {
    // Enable dark mode via localStorage before any navigation
    await page.addInitScript(() => { localStorage.setItem('theme', 'dark'); });

    for (const pg of PAGES) {
      await test.step(`${pg.name} (dark)`, async () => {
        await page.goto(pg.path);
        await page.waitForLoadState('networkidle');
        const heading = page.locator('main h1, main h2, [role="heading"]').first();
        await expect(heading).toBeVisible({ timeout: 10_000 });
        await page.screenshot({ path: `${SCREENSHOT_DIR}/${pg.name}-dark.png`, fullPage: true });
      });
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 3. Sidebar states
// ─────────────────────────────────────────────────────────────────────────────

test.describe('Sidebar @walkthrough', () => {
  test('sidebar expanded vs collapsed', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Expanded (default)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/sidebar-expanded.png`, fullPage: true });

    // Collapse with Ctrl+B
    await page.keyboard.press('Control+b');
    await page.waitForTimeout(400);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/sidebar-collapsed.png`, fullPage: true });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 4. Editor interactions
// ─────────────────────────────────────────────────────────────────────────────

test.describe('Editor @walkthrough', () => {
  test('editor views and node palette', async ({ page }) => {
    await page.goto('/editor');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // Visual mode (default)
    await page.screenshot({ path: `${SCREENSHOT_DIR}/editor-visual.png`, fullPage: true });

    // Code mode
    const codeBtn = page.getByRole('button', { name: /code/i }).first();
    if (await codeBtn.isVisible()) {
      await codeBtn.click();
      await page.waitForTimeout(300);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/editor-code.png`, fullPage: true });
    }

    // Split mode
    const splitBtn = page.getByRole('button', { name: /split/i }).first();
    if (await splitBtn.isVisible()) {
      await splitBtn.click();
      await page.waitForTimeout(300);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/editor-split.png`, fullPage: true });
    }

    // Add some nodes
    await page.getByRole('button', { name: /visual/i }).first().click();
    await page.waitForTimeout(300);
    const taskNode = page.getByText('Task Step').first();
    if (await taskNode.isVisible()) {
      await taskNode.click();
      await page.waitForTimeout(200);
      const transformNode = page.getByText('Transform').first();
      if (await transformNode.isVisible()) {
        await transformNode.click();
        await page.waitForTimeout(200);
      }
      await page.screenshot({ path: `${SCREENSHOT_DIR}/editor-with-nodes.png`, fullPage: true });
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 5. Pipeline execute dialog
// ─────────────────────────────────────────────────────────────────────────────

test.describe('Pipeline execute dialog @walkthrough', () => {
  test('open execute dialog on pipelines page', async ({ page }) => {
    await page.goto('/pipelines');
    await page.waitForLoadState('networkidle');

    const executeBtn = page.getByRole('button', { name: /execute/i }).first();
    if (await executeBtn.isVisible()) {
      await executeBtn.click();
      await page.waitForTimeout(300);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/pipeline-execute-dialog.png`, fullPage: true });

      // Close it
      const cancelBtn = page.getByRole('button', { name: /cancel/i });
      if (await cancelBtn.isVisible()) await cancelBtn.click();
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 6. Execution detail (if any executions exist)
// ─────────────────────────────────────────────────────────────────────────────

test.describe('Execution detail @walkthrough', () => {
  test('capture execution detail page', async ({ page, request }) => {
    // Check for existing executions via API
    const resp = await request.get('http://localhost:7331/api/execute');
    if (!resp.ok()) { test.skip(true, 'API not available'); return; }
    const executions = await resp.json();
    if (!Array.isArray(executions) || executions.length === 0) {
      test.skip(true, 'No executions available');
      return;
    }

    const jobId = executions[0].job_id;
    await page.goto(`/executions/${jobId}`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/loading execution/i)).not.toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: `${SCREENSHOT_DIR}/execution-detail.png`, fullPage: true });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 7. Mobile viewport
// ─────────────────────────────────────────────────────────────────────────────

test.describe('Mobile @walkthrough', () => {
  test('mobile viewport walkthrough', async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 375, height: 812 } });
    const page = await context.newPage();

    const mobilePages = ['/', '/pipelines', '/patterns', '/metrics', '/agents'];
    for (const p of mobilePages) {
      await test.step(`mobile ${p}`, async () => {
        await page.goto(`http://localhost:5174${p}`);
        await page.waitForLoadState('networkidle');
        const name = p === '/' ? 'home' : p.slice(1);
        await page.screenshot({ path: `${SCREENSHOT_DIR}/mobile-${name}.png`, fullPage: true });
      });
    }

    // Open mobile menu
    const menuBtn = page.getByRole('button').first();
    if (await menuBtn.isVisible()) {
      await menuBtn.click();
      await page.waitForTimeout(300);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/mobile-menu-open.png`, fullPage: true });
    }

    await page.close();
    await context.close();
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 8. Individual page tests (for running one at a time)
// ─────────────────────────────────────────────────────────────────────────────

for (const pg of PAGES) {
  test(`screenshot: ${pg.name} @screenshot`, async ({ page }) => {
    await page.goto(pg.path);
    await page.waitForLoadState('networkidle');
    const heading = page.locator('main h1, main h2, [role="heading"]').first();
    await expect(heading).toBeVisible({ timeout: 10_000 });
    await page.screenshot({ path: `${SCREENSHOT_DIR}/${pg.name}.png`, fullPage: true });
  });
}
