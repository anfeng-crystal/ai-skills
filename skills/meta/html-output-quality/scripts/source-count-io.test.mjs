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
const marker = 'private-source-error-sentinel';

function fixture(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'html-source-io-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const source = path.join(dir, 'source.json');
  fs.writeFileSync(source, '[{}]');
  return { dir, source };
}

function assertReadFailure(findings, code) {
  assert.equal(findings.length, 1);
  assert.equal(findings[0].level, 'High');
  assert.equal(findings[0].code, 'source_read_failed');
  assert.deepEqual(findings[0].detail, { code });
  assert.equal(JSON.stringify(findings).includes(marker), false);
}

for (const [name, code, expected] of [
  ['access denied', 'EACCES', 'EACCES'],
  ['removed after existence check', 'ENOENT', 'ENOENT'],
  ['device read failed', 'EIO', 'EIO'],
  ['missing error code', undefined, 'UNKNOWN'],
  ['unrecognized upper-case code', 'PRIVATE_SOURCE_ERROR_SENTINEL', 'UNKNOWN'],
  ['message embedded in code', `EIO: ${marker}`, 'UNKNOWN'],
  ['non-string error code', { private: marker }, 'UNKNOWN'],
]) {
  test(`source read failure is reported without payload: ${name}`, (t) => {
    const { source } = fixture(t);
    const original = fs.readFileSync;
    fs.readFileSync = function (file, ...args) {
      if (file === source) throw Object.assign(new Error(marker), { code, path: marker });
      return original.call(this, file, ...args);
    };
    const findings = [];
    try { assert.equal(readSourceCount(source, findings), null); }
    finally { fs.readFileSync = original; }
    assertReadFailure(findings, expected);
  });
}

test('native directory source errors become a finding on platforms that reject directory reads', (t) => {
  const { dir } = fixture(t);
  let code;
  try { fs.readFileSync(dir, 'utf8'); }
  catch (error) { code = error.code; }
  if (code !== 'EISDIR') {
    t.skip('This platform does not reject directory reads with EISDIR');
    return;
  }
  const findings = [];
  assert.equal(readSourceCount(dir, findings), null);
  assertReadFailure(findings, 'EISDIR');
});

test('successful source counts and existing failure classifications stay intact', (t) => {
  const { dir } = fixture(t);
  for (const [file, content, count, expected] of [
    ['array.json', '\uFEFF[{},{}]', 2, null],
    ['nested.json', '{"data":{"rows":[{},{},{}]}}', 3, null],
    ['declared.json', '{"recordCount":4,"_recordCount":4,"rows":[],"tags":[]}', 4, null],
    ['data.csv', 'name,note\nA,"one\ntwo"\nB,"quoted ""text"""\n', 2, null],
    ['data.tsv', 'name\tnote\nA\t"one\ntwo"\n', 1, null],
    ['ambiguous.json', '{"rows":[],"tags":[]}', null, 'source_json_ambiguous'],
    ['invalid.json', `{"${marker}":invalid}`, null, 'source_json_invalid'],
    ['negative.json', '{"recordCount":-1}', null, 'source_count_invalid'],
    ['invalid.csv', 'name\n"unclosed', null, 'source_delimited_invalid'],
  ]) {
    const source = path.join(dir, file);
    fs.writeFileSync(source, content);
    const findings = [];
    assert.equal(readSourceCount(source, findings), count);
    assert.equal(findings[0]?.code ?? null, expected);
    assert.equal(JSON.stringify(findings).includes(marker), false);
  }
  const absent = [];
  assert.equal(readSourceCount(path.join(dir, 'missing.json'), absent), null);
  assert.equal(absent[0].code, 'source_not_found');
  const unspecified = [];
  assert.equal(readSourceCount(null, unspecified), null);
  assert.equal(unspecified[0].code, 'source_missing');
});

for (const [name, code, expected] of [
  ['EACCES', 'EACCES', 'EACCES'],
  ['ENOENT', 'ENOENT', 'ENOENT'],
  ['EIO', 'EIO', 'EIO'],
  ['unknown', 'PRIVATE_SOURCE_ERROR_SENTINEL', 'UNKNOWN'],
]) {
  test(`CLI writes failed JSON/Markdown and continues independent checks after ${name}`, (t) => {
    const { dir, source } = fixture(t);
    const html = path.join(dir, 'report.html');
    // Missing title supplies an independent static finding that must survive.
    fs.writeFileSync(html, '<!doctype html><html><body><main data-source="synthetic" data-generated-at="2026-10-05" data-source-count="2"><p>This local synthetic report contains enough text to exercise source error handling without reading any private data.</p><details><summary>Detail</summary>Local detail</details></main></body></html>');
    const preload = path.join(dir, 'inject.mjs');
    fs.writeFileSync(preload, `import fs from 'node:fs';
const original = fs.readFileSync;
fs.readFileSync = function (file, ...args) {
  if (file === process.env.TEST_SOURCE) throw Object.assign(new Error(${JSON.stringify(marker)}), { code: ${JSON.stringify(code)} });
  return original.call(this, file, ...args);
};
`);
    const out = path.join(dir, 'quality');
    const result = spawnSync(process.execPath, ['--import', preload, script, '--html', html, '--source', source, '--out', out, '--browser-path', path.join(dir, 'absent-browser')], {
      encoding: 'utf8', timeout: 15000,
      env: { ...process.env, TEST_SOURCE: source },
    });
    assert.ifError(result.error);
    assert.equal(result.status, 1, result.stderr);
    const json = fs.readFileSync(path.join(out, 'quality-report.json'), 'utf8');
    const markdown = fs.readFileSync(path.join(out, 'quality-report.md'), 'utf8');
    const report = JSON.parse(json);
    assert.equal(report.status, 'fail');
    const failure = report.findings.filter((finding) => finding.code === 'source_read_failed');
    assertReadFailure(failure, expected);
    assert.ok(report.findings.some((finding) => finding.code === 'title_missing'));
    assert.ok(report.findings.some((finding) => ['playwright_unavailable', 'playwright_browser_unavailable', 'playwright_check_failed'].includes(finding.code)), 'Independent visual checks must still run');
    assert.ok(!report.findings.some((finding) => finding.code === 'count_mismatch'));
    assert.match(markdown, /source_read_failed/);
    assert.equal(JSON.parse(result.stdout).status, 'fail');
    assert.equal(result.stderr, '');
    assert.ok(!`${json}${markdown}${result.stdout}${result.stderr}`.includes(marker));
    assert.ok(!`${json}${markdown}${result.stdout}${result.stderr}`.includes('PRIVATE_SOURCE_ERROR_SENTINEL'));
  });
}
