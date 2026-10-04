import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { browserLaunchOptions, runVisualChecks } from './visual-checks.mjs';
import { smokeTestInteraction } from './interaction-checks.mjs';

async function playwrightOrSkip(t) {
  try { return (await import('playwright')).chromium; }
  catch { t.skip('Playwright is unavailable'); return null; }
}

async function browserOrSkip(t) {
  const chromium = await playwrightOrSkip(t);
  if (!chromium) return null;
  try {
    const browser = await chromium.launch(browserLaunchOptions());
    t.after(() => browser.close());
    return browser;
  } catch { t.skip('Configured browser is unavailable; browser behavior remains unverified'); return null; }
}

test('browser selection is explicit, supports existing host path, and isolates CLI choice', () => {
  assert.deepEqual(browserLaunchOptions({}, {}), { headless: true });
  assert.deepEqual(browserLaunchOptions({}, { WEB_ACCESS_BROWSER_PATH: '/browser path/chrome' }), { headless: true, executablePath: '/browser path/chrome' });
  assert.deepEqual(browserLaunchOptions({}, { HTML_QUALITY_BROWSER_CHANNEL: 'chrome' }), { headless: true, channel: 'chrome' });
  assert.deepEqual(browserLaunchOptions({ browserChannel: 'msedge' }, { WEB_ACCESS_BROWSER_PATH: '/host/chrome' }), { headless: true, channel: 'msedge' });
  assert.deepEqual(browserLaunchOptions({ browserPath: '/chosen/chrome' }, { HTML_QUALITY_BROWSER_CHANNEL: 'chrome' }), { headless: true, executablePath: '/chosen/chrome' });
  assert.throws(() => browserLaunchOptions({ browserPath: '/chrome', browserChannel: 'chrome' }, {}), /不能同时/);
  assert.throws(() => browserLaunchOptions({}, { HTML_QUALITY_BROWSER_PATH: '/chrome', HTML_QUALITY_BROWSER_CHANNEL: 'chrome' }), /不能同时/);
});

test('smoke rejects no-op focus, empty search, existing active and aria-sort states', async (t) => {
  const browser = await browserOrSkip(t);
  if (!browser) return;
  const page = await browser.newPage();
  t.after(() => page.close());
  for (const html of [
    '<button>Does nothing</button>',
    '<input type="search">',
    '<button data-filter-level="all">All</button><button class="active" data-filter-level="high">High</button>',
    '<button>Focus target</button><table><thead><tr><th data-sort="name" aria-sort="ascending">Name</th></tr></thead><tbody><tr><td>Alpha</td></tr></tbody></table>',
  ]) {
    await page.setContent(html);
    assert.equal((await smokeTestInteraction(page)).ok, false, html);
  }
});

test('smoke recognizes CSS filtering, debounce, native details, tab visibility and sorting', async (t) => {
  const browser = await browserOrSkip(t);
  if (!browser) return;
  const page = await browser.newPage();
  t.after(() => page.close());
  const rows = '<table><tbody><tr><td>Alpha</td></tr><tr><td>Beta</td></tr></tbody></table>';
  for (const [html, action] of [
    [`<input type="search" oninput="document.querySelectorAll('tr').forEach(r=>r.style.display='none')">${rows}`, 'search'],
    [`<input type="search" oninput="setTimeout(()=>document.querySelectorAll('tr').forEach(r=>r.style.visibility='hidden'),150)">${rows}`, 'search'],
    ['<details><summary>More</summary><p>Expanded details</p></details>', 'details'],
    ['<button onclick="document.querySelector(\'output\').textContent=\'Done\'">Run</button><output>Ready</output>', 'button'],
    ['<button data-tab="a">A</button><button data-tab="b" onclick="document.querySelectorAll(\'[data-panel]\').forEach(n=>n.style.visibility=n.dataset.panel===\'b\'?\'visible\':\'hidden\')">B</button><div data-panel="a">A panel</div><div data-panel="b" style="visibility:hidden">B panel</div>', 'tab'],
    ['<table><thead><tr><th data-sort="name" onclick="this.setAttribute(\'aria-sort\',\'descending\');document.querySelector(\'tbody\').appendChild(document.querySelector(\'tbody tr\'))">Sort</th></tr></thead><tbody><tr><td>Alpha</td></tr><tr><td>Beta</td></tr></tbody></table>', 'sort'],
  ]) {
    await page.setContent(html);
    assert.deepEqual(await smokeTestInteraction(page), { ok: true, action });
  }
});

