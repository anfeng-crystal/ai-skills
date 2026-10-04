import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';

const modulePath = process.env.SOURCE_COUNT_MODULE || fileURLToPath(new URL('./source-count.mjs', import.meta.url));
const { readSourceCount } = await import(pathToFileURL(modulePath).href);
const script = process.env.HTML_QUALITY_SCRIPT || fileURLToPath(new URL('./check-html.mjs', import.meta.url));
// Construct valid deep JSON without using a recursive test serializer.
const nested = (leaf, depth = 12000) => '{"child":'.repeat(depth) + leaf + '}'.repeat(depth);

function fixture(t, content) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'html-source-depth-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const source = path.join(dir, 'source.json');
  fs.writeFileSync(source, content);
  return { dir, source };
}

for (const [label, content, expected, finding] of [
  ['deep unique array', nested('[{},{}]'), 2, null],
  ['deep empty array', nested('[]'), 0, null],
  ['deep multiple arrays', nested('{"rows":[{}],"tags":[]}'), null, 'source_json_ambiguous'],
  ['deep no array', nested('{"value":null}'), null, 'source_json_no_array'],
  ['arrays are records, not nested containers', nested('[{"children":[]},{"children":[1,2,3]}]'), 2, null],
  ['declared count takes precedence', '{"recordCount":7,"payload":' + nested('[{}]') + '}', 7, null],
  ['matching declarations', '{"recordCount":0,"_recordCount":0,"payload":' + nested('[{}]') + '}', 0, null],
  ['conflicting declarations', '{"recordCount":0,"_recordCount":1,"payload":' + nested('[{}]') + '}', null, 'source_count_invalid'],
  ['shallow unique', '{"items":[1,2,3]}', 3, null],
  ['top array', '[{"children":[]},{}]', 2, null],
  ['scalar', 'null', null, 'source_json_no_array'],
  ['invalid JSON', '{"rows":[}', null, 'source_json_invalid'],
  ['BOM deep JSON', '\uFEFF' + nested('[{}]'), 1, null],
]) {
  test(`source count retains semantics: ${label}`, (t) => {
    const { source } = fixture(t, content);
    const findings = [];
    assert.equal(readSourceCount(source, findings), expected);
    assert.deepEqual(findings.map((item) => item.code), finding ? [finding] : []);
  });
}

for (const [label, content, htmlCount, expectedStatus, expectedCode] of [
  ['matching deep source', nested('[{},{}]'), 2, 'pass', null],
  ['mismatched deep source', nested('[{},{}]'), 1, 'fail', 'count_mismatch'],
  ['ambiguous deep source', nested('{"a":[],"b":[{}]}'), 2, 'warn', 'source_json_ambiguous'],
  ['deep source with no array', nested('0'), 2, 'warn', 'source_json_no_array'],
]) {
  test(`real CLI still writes both reports: ${label}`, (t) => {
    const { dir, source } = fixture(t, content);
    const html = path.join(dir, 'report.html');
    fs.writeFileSync(html, `<!doctype html><html><head><title>Offline source depth</title></head><body>
      <main data-source="synthetic" data-generated-at="2026-10-05" data-source-count="${htmlCount}">
      <p>This synthetic local report has enough explanatory text to exercise valid nested JSON record counting without network access.</p>
      <details><summary>Records</summary>Local synthetic source data for static checking.</details></main></body></html>`);
    const visualUrl = pathToFileURL(path.join(path.dirname(script), 'visual-checks.mjs')).href;
    const preload = path.join(dir, 'visual-stub.mjs');
    fs.writeFileSync(preload, `import { registerHooks } from 'node:module';
      registerHooks({ load(url, context, nextLoad) {
        if (url === ${JSON.stringify(visualUrl)}) return { format: 'module', shortCircuit: true,
          source: 'export async function runVisualChecks() { return {}; }' };
        return nextLoad(url, context);
      } });`);
    const result = spawnSync(process.execPath, ['--import', preload, script,
      '--html', html, '--source', source], { encoding: 'utf8', timeout: 10000 });
    assert.ifError(result.error);
    assert.equal(result.stderr, '');
    assert.equal(result.status, expectedStatus === 'fail' ? 1 : 0);
    const report = JSON.parse(fs.readFileSync(path.join(dir, 'quality-report.json'), 'utf8'));
    const markdown = fs.readFileSync(path.join(dir, 'quality-report.md'), 'utf8');
    assert.equal(report.status, expectedStatus);
    assert.equal(JSON.parse(result.stdout).status, expectedStatus);
    assert.deepEqual(report.findings.map((item) => item.code), expectedCode ? [expectedCode] : []);
    assert.ok(markdown.length > 0);
    if (expectedCode) assert.ok(markdown.includes(expectedCode));
  });
}
