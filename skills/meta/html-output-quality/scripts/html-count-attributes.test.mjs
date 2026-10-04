import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';

const script = process.env.HTML_QUALITY_SCRIPT || fileURLToPath(new URL('./check-html.mjs', import.meta.url));

function check(t, attribute, sourceCount, { before = '', after = '' } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'html-count-attribute-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const html = path.join(dir, 'report.html');
  const source = path.join(dir, 'source.json');
  fs.writeFileSync(html, `<!doctype html><html><head><title>Count report</title></head><body>
    ${before}<main data-source="synthetic" data-generated-at="2026-10-05" ${attribute}>
    <p>This local synthetic report contains enough text to verify declared record counts independently of visual rendering.</p>
    <details><summary>Records</summary>Two complete records for count comparison.</details></main>${after}</body></html>`);
  fs.writeFileSync(source, JSON.stringify(Array.from({ length: sourceCount }, () => ({}))));
  // Exercise the real CLI, static checks, source reader and report serialization.
  // Only browser work is replaced; this suite checks HTML attribute syntax.
  const visualUrl = pathToFileURL(path.join(path.dirname(script), 'visual-checks.mjs')).href;
  const preload = path.join(dir, 'visual-stub.mjs');
  fs.writeFileSync(preload, `import { registerHooks } from 'node:module';
    registerHooks({ load(url, context, nextLoad) {
      if (url === ${JSON.stringify(visualUrl)}) return { format: 'module', shortCircuit: true,
        source: 'export async function runVisualChecks() { return {}; }' };
      return nextLoad(url, context);
    } });`);
  const result = spawnSync(process.execPath, ['--import', preload, script, '--html', html, '--source', source], {
    encoding: 'utf8', timeout: 10000,
  });
  assert.ifError(result.error);
  assert.equal(result.stderr, '');
  return { result, report: JSON.parse(fs.readFileSync(path.join(dir, 'quality-report.json'), 'utf8')) };
}

for (const name of ['data-source-count', 'data-record-count']) {
  for (const [label, suffix] of [
    ['double quoted', '="2"'],
    ['single quoted', "='2'"],
    ['spaces around equals', ' = "2"'],
    ['mixed ASCII whitespace', '\t=\n\r\f"2"'],
    ['unquoted before tag end', '=2'],
    ['unquoted before next attribute', '=2 aria-label="Records"'],
  ]) {
    test(`${name}: ${label} retains count mismatch detection`, (t) => {
      const { result, report } = check(t, name + suffix, 1);
      assert.equal(result.status, 1);
      assert.equal(report.status, 'fail');
      assert.deepEqual(report.findings.filter((item) => item.code === 'count_mismatch').map((item) => item.detail),
        [{ sourceCount: 1, htmlCount: 2 }]);
      assert.ok(!report.findings.some((item) => item.code === 'html_count_missing'));
    });
  }
  test(`${name}: matching unquoted count stays clean`, (t) => {
    const { result, report } = check(t, `${name} = 2`, 2);
    assert.equal(result.status, 0);
    assert.equal(report.status, 'pass');
    assert.deepEqual(report.findings, []);
  });
  test(`${name}: zero is a declared count`, (t) => {
    const { result, report } = check(t, `${name} = 0`, 0);
    assert.equal(result.status, 0);
    assert.equal(report.status, 'pass');
  });
}

for (const attribute of ['', 'data-source-count="-1"', 'data-source-count="2.5"',
  'data-record-count=2extra', 'x-data-source-count="2"', 'data-record-count=2/']) {
  test(`unsupported or missing count is not fabricated: ${attribute || '(absent)'}`, (t) => {
    const { result, report } = check(t, attribute, 1);
    assert.equal(result.status, 0);
    assert.equal(report.status, 'warn');
    assert.ok(report.findings.some((item) => item.code === 'html_count_missing'));
    assert.ok(!report.findings.some((item) => item.code === 'count_mismatch'));
  });
}