test('hidden or disabled search does not prevent a supported visible details action', async (t) => {
  const browser = await browserOrSkip(t);
  if (!browser) return;
  const page = await browser.newPage();
  t.after(() => page.close());
  await page.setContent('<input type="search" hidden><input type="search" disabled><details><summary>More</summary><p>Visible content</p></details>');
  assert.deepEqual(await smokeTestInteraction(page), { ok: true, action: 'details' });
});

async function fakeVisualCase(t, { failViewport, failInteraction, failClose } = {}) {
  const chromium = await playwrightOrSkip(t);
  if (!chromium) return null;
  const out = await fs.mkdtemp(path.join(os.tmpdir(), 'html-partial-'));
  t.after(() => fs.rm(out, { recursive: true, force: true }));
  let contexts = 0;
  let closed = 0;
  let browserClosed = false;
  t.mock.method(chromium, 'launch', async () => ({
    newContext: async (options) => {
      assert.deepEqual(options, { offline: true, serviceWorkers: 'block' });
      const index = contexts++;
      if (index === failViewport) throw new Error('synthetic context failure: private-value');
      let evaluations = 0;
      return {
        route: async () => {}, routeWebSocket: async () => {},
        newPage: async () => ({
          setViewportSize: async () => {}, goto: async () => {},
          evaluate: async () => {
            if (evaluations++ && failInteraction) throw new Error('synthetic interaction error: private-value');
            return { bodyTextLength: 200, mainVisible: true, scrollWidth: 390, clientWidth: 390, interactiveCount: failInteraction ? 1 : 0 };
          },
          locator: () => { throw new Error('synthetic interaction error: private-value'); },
          screenshot: async ({ path: output }) => fs.writeFile(output, Buffer.alloc(2048)),
        }),
        close: async () => { closed += 1; if (failClose) throw new Error('private-value'); },
      };
    },
    close: async () => { browserClosed = true; if (failClose) throw new Error('private-value'); },
  }));
  const findings = [];
  const screenshots = await runVisualChecks({ html: path.join(out, 'synthetic.html'), out }, findings);
  assert.equal(browserClosed, true);
  assert.equal(closed, contexts - (failViewport === undefined ? 0 : 1));
  assert.equal(JSON.stringify(findings).includes('private-value'), false);
  for (const file of Object.values(screenshots)) assert.equal((await fs.stat(file)).size, 2048);
  return { screenshots, findings };
}

test('a failed viewport preserves successful screenshot paths and the other viewport runs', async (t) => {
  for (const failViewport of [0, 1]) {
    await t.test(`viewport ${failViewport}`, async (child) => {
      const result = await fakeVisualCase(child, { failViewport });
      if (!result) return;
      assert.deepEqual(Object.keys(result.screenshots), [failViewport === 0 ? 'mobile' : 'desktop']);
      assert.ok(result.findings.some((entry) => entry.code === `${failViewport === 0 ? 'desktop' : 'mobile'}_visual_check_failed`));
    });
  }
});

test('interaction and cleanup failures retain both initial screenshots and report safe diagnostics', async (t) => {
  const result = await fakeVisualCase(t, { failInteraction: true, failClose: true });
  if (!result) return;
  assert.deepEqual(Object.keys(result.screenshots), ['desktop', 'mobile']);
  assert.equal(result.findings.filter((entry) => entry.code.endsWith('interaction_smoke_failed')).length, 2);
  assert.equal(result.findings.filter((entry) => entry.code.endsWith('close_failed')).length, 3);
});
