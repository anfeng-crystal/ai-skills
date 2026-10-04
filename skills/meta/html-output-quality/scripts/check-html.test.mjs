import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import fs from 'node:fs/promises';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';
import { countDelimitedRecords, readSourceCount } from './source-count.mjs';
import { browserLaunchOptions } from './visual-checks.mjs';

const runFile = promisify(execFile);
const script = process.env.HTML_QUALITY_SCRIPT || fileURLToPath(new URL('./check-html.mjs', import.meta.url));

test('CSV/TSV count logical records with quoted line breaks, escapes, BOM and blank lines', () => {
  assert.equal(countDelimitedRecords('\uFEFFname,note\r\nA,"one\r\ntwo"\r\nB,"said ""yes"""\r\n\r\n', ','), 2);
  assert.equal(countDelimitedRecords('name\tnote\nA\t"one\ntwo"\nB\t""\n', '\t'), 2);
  assert.equal(countDelimitedRecords('name\n""\n', ','), 1);
  assert.equal(countDelimitedRecords('', ','), 0);
  assert.throws(() => countDelimitedRecords('name,note\nA,"unfinished', ','), /未闭合/);
  assert.throws(() => countDelimitedRecords('name,note\nA,"closed"extra', ','), /不正确/);
});

test('JSON counts require an explicit valid declaration or a single record array', async (t) => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'html-source-count-'));
  t.after(() => fs.rm(dir, { recursive: true, force: true }));
  const source = path.join(dir, 'source.json');
  for (const [data, expected, code] of [
    [[{ id: 1 }], 1, null],
    [{ data: { rows: [{ id: 1 }, { id: 2 }] } }, 2, null],
    [{ rows: [{ id: 1 }], tags: ['a', 'b'] }, null, 'source_json_ambiguous'],
    [{ recordCount: 1, rows: [{ id: 1 }], tags: ['a', 'b'] }, 1, null],
    [{ recordCount: -1 }, null, 'source_count_invalid'],
    [{ recordCount: 1, _recordCount: 2 }, null, 'source_count_invalid'],
    [{ recordCount: 1.5 }, null, 'source_count_invalid'],
  ]) {
    await fs.writeFile(source, `\uFEFF${JSON.stringify(data)}`);
    const findings = [];
    assert.equal(readSourceCount(source, findings), expected);
    assert.equal(findings[0]?.code ?? null, code);
  }
  await fs.writeFile(source, '{"private-value":invalid}');
  const findings = [];
  assert.equal(readSourceCount(source, findings), null);
  assert.equal(findings[0].code, 'source_json_invalid');
  assert.equal(JSON.stringify(findings).includes('private-value'), false);
});

async function chromiumOrSkip(t) {
  try {
    const { chromium } = await import('playwright');
    const browser = await chromium.launch(browserLaunchOptions());
    t.after(() => browser.close());
    return browser;
  } catch {
    t.skip('Playwright or its browser is unavailable; browser behavior remains unverified');
    return null;
  }
}

function reportHtml(scriptContent = '') {
  return `<!doctype html><html><head><meta charset="utf-8"><title>Report test</title>
    <style>body{font:16px sans-serif}main{min-height:200px}td{padding:8px}</style></head><body>
    <main data-generated-at="2026-10-04" data-source="synthetic" data-source-count="2">
    <h1>Source record verification</h1><p>This synthetic report contains two complete records for local visual verification and interaction testing.</p>
    <input type="search" aria-label="Search"><table><tbody><tr><td>Alpha first record</td></tr><tr><td>Beta second record</td></tr></tbody></table></main>
    <script>document.querySelector('input').addEventListener('input', (event) => {
      document.querySelectorAll('tr').forEach((row) => { row.hidden = !row.textContent.includes(event.target.value); });
    });${scriptContent}</script></body></html>`;
}

async function runChecker(dir, html) {
  const htmlFile = path.join(dir, 'report.html');
  const source = path.join(dir, 'source.json');
  const out = path.join(dir, 'quality');
  await fs.writeFile(htmlFile, html);
  await fs.writeFile(source, '[{},{}]');
  try { await runFile(process.execPath, [script, '--html', htmlFile, '--source', source, '--out', out]); }
  catch (error) { if (error.code !== 1) throw error; }
  return { htmlFile, report: JSON.parse(await fs.readFile(path.join(out, 'quality-report.json'), 'utf8')) };
}

test('offline visual checks block actual HTTP and WebSocket traffic and redact request details', async (t) => {
  if (!await chromiumOrSkip(t)) return;
  let requests = 0;
  const server = http.createServer((_req, res) => { requests += 1; res.writeHead(200, { 'Access-Control-Allow-Origin': '*' }); res.end('ok'); });
  server.on('upgrade', (_request, socket) => { requests += 1; socket.destroy(); });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise((resolve) => server.close(resolve)));
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'html-offline-'));
  t.after(() => fs.rm(dir, { recursive: true, force: true }));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const { report } = await runChecker(dir, reportHtml(`fetch('${origin}/private-path?credential=private-value').catch(() => {}); new WebSocket('${origin.replace('http:', 'ws:')}/socket');`));
  assert.equal(requests, 0, 'The report checker must not reach the local network probe');
  const blocked = report.findings.find((finding) => finding.code === 'external_requests_blocked');
  assert.ok(blocked, 'Blocked dynamic requests must be visible in the report');
  assert.equal(JSON.stringify(blocked).includes('private-path'), false);
  assert.equal(JSON.stringify(blocked).includes('private-value'), false);
  assert.equal(report.status, 'fail');
});

test('desktop/mobile screenshots preserve the initial report before search smoke tests', async (t) => {
  const browser = await chromiumOrSkip(t);
  if (!browser) return;
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'html-initial-view-'));
  t.after(() => fs.rm(dir, { recursive: true, force: true }));
  const { htmlFile, report } = await runChecker(dir, reportHtml());
  for (const [name, width] of [['desktop', 1365], ['mobile', 390]]) {
    assert.ok(report.screenshots[name], `${name} screenshot must exist`);
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.goto(pathToFileURL(htmlFile).href, { waitUntil: 'networkidle' });
    const initial = await page.screenshot({ fullPage: true });
    assert.ok(initial.equals(await fs.readFile(report.screenshots[name])), `${name} screenshot must equal the unfiltered initial view`);
    await page.close();
  }
  assert.equal(report.status, 'pass');
});

test('a real blocked button action keeps both screenshots and records interaction failures', async (t) => {
  if (!await chromiumOrSkip(t)) return;
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'html-blocked-action-'));
  t.after(() => fs.rm(dir, { recursive: true, force: true }));
  const html = reportHtml().replace(/<input[^>]*>/, '').replace(/<script>[\s\S]*?<\/script>/, '')
    .replace('</main>', '<button onclick="this.textContent=\'Done\'">Run</button><div style="position:fixed;inset:0;z-index:9;opacity:.01;background:white"></div></main>');
  const { report } = await runChecker(dir, html);
  assert.deepEqual(Object.keys(report.screenshots), ['desktop', 'mobile']);
  for (const file of Object.values(report.screenshots)) assert.ok((await fs.stat(file)).size > 1024);
  const failures = report.findings.filter((entry) => entry.code.endsWith('interaction_smoke_failed'));
  assert.equal(failures.length, 2);
  assert.ok(failures.every((entry) => entry.detail.phase === 'interaction' && entry.detail.error === 'TimeoutError'));
});