// These contexts can contain count-shaped text without declaring an attribute.
for (const [label, before] of [
  ['comment', '<!-- data-source-count="2" -->'],
  ['comment with a fake tag', '<!-- <div data-source-count="2"> -->'],
  ['script', `<script>const sample = ' data-source-count="2"';</script>`],
  ['style', `<style>/* <div data-source-count="2"> */</style>`],
  ['textarea', '<textarea><div data-source-count="2"></textarea>'],
  ['title', '<title> data-source-count="2" </title>'],
  ['xmp', '<xmp><div data-source-count="2"></xmp>'],
  ['iframe fallback', '<iframe> data-source-count="2" </iframe>'],
  ['noembed', '<noembed> data-source-count="2" </noembed>'],
  ['noframes', '<noframes> data-source-count="2" </noframes>'],
  ['noscript', '<noscript> data-source-count="2" </noscript>'],
  ['plain text', ' data-source-count="2" '],
  ['quoted attribute', `<div title=' data-source-count="2" '></div>`],
  ['quoted greater-than', `<div title='> <div data-record-count="2">'></div>`],
  ['end tag attributes', '</div data-source-count="2">'],
  ['declaration', '<!something data-source-count="2">'],
  ['processing instruction', '<?data data-source-count="2">'],
]) {
  test(`count-shaped ${label} cannot hide a real mismatch`, (t) => {
    const { result, report } = check(t, 'data-source-count="1"', 2, { before });
    assert.equal(result.status, 1);
    assert.deepEqual(report.findings.filter((f) => f.code === 'count_mismatch').map((f) => f.detail),
      [{ sourceCount: 2, htmlCount: 1 }]);
  });
  test(`count-shaped ${label} does not fabricate a declaration`, (t) => {
    const { report } = check(t, '', 2, { before });
    assert.ok(report.findings.some((f) => f.code === 'html_count_missing'));
    assert.ok(!report.findings.some((f) => f.code === 'count_mismatch'));
  });
}

for (const [label, attribute, before, after, sourceCount] of [
  ['first valid real declaration', 'data-record-count="1"', '<div data-source-count="2"></div>', '', 2],
  ['skip invalid declaration', 'data-record-count="2"', '<div data-source-count="no"></div>', '', 2],
  ['later real declaration', 'data-record-count="2"', '', '<div data-source-count="1"></div>', 2],
  ['fake declaration after real one', 'data-record-count="2"', '', '<!-- data-source-count="1" -->', 2],
  ['attribute on raw-text element', '', '<script data-record-count="2">" data-source-count=1 "</script>', '', 2],
  ['raw close name boundary', 'data-record-count="2"', '<script>"</scriptx><i data-source-count=1>"</script>', '', 2],
  ['mixed-case raw close', 'DATA-RECORD-COUNT = 2', '<SCRIPT>" data-source-count=1 "</ScRiPt >', '', 2],
  ['quoted greater-than before real attribute', `title='a > b' data-source-count="2"`, '', '', 2],
  ['first valid same tag', 'data-record-count="2" data-source-count="1"', '', '', 2],
  ['zero with fake nonzero', 'data-record-count=0', '<!-- data-source-count="2" -->', '', 0],
]) {
  test(`context control: ${label}`, (t) => {
    const { report } = check(t, attribute, sourceCount, { before, after });
    assert.ok(!report.findings.some((f) => ['html_count_missing', 'count_mismatch'].includes(f.code)));
  });
}

for (const before of ['<plaintext> data-source-count="2" ', '<script> data-source-count="2" ', '<!-- data-source-count="2" ']) {
  test(`unclosed text context does not create following declarations: ${before}`, (t) => {
    const { report } = check(t, 'data-source-count="2"', 2, { before });
    assert.ok(report.findings.some((f) => f.code === 'html_count_missing'));
  });
}
