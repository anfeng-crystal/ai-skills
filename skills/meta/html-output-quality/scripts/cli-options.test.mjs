import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';

const script = process.env.HTML_QUALITY_SCRIPT || fileURLToPath(new URL('./check-html.mjs', import.meta.url));

function fixture(t) {
  const dir = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'html-cli-options-')));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const html = path.join(dir, 'report with spaces.html');
  const source = path.join(dir, 'source with spaces.json');
  const out = path.join(dir, 'quality with spaces');
  fs.writeFileSync(html, '<!doctype html><html><head><title>Local report</title></head><body><main data-source="synthetic" data-generated-at="2026-10-05" data-source-count="1"><p>This synthetic report contains enough text to exercise command line options using local temporary inputs only.</p><details><summary>Record</summary>First complete record</details></main></body></html>');
  fs.writeFileSync(source, '[{}]');
  // The CLI and its real static checks execute; only visual checks are replaced.
  const visualMarker = path.join(dir, 'visual-called.json');
  const visualUrl = pathToFileURL(path.join(path.dirname(script), 'visual-checks.mjs')).href;
  const preload = path.join(dir, 'visual-stub.mjs');
  const visualSource = `import fs from 'node:fs';
export async function runVisualChecks(args) {
  fs.writeFileSync(${JSON.stringify(visualMarker)}, JSON.stringify(args));
  return {};
}`;
  fs.writeFileSync(preload, `import { registerHooks } from 'node:module';
registerHooks({ load(url, context, nextLoad) {
  if (url === ${JSON.stringify(visualUrl)}) return { format: 'module', shortCircuit: true, source: ${JSON.stringify(visualSource)} };
  return nextLoad(url, context);
} });`);
  return { dir, html, source, out, preload, visualMarker };
}

function run(f, args) {
  const result = spawnSync(process.execPath, ['--import', f.preload, script, ...args], {
    cwd: f.dir, encoding: 'utf8', timeout: 15000,
  });
  assert.ifError(result.error);
  return result;
}

for (const option of ['--html', '--source', '--out']) {
  for (const [name, tail] of [
    ['end of command', []],
    ['explicit empty value', ['']],
    ['following long help flag', ['--help']],
    ['following short help flag', ['-h']],
    ['following browser option', ['--browser-channel', 'chrome']],
  ]) {
    test(`${option} rejects a missing value before ${name}, without output side effects`, (t) => {
      const f = fixture(t);
      const before = fs.readdirSync(f.dir).sort();
      const prefix = option === '--html' ? [] : ['--html', f.html];
      const result = run(f, [...prefix, option, ...tail]);
      assert.equal(result.status, 2, `${result.stdout}\n${result.stderr}`);
      assert.equal(result.stderr, `check-html failed: ${option} 缺少参数值\n`);
      assert.equal(result.stdout, '');
      assert.deepEqual(fs.readdirSync(f.dir).sort(), before, 'Invalid options must not create reports, output directories or call visual checks');
    });
  }
}

test('a missing source value does not consume the requested output option', (t) => {
  const f = fixture(t);
  const result = run(f, ['--html', f.html, '--source', '--out', f.out]);
  assert.equal(result.status, 2);
  assert.equal(result.stderr, 'check-html failed: --source 缺少参数值\n');
  assert.equal(fs.existsSync(f.out), false);
  assert.equal(fs.existsSync(f.visualMarker), false);
});

test('valid relative file values and explicit output keep source counting and visual dispatch', (t) => {
  const f = fixture(t);
  const result = run(f, ['--html', path.basename(f.html), '--source', path.basename(f.source), '--out', path.basename(f.out)]);
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(fs.readFileSync(path.join(f.out, 'quality-report.json'), 'utf8'));
  assert.equal(report.status, 'pass');
  assert.equal(report.html, f.html);
  assert.equal(report.source, f.source);
  assert.equal(report.findings.length, 0);
  assert.ok(fs.readFileSync(path.join(f.out, 'quality-report.md'), 'utf8').includes('**状态**：pass'));
  assert.equal(JSON.parse(fs.readFileSync(f.visualMarker, 'utf8')).out, f.out);
});

test('omitting source and output still emits a source limitation in the HTML directory', (t) => {
  const f = fixture(t);
  const result = run(f, ['--html', f.html]);
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(fs.readFileSync(path.join(f.dir, 'quality-report.json'), 'utf8'));
  assert.equal(report.status, 'warn');
  assert.equal(report.source, null);
  assert.ok(report.findings.some((finding) => finding.code === 'source_missing'));
  assert.equal(JSON.parse(fs.readFileSync(f.visualMarker, 'utf8')).out, f.dir);
});

test('standalone help remains available without HTML or report writes', (t) => {
  const f = fixture(t);
  for (const help of ['--help', '-h']) {
    const result = run(f, [help]);
    assert.equal(result.status, 0);
    assert.match(result.stdout, /^Usage:/);
    assert.equal(result.stderr, '');
    assert.equal(fs.existsSync(f.visualMarker), false);
    assert.equal(fs.existsSync(path.join(f.dir, 'quality-report.json')), false);
  }
});
