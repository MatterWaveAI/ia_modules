// @ts-check
const { test, expect } = require('@playwright/test');
const path = require('path');

/**
 * Demo flow — walks through the showcase app like a live demo.
 * Records video + takes screenshots at each key moment.
 *
 * Run:
 *   npx playwright test test-demo-flow --project=chromium
 *
 * Video:       test-results/ (auto by Playwright)
 * Screenshots: showcase_app/screenshots/demo/
 */

const DEMO_DIR = path.join(__dirname, '..', '..', 'screenshots', 'demo');
const API_BASE = 'http://localhost:7331';

test.use({
  trace: 'on',
  colorScheme: 'dark',
});

test.setTimeout(1_200_000);

// Auto-incrementing counter so filenames sort alphabetically in capture order.
let snapCounter = 0;
async function snap(page, name) {
  snapCounter += 1;
  const seq = String(snapCounter).padStart(3, '0');
  await page.screenshot({ path: `${DEMO_DIR}/${seq}-${name}.png`, fullPage: true });
}

async function pause(page, ms = 500) {
  await page.waitForTimeout(ms);
}

function escapeRegExp(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Pipeline event bus — opens a WebSocket inside the page context and forwards
 * every frame to Node via an exposed binding. The test awaits events from the
 * returned `waitFor(predicate)` helper.
 *
 * Set up ONCE per page, before navigating to the execution detail route.
 *
 * @param {import('@playwright/test').Page} page
 */
async function attachPipelineEventBus(page) {
  /** @type {any[]} */
  const queue = [];
  /** @type {((evt: any) => void)[]} */
  const waiters = [];

  await page.exposeBinding('__onPipelineEvent', (/** @type {any} */ _src, /** @type {any} */ event) => {
    if (waiters.length > 0) {
      const resolve = waiters.shift();
      if (resolve) resolve(event);
    } else {
      queue.push(event);
    }
  });

  // Injected into every frame — opens a WS to the execution stream for whatever
  // job_id is in the current URL and forwards every frame. Re-runs on each
  // navigation so it picks up new job ids automatically.
  await page.addInitScript(() => {
    /** @type {WebSocket | null} */
    let ws = null;
    /** @type {string | null} */
    let currentJobId = null;

    const connect = () => {
      const m = window.location.pathname.match(/\/executions\/([a-f0-9-]+)/);
      const jobId = m ? m[1] : null;
      if (jobId === currentJobId) return;
      if (ws) { try { ws.close(); } catch { /* ignore */ } ws = null; }
      currentJobId = jobId;
      if (!jobId) return;

      const wsBase = `ws://${window.location.host}`;
      ws = new WebSocket(`${wsBase}/ws/execution/${jobId}`);
      ws.onmessage = (msg) => {
        try {
          const evt = JSON.parse(msg.data);
          // @ts-ignore — exposed by page.exposeBinding
          window.__onPipelineEvent({ ...evt, __job_id: jobId });
        } catch { /* ignore malformed */ }
      };
    };

    // Re-check on every history change (SPA navigation).
    const origPush = history.pushState;
    const origReplace = history.replaceState;
    history.pushState = function (...args) { origPush.apply(this, args); setTimeout(connect, 0); };
    history.replaceState = function (...args) { origReplace.apply(this, args); setTimeout(connect, 0); };
    window.addEventListener('popstate', () => setTimeout(connect, 0));
    // Initial attempt (won't match on first load — that's fine).
    setTimeout(connect, 0);
  });

  /**
   * @param {(evt: any) => boolean} predicate
   * @param {{ timeout?: number }} [opts]
   * @returns {Promise<any>}
   */
  const waitFor = (predicate, { timeout = 300_000 } = {}) => {
    const deadline = Date.now() + timeout;
    return new Promise((resolve, reject) => {
      while (queue.length > 0) {
        const evt = queue.shift();
        if (predicate(evt)) return resolve(evt);
      }
      if (Date.now() >= deadline) return reject(new Error('waitFor: timeout'));
      /** @type {(evt: any) => void} */
      const waiter = (evt) => {
        if (predicate(evt)) return resolve(evt);
        if (Date.now() >= deadline) return reject(new Error('waitFor: timeout'));
        waiters.push(waiter);
      };
      waiters.push(waiter);
    });
  };

  return { waitFor };
}

/**
 * Collaboration event bus — opens a single WS to `/ws/collaboration` and
 * forwards every `collab_step` / `collab_complete` frame into Node via an
 * exposed binding. Independent of navigation (single global stream).
 *
 * @param {import('@playwright/test').Page} page
 */
async function attachCollaborationEventBus(page) {
  /** @type {any[]} */
  const queue = [];
  /** @type {((evt: any) => void)[]} */
  const waiters = [];

  await page.exposeBinding('__onCollabEvent', (/** @type {any} */ _src, /** @type {any} */ event) => {
    if (waiters.length > 0) {
      const resolve = waiters.shift();
      if (resolve) resolve(event);
    } else {
      queue.push(event);
    }
  });

  // Injected into every frame — opens a single WS for the collaboration
  // stream and forwards every frame. The page itself also opens this socket
  // for its own live UI; that's fine, the backend broadcasts to all listeners.
  await page.addInitScript(() => {
    /** @type {WebSocket | null} */
    let ws = null;

    const connect = () => {
      if (ws) return;
      const wsBase = `ws://${window.location.host}`;
      ws = new WebSocket(`${wsBase}/ws/collaboration`);
      ws.onmessage = (msg) => {
        try {
          const evt = JSON.parse(msg.data);
          // @ts-ignore — exposed by page.exposeBinding
          window.__onCollabEvent(evt);
        } catch { /* ignore malformed */ }
      };
      ws.onclose = () => { ws = null; setTimeout(connect, 500); };
    };

    setTimeout(connect, 0);
  });

  /**
   * @param {(evt: any) => boolean} predicate
   * @param {{ timeout?: number }} [opts]
   * @returns {Promise<any>}
   */
  const waitFor = (predicate, { timeout = 300_000 } = {}) => {
    const deadline = Date.now() + timeout;
    return new Promise((resolve, reject) => {
      while (queue.length > 0) {
        const evt = queue.shift();
        if (predicate(evt)) return resolve(evt);
      }
      if (Date.now() >= deadline) return reject(new Error('waitFor: timeout'));
      /** @type {(evt: any) => void} */
      const waiter = (evt) => {
        if (predicate(evt)) return resolve(evt);
        if (Date.now() >= deadline) return reject(new Error('waitFor: timeout'));
        waiters.push(waiter);
      };
      waiters.push(waiter);
    });
  };

  return { waitFor };
}

/**
 * Patterns event bus — opens a single WS to `/ws/patterns` and forwards every
 * `pattern_event` frame into Node via an exposed binding. Independent of
 * navigation (single global stream).
 *
 * @param {import('@playwright/test').Page} page
 */
async function attachPatternsEventBus(page) {
  /** @type {any[]} */
  const queue = [];
  /** @type {((evt: any) => void)[]} */
  const waiters = [];

  await page.exposeBinding('__onPatternEvent', (/** @type {any} */ _src, /** @type {any} */ event) => {
    if (waiters.length > 0) {
      const resolve = waiters.shift();
      if (resolve) resolve(event);
    } else {
      queue.push(event);
    }
  });

  await page.addInitScript(() => {
    /** @type {WebSocket | null} */
    let ws = null;

    const connect = () => {
      if (ws) return;
      const wsBase = `ws://${window.location.host}`;
      ws = new WebSocket(`${wsBase}/ws/patterns`);
      ws.onmessage = (msg) => {
        try {
          const evt = JSON.parse(msg.data);
          // @ts-ignore — exposed by page.exposeBinding
          window.__onPatternEvent(evt);
        } catch { /* ignore malformed */ }
      };
      ws.onclose = () => { ws = null; setTimeout(connect, 500); };
    };

    setTimeout(connect, 0);
  });

  /**
   * @param {(evt: any) => boolean} predicate
   * @param {{ timeout?: number }} [opts]
   * @returns {Promise<any>}
   */
  const waitFor = (predicate, { timeout = 300_000 } = {}) => {
    const deadline = Date.now() + timeout;
    return new Promise((resolve, reject) => {
      while (queue.length > 0) {
        const evt = queue.shift();
        if (predicate(evt)) return resolve(evt);
      }
      if (Date.now() >= deadline) return reject(new Error('waitFor: timeout'));
      /** @type {(evt: any) => void} */
      const waiter = (evt) => {
        if (predicate(evt)) return resolve(evt);
        if (Date.now() >= deadline) return reject(new Error('waitFor: timeout'));
        waiters.push(waiter);
      };
      waiters.push(waiter);
    });
  };

  return { waitFor };
}

// Navigate via sidebar, with direct-URL fallback
async function sidebarNav(page, linkText, urlPath) {
  const link = page.locator('aside a').filter({ hasText: linkText }).first();
  if (await link.isVisible().catch(() => false)) {
    await link.click();
  } else {
    await page.goto(urlPath);
  }
  await page.waitForLoadState('networkidle');
}

/**
 * Execute a pipeline by name and walk through the result.
 *
 * @param {import('@playwright/test').Page} page
 * @param {import('@playwright/test').APIRequestContext} request
 * @param {{ waitFor: (pred: (evt: any) => boolean, opts?: { timeout?: number }) => Promise<any> }} bus
 * @param {{ pipelineName?: RegExp | null, pipelineIndex?: number, stepPrefix: string, openInEditor?: boolean }} opts
 */
async function executePipelineFlow(page, request, bus, {
  pipelineName,
  pipelineIndex = 0,
  stepPrefix,
  openInEditor,
}) {
  const resp = await request.get(`${API_BASE}/api/pipelines`);
  expect(resp.ok()).toBeTruthy();
  const pipelines = await resp.json();
  expect(pipelines.length).toBeGreaterThan(0);

  let pipeline;
  if (pipelineName) {
    pipeline = pipelines.find(p => pipelineName.test(p.name));
  }
  if (!pipeline) {
    pipeline = pipelines[pipelineIndex] || pipelines[0];
  }

  const pipelineId = pipeline.id;
  const label = pipeline.name;

  // Pipelines list
  // The default view is a table, so match the pipeline name anywhere on the row
  // (it's rendered as a <span> inside a <tr>, no longer an <h3>).
  const pipelineRowLocator = page.getByRole('row', { name: new RegExp(escapeRegExp(label)) });
  await test.step(`${label}: pipelines list`, async () => {
    await page.goto('/pipelines');
    await expect(page.locator('main h1').first()).toBeVisible({ timeout: 10_000 });
    // Wait for the row containing this pipeline to render
    await expect(pipelineRowLocator.first()).toBeVisible({ timeout: 10_000 });
    await snap(page, `${stepPrefix}-pipelines`);
    await pause(page, 2000);
  });

  // Editor (optional)
  if (openInEditor) {
    await test.step(`${label}: editor`, async () => {
      const row = pipelineRowLocator.first();
      if (await row.isVisible().catch(() => false)) {
        const editBtn = row.getByRole('button', { name: /edit/i });
        await editBtn.click();
      } else {
        await page.goto(`/editor/${pipelineId}`);
      }
      await page.waitForURL(`**/editor/${pipelineId}`);
      await page.waitForTimeout(800);
      await snap(page, `${stepPrefix}-editor`);
      await pause(page, 2000);

      // const codeBtn = page.getByRole('button', { name: /code/i }).first();
      // if (await codeBtn.isVisible()) {
      //   await codeBtn.click();
      //   await page.waitForTimeout(400);
      //   await snap(page, `${stepPrefix}-editor-code`);
      //   await pause(page, 2000);
      // }
      // const visualBtn = page.getByRole('button', { name: /visual/i }).first();
      // if (await visualBtn.isVisible()) {
      //   await visualBtn.click();
      //   await page.waitForTimeout(300);
      // }
    });
    await page.goto('/pipelines');
    await expect(page.locator('main h1').first()).toBeVisible({ timeout: 10_000 });
    await expect(pipelineRowLocator.first()).toBeVisible({ timeout: 10_000 });
  }

  // Execute
  /** @type {string | null} */
  let jobId = null;
  await test.step(`${label}: execute`, async () => {
    // Find the row by name, then find the Execute button inside it.
    // If that fails, fall back to the first Execute button on the page.
    const row = pipelineRowLocator.first();
    let executeBtn = null;
    if (await row.isVisible().catch(() => false)) {
      const scoped = row.getByRole('button', { name: /execute/i });
      if (await scoped.isVisible().catch(() => false)) {
        executeBtn = scoped;
      }
    }
    if (!executeBtn) {
      executeBtn = page.getByRole('button', { name: /execute/i }).first();
    }
    await expect(executeBtn).toBeVisible({ timeout: 10_000 });
    await executeBtn.click();

    const dialogTitle = page.locator('h2').filter({ hasText: /execute/i });
    await expect(dialogTitle).toBeVisible({ timeout: 5_000 });
    await snap(page, `${stepPrefix}-execute-dialog`);
    await pause(page, 2000);

    const confirmBtn = page.getByRole('button', { name: /execute pipeline/i });
    await expect(confirmBtn).toBeVisible();
    await confirmBtn.click();

    await page.waitForURL('**/executions/**', { timeout: 15_000 });
    const match = page.url().match(/\/executions\/([a-f0-9-]+)/);
    expect(match).toBeTruthy();
    jobId = match && match[1];
    await snap(page, `${stepPrefix}-execution-started`);
    await pause(page, 2000);
  });

  // Event-driven capture — listen on the pipeline event bus for step_started /
  // step_completed / execution_completed. On each event, wait a beat for the UI
  // to refetch, then scroll through each section anchor and take a full-viewport
  // screenshot. No polling, no reloads.
  await test.step(`${label}: capture per-step progress`, async () => {
    await expect(page.getByText(/loading execution/i)).not.toBeVisible({ timeout: 15_000 });

    // Sections are tagged with stable ids in ExecutionDetailPage.jsx. Input
    // and output JSON cards are intentionally omitted — they're collapsed by
    // default and only contain raw JSON dumps not useful for the demo.
    const SECTION_SLUGS = [
      'status',
      'timeline',
      'pipeline-flow',
      'trace',
      'step-details',
      'checkpoints',
      'conversation',
      'replay',
      'decisions',
    ];

    /** @param {string} tag */
    const captureAllSections = async (tag) => {
      for (const slug of SECTION_SLUGS) {
        const scrolled = await page.evaluate((/** @type {string} */ id) => {
          const el = document.getElementById(id);
          if (!el) return false;
          const rect = el.getBoundingClientRect();
          if (rect.height < 10) return false;
          el.scrollIntoView({ block: 'start', behavior: 'instant' });
          return true;
        }, `section-${slug}`);
        if (!scrolled) continue;
        await page.waitForTimeout(150);
        snapCounter += 1;
        const seq = String(snapCounter).padStart(3, '0');
        await page.screenshot({
          path: `${DEMO_DIR}/${seq}-${stepPrefix}-${tag}-${slug}.png`,
        }).catch((e) => {
          console.warn(`[capture] ${tag}-${slug} failed: ${e.message}`);
        });
      }
    };

    let done = false;
    /** @type {Set<string>} */
    const seenStepIds = new Set();

    // HTTP poll fallback — terminal WS frames can be dropped if the frontend
    // hasn't connected yet when the backend broadcasts. Race the WS wait
    // against a GET so we never sit forever on a missed final event.
    const pollForTerminal = async () => {
      while (!done) {
        await new Promise((r) => setTimeout(r, 1500));
        if (done) return null;
        try {
          const resp = await request.get(`${API_BASE}/api/execute/${jobId}`);
          if (!resp.ok()) continue;
          const body = await resp.json();
          if (body.status === 'completed' || body.status === 'failed') {
            return { type: `execution_${body.status}`, __job_id: jobId, __http: true };
          }
        } catch { /* keep polling */ }
      }
      return null;
    };

    while (!done) {
      const wsWait = bus.waitFor(
        (e) => {
          if (!e) return false;
          // Per-step end updates from ExecutionTracker._broadcast_step_update.
          // Initial page load captures the "first start"; we only snap on step completion.
          if (e.type === 'step_update') {
            const data = e.data || {};
            if (data.execution_id !== jobId) return false;
            if (data.status !== 'completed' && data.status !== 'failed') return false;
            const sid = data.step_id;
            if (!sid || seenStepIds.has(sid)) return false;
            return true;
          }
          // Terminal execution-level messages from the showcase app pipeline_service.
          if (
            e.type === 'execution_completed' ||
            e.type === 'execution_failed' ||
            e.type === 'execution_paused'
          ) {
            return e.__job_id === jobId;
          }
          return false;
        },
        { timeout: 60_000 }
      ).catch(() => null);

      const evt = await Promise.race([wsWait, pollForTerminal()]);
      if (!evt) {
        console.warn(`[bus] no event in 60s — moving on`);
        break;
      }

      // Wait for the UI to refetch and render the new state before snapping.
      await page.waitForTimeout(1200);

      let tag;
      if (evt.type === 'step_update') {
        const data = evt.data || {};
        seenStepIds.add(data.step_id);
        tag = `step-${String(seenStepIds.size).padStart(2, '0')}-end`;
        console.log(`[capture] step_update ${data.status} (${data.step_name || data.step_id || ''}) → ${tag}`);
      } else {
        tag = 'final';
        done = true;
        const source = evt.__http ? ' (via HTTP poll)' : '';
        console.log(`[capture] ${evt.type}${source} → ${tag}`);
      }
      await captureAllSections(tag);
    }

    await pause(page, 1500);
  });

  return jobId;
}

// ---------------------------------------------------------------------------

test.describe('Pipeline Demo Flow @demo', () => {

  test.skip('full demo walkthrough', async ({ page, request }) => {
    // Skipped: LLM calls exceed 20-minute timeout
    await page.addInitScript(() => { localStorage.setItem('theme', 'dark'); });

    // Attach the pipeline event bus once. Subsequent executions reuse it —
    // the injected script re-connects to /ws/execution/{job_id} on each SPA
    // navigation.
    const bus = await attachPipelineEventBus(page);

    // Attach the collaboration event bus once. Independent of navigation —
    // opens a single WS to /ws/collaboration and forwards every collab_step.
    const collabBus = await attachCollaborationEventBus(page);

    // Attach the patterns event bus once. Independent of navigation —
    // opens a single WS to /ws/patterns and forwards every pattern_event.
    const patternsBus = await attachPatternsEventBus(page);

    // -- 01 Home ---------------------------------------------------------------
    await test.step('Home page', async () => {
      await page.goto('/');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('main h1, main h2').first()).toBeVisible({ timeout: 10_000 });
      await snap(page, '01-home');
      await pause(page);
    });

    // -- 10 Pipeline loop 1: first pipeline with editor ------------------------
    await executePipelineFlow(page, request, bus, {
      pipelineName: null,
      stepPrefix: '10',
      openInEditor: true,
    });

    // -- 20 Pipeline loop 2: decision/conditional ------------------------------
    await executePipelineFlow(page, request, bus, {
      pipelineName: /conditional|decision|branch/i,
      pipelineIndex: 1,
      stepPrefix: '20',
      openInEditor: true,
    });

    // -- 30 Executions list ----------------------------------------------------
    await test.step('Executions list', async () => {
      await sidebarNav(page, 'Executions', '/executions');
      await page.waitForTimeout(400);
      await snap(page, '30-executions-list');
      await pause(page, 2000);

      // Expand first execution row
      const expandBtn = page.locator('tr').first().locator('svg').first();
      if (await expandBtn.isVisible().catch(() => false)) {
        await expandBtn.click();
        await page.waitForTimeout(400);
        await snap(page, '30-execution-expanded');
      }
      await pause(page, 2000);
    });

    // -- 31 Patterns: run each pattern -----------------------------------------
    // Pages now use /patterns/:id detail view — navigate directly, no scrolling.
    const PATTERNS = [
      { slug: 'reflection',    name: 'Reflection',    backend: 'reflection' },
      { slug: 'planning',      name: 'Planning',      backend: 'planning' },
      { slug: 'tool-use',      name: 'Tool Use',      backend: 'tool_use' },
      { slug: 'agentic-rag',   name: 'Agentic RAG',   backend: 'agentic_rag' },
      { slug: 'metacognition', name: 'Metacognition', backend: 'metacognition' },
    ];

    await test.step('Patterns page', async () => {
      await sidebarNav(page, 'Patterns', '/patterns');
      await page.waitForTimeout(400);
      await snap(page, '31-patterns');
      await pause(page, 2000);
    });

    for (const p of PATTERNS) {
      await test.step(`Patterns: ${p.name}`, async () => {
        await page.goto(`/patterns/${p.slug}`);
        const runBtn = page.getByRole('button', { name: /run pattern/i }).first();
        await expect(runBtn).toBeVisible({ timeout: 10_000 });
        await page.waitForTimeout(600);
        await pause(page, 2000);

        await runBtn.click();

        // Event-driven per-event capture: on each matching pattern_event, wait
        // ~1s for React to render the new row, then take a full-page snap.
        // Terminates on the `completed` event.
        let eventIdx = 0;
        let patternDone = false;
        while (!patternDone) {
          const evt = await patternsBus.waitFor(
            (e) => {
              if (!e) return false;
              if (e.type !== 'pattern_event') return false;
              return e.pattern === p.backend;
            },
            { timeout: 120_000 }
          ).catch((err) => {
            console.warn(`[patterns] waitFor failed: ${String(err)}`);
            return null;
          });
          if (!evt) break;

          eventIdx += 1;
          await page.waitForTimeout(1000);

          const tag = `event-${String(eventIdx).padStart(2, '0')}-${evt.event || 'unknown'}`;
          console.log(`[patterns] ${p.slug} ${evt.event || ''} → ${tag}`);
          await snap(page, `31-patterns-${p.slug}-${tag}`);

          if (evt.event === 'completed') {
            patternDone = true;
          }
        }

        await pause(page, 1500);
      });
    }

    // -- 32 Collaboration: run each pattern ------------------------------------
    const COLLAB_PATTERNS = [
      { slug: 'consensus',    name: 'Consensus' },
      { slug: 'debate',       name: 'Debate' },
      { slug: 'hierarchical', name: 'Hierarchical' },
      { slug: 'peer-to-peer', name: 'Peer-to-Peer' },
    ];

    await test.step('Collaboration page', async () => {
      await sidebarNav(page, 'Collaboration', '/collaboration');
      await page.waitForTimeout(400);
      await snap(page, '32-collaboration');
      await pause(page, 2000);
    });

    for (const c of COLLAB_PATTERNS) {
      await test.step(`Collaboration: ${c.name}`, async () => {
        await page.goto(`/collaboration/${c.slug}`);
        const runBtn = page.getByRole('button', { name: /^run$/i }).first();
        await expect(runBtn).toBeVisible({ timeout: 10_000 });
        await page.waitForTimeout(1500);
        await snap(page, `32-collaboration-${c.slug}-selected`);
        await pause(page, 2000);

        await runBtn.click();

        // Event-driven per-step capture: on each collab_step for THIS run,
        // wait ~1s for React to render, then take a full-page snap. The last
        // live step auto-expands in the UI. Terminates on collab_complete.
        /** @type {string | null} */
        let activeRunId = null;
        let stepIdx = 0;
        let collabDone = false;
        while (!collabDone) {
          const evt = await collabBus.waitFor(
            (e) => {
              if (!e) return false;
              if (e.type === 'collab_step') {
                if (!e.run_id) return false;
                if (activeRunId && e.run_id !== activeRunId) return false;
                return true;
              }
              if (e.type === 'collab_complete') {
                if (!activeRunId) return false;
                return e.run_id === activeRunId;
              }
              return false;
            },
            { timeout: 600_000 }
          ).catch((err) => {
            console.warn(`[collab] waitFor failed: ${String(err)}`);
            return null;
          });
          if (!evt) break;

          if (evt.type === 'collab_complete') {
            collabDone = true;
            break;
          }

          // First matching step defines the active run id.
          if (!activeRunId) activeRunId = evt.run_id;

          stepIdx += 1;
          await page.waitForTimeout(1000);

          const tag = `step-${String(stepIdx).padStart(2, '0')}`;
          console.log(`[collab] ${c.slug} ${evt.phase || ''} → ${tag}`);
          await snap(page, `32-collaboration-${c.slug}-${tag}`);
        }

        await page.waitForTimeout(800);

        // Scroll to top of results card for the completed screenshot
        const resultsHeader = page.getByRole('heading', { name: /^results$/i }).first();
        if (await resultsHeader.isVisible().catch(() => false)) {
          await resultsHeader.scrollIntoViewIfNeeded();
          await page.waitForTimeout(400);
        }
        await snap(page, `32-collaboration-${c.slug}-result`);

        // Expand all step accordions in the live results section
        const accordionBtns = page.locator('button.w-full.flex.items-center.justify-between');
        const btnCount = await accordionBtns.count();
        for (let i = 0; i < btnCount; i++) {
          const btn = accordionBtns.nth(i);
          if (await btn.isVisible().catch(() => false)) {
            await btn.click();
          }
        }
        await page.waitForTimeout(300);
        await snap(page, `32-collaboration-${c.slug}-details`);

        // Scroll to bottom of page to show full expanded timeline
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await page.waitForTimeout(400);
        await snap(page, `32-collaboration-${c.slug}-viz`);
        await pause(page, 2000);
      });
    }

    // -- 33 Metrics (after all the executions) ---------------------------------
    await test.step('Metrics', async () => {
      await sidebarNav(page, 'Metrics', '/metrics');
      await page.waitForTimeout(800);
      await snap(page, '33-metrics');

      await page.evaluate(() => window.scrollBy(0, 400));
      await page.waitForTimeout(300);
      await snap(page, '33-metrics-scrolled');
      await page.evaluate(() => window.scrollTo(0, 0));
      await pause(page);
    });

    // -- 34 Agents -------------------------------------------------------------
    await test.step('Agents', async () => {
      await sidebarNav(page, /^Agents$/i, '/agents');
      await page.waitForTimeout(400);
      await snap(page, '34-agents');

      await page.evaluate(() => window.scrollBy(0, 300));
      await page.waitForTimeout(300);
      await snap(page, '34-agents-scrolled');
      await page.evaluate(() => window.scrollTo(0, 0));
      await pause(page);
    });
  });
});
