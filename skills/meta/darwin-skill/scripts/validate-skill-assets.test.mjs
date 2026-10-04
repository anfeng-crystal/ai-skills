import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const validator = process.env.ASSET_VALIDATOR || fileURLToPath(new URL('./validate-skill-assets.mjs', import.meta.url));
const fields = ['timestamp', 'commit', 'skill', 'prompt_id', 'baseline_score', 'old_score', 'new_score', 'avg_skill_delta', 'eval_mode', 'model_set', 'status', 'notes'];
const row = ['2026-10-04T00:00:00Z', 'baseline', 'example', 'case-1', '-', '-', '-', '-', 'dry_run', 'reviewer', 'keep', 'structural review only'];
const prompt = { id: 'case-1', prompt: 'example request', expected: 'example result', eval_focus: 'routing', baseline_risk: 'wrong route' };

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'skill-assets-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const skill = path.join(root, 'core', 'example');
  fs.mkdirSync(skill, { recursive: true });
  fs.writeFileSync(path.join(skill, 'SKILL.md'), '# Example\n');
  return { root, skill };
}

function writeAssets(skill, headers = fields, values = row) {
  fs.writeFileSync(path.join(skill, 'test-prompts.json'), JSON.stringify([prompt]));
  fs.writeFileSync(path.join(skill, 'results.tsv'), `${headers.join('\t')}\n${values.join('\t')}\n`);
}

function run(root, ...args) {
  const result = spawnSync(process.execPath, [validator, '--source-root', root, '--json', ...args], { encoding: 'utf8' });
  assert.equal(result.signal, null);
  assert.ok(result.stdout, result.stderr);
  return { exit: result.status, ...JSON.parse(result.stdout) };
}

test('evaluation assets remain optional', t => {
  const { root } = fixture(t);
  assert.equal(run(root).exit, 0);
  const required = run(root, '--require-eval-assets');
  assert.equal(required.exit, 1);
  assert.deepEqual(required.errors.map(error => error.code), ['missing_test_prompts', 'missing_results']);
});

test('canonical records resolve their prompt and allow unavailable measurements', t => {
  const { root, skill } = fixture(t);
  writeAssets(skill);
  const report = run(root, '--strict-results');
  assert.equal(report.exit, 0);
  assert.equal(report.summary.warnings, 0);
});

test('duplicate header cannot hide a conflicting evaluation mode', t => {
  const { root, skill } = fixture(t);
  writeAssets(skill, [...fields, 'eval_mode'], [...row, 'invented']);
  const report = run(root);
  assert.equal(report.exit, 1);
  assert.ok(report.errors.some(error => error.code === 'duplicate_results_header'));
});

test('canonical result must reference an existing prompt', t => {
  const { root, skill } = fixture(t);
  const values = [...row];
  values[3] = 'missing-case';
  writeAssets(skill, fields, values);
  const report = run(root);
  assert.equal(report.exit, 1);
  assert.ok(report.errors.some(error => error.code === 'unknown_result_prompt'));
});

test('unpaired results retain the optional-assets warning contract', t => {
  const { root, skill } = fixture(t);
  writeAssets(skill);
  fs.unlinkSync(path.join(skill, 'test-prompts.json'));
  const report = run(root);
  assert.equal(report.exit, 0);
  assert.ok(report.warnings.some(error => error.code === 'missing_test_prompts'));
});

test('legacy records warn by default and fail only in strict mode', t => {
  const { root, skill } = fixture(t);
  const legacyFields = fields.filter(field => field !== 'prompt_id').concat('dimension', 'note');
  const legacyValues = row.filter((_, index) => index !== 3).concat('routing', 'old format');
  writeAssets(skill, legacyFields, legacyValues);
  assert.equal(run(root).exit, 0);
  assert.ok(run(root).warnings.some(error => error.code === 'legacy_results_header'));
  assert.equal(run(root, '--strict-results').exit, 1);
});

test('excluded incoming tree cannot fail the default portable scan', t => {
  const { root } = fixture(t);
  const incoming = path.join(root, 'incoming', 'candidate');
  fs.mkdirSync(incoming, { recursive: true });
  fs.writeFileSync(path.join(incoming, 'SKILL.md'), '# Candidate\n' + ['','home','example','private'].join('/'));
  assert.equal(run(root).exit, 0);
  const included = run(root, '--include-incoming');
  assert.equal(included.exit, 1);
  assert.equal(included.summary.skills, 2);
  assert.ok(included.errors.some(error => error.code === 'non_portable_text'));
});

test('resource folder named incoming is still checked within an included skill', t => {
  const { root, skill } = fixture(t);
  const nested = path.join(skill, 'incoming');
  fs.mkdirSync(nested);
  fs.writeFileSync(path.join(nested, 'reference.md'), ['','home','example','private'].join('/'));
  assert.equal(run(root).exit, 1);
});


for (const value of [undefined, '', '--json', '--strict-results', '--include-incoming', '--require-eval-assets', '--help', '-h']) {
  test(`source-root rejects missing path before scanning: ${String(value)}`, t => {
    const { root } = fixture(t);
    // Give the old parser a real directory to reveal option swallowing as false success.
    if (value && value.startsWith('-')) {
      const skill = path.join(root, value, 'core', 'example');
      fs.mkdirSync(skill, { recursive: true });
      fs.writeFileSync(path.join(skill, 'SKILL.md'), '# Example\n');
    }
    const trace = path.join(root, 'scan.txt');
    const preload = path.join(root, 'trace.mjs');
    fs.writeFileSync(preload, `import fs from 'node:fs';
      const original = fs.readdirSync;
      fs.readdirSync = function(...args) { fs.appendFileSync(${JSON.stringify(trace)}, 'scan\\n'); return original.apply(this,args); };`);
    const args = ['--source-root', ...(value === undefined ? [] : [value])];
    const result = spawnSync(process.execPath, ['--import', preload, validator, ...args], {
      cwd: root, encoding: 'utf8', timeout: 10000,
    });
    assert.ifError(result.error);
    assert.equal(result.status, 1);
    assert.equal(result.stdout, '');
    assert.match(result.stderr, /--source-root requires a path value/);
    assert.equal(fs.existsSync(trace), false);
  });
}

for (const dirname of ['with space', '--json', '-h', '中文目录']) {
  test(`source-root accepts an explicit relative path: ${dirname}`, t => {
    const { root } = fixture(t);
    const skill = path.join(root, dirname, 'meta', 'example');
    fs.mkdirSync(skill, { recursive: true });
    fs.writeFileSync(path.join(skill, 'SKILL.md'), '# Example\n');
    const result = spawnSync(process.execPath, [validator, '--source-root', `./${dirname}`, '--json'], {
      cwd: root, encoding: 'utf8', timeout: 10000,
    });
    assert.ifError(result.error);
    assert.equal(result.status, 0, result.stderr);
    const report = JSON.parse(result.stdout);
    assert.equal(report.ok, true);
    assert.equal(fs.realpathSync(report.sourceRoot), fs.realpathSync(path.join(root, dirname)));
    assert.equal(report.summary.skills, 1);
  });
}
