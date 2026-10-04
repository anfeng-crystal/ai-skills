import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const validator = process.env.ASSET_VALIDATOR || fileURLToPath(new URL('./validate-skill-assets.mjs', import.meta.url));
const fields = ['timestamp', 'commit', 'skill', 'prompt_id', 'baseline_score', 'old_score', 'new_score', 'avg_skill_delta', 'eval_mode', 'model_set', 'status', 'notes'];
const values = ['2026-10-05', 'baseline', 'example', 'case-1', '-', '-', '-', '-', 'dry_run', 'reviewer', 'keep', 'synthetic'];

function fixture(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'asset-read-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const root = path.join(dir, 'source');
  const skill = path.join(root, 'core', 'example');
  fs.mkdirSync(skill, { recursive: true });
  fs.writeFileSync(path.join(skill, 'SKILL.md'), '# Example\n');
  fs.writeFileSync(path.join(skill, 'test-prompts.json'), JSON.stringify([{
    id: 'case-1', prompt: 'request', expected: 'result', eval_focus: 'routing', baseline_risk: 'wrong route',
  }]));
  fs.writeFileSync(path.join(skill, 'results.tsv'), `${fields.join('\t')}\n${values.join('\t')}\n`);
  // The later Skill must still contribute its independent validation error.
  const later = path.join(root, 'core', 'zz-later');
  fs.mkdirSync(later);
  fs.writeFileSync(path.join(later, 'SKILL.md'), '# Later\n');
  fs.writeFileSync(path.join(later, 'test-prompts.json'), '[]');
  fs.writeFileSync(path.join(later, 'reference.md'), ['','home','synthetic-user','private'].join('/'));
  return { dir, root, skill };
}

function run(f, { file, code = 'EACCES', json = true } = {}) {
  const args = [];
  if (file) {
    const hook = path.join(f.dir, 'mock-fs.mjs');
    fs.writeFileSync(hook, `import fs from 'node:fs';
const original = fs.readFileSync;
fs.readFileSync = function(file, ...args) {
  if (String(file) === process.env.ASSET_FAULT_FILE) {
    throw Object.assign(new Error('sensitive-synthetic-read-detail'), { code: process.env.ASSET_FAULT_CODE });
  }
  return original.call(this, file, ...args);
};\n`);
    args.push('--import', hook);
  }
  args.push(validator, '--source-root', f.root);
  if (json) args.push('--json');
  return spawnSync(process.execPath, args, {
    encoding: 'utf8', env: { ...process.env, ASSET_FAULT_FILE: file || '', ASSET_FAULT_CODE: code },
  });
}

function checkReport(result, expectedCode) {
  assert.equal(result.status, 1);
  assert.equal(result.signal, null);
  assert.ok(result.stdout.trim(), result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.ok, false);
  assert.equal(report.summary.errors, report.errors.length);
  assert.ok(report.errors.some(error => error.code === expectedCode));
  assert.ok(report.errors.some(error => error.code === 'empty_test_prompts' && error.skill === 'core/zz-later'));
  assert.ok(report.errors.some(error => error.code === 'non_portable_text'));
  assert.equal(result.stderr, '');
  assert.ok(!result.stdout.includes('sensitive-synthetic-read-detail'));
  return report;
}

test('results directory becomes a report error and later checks continue', t => {
  const f = fixture(t);
  fs.unlinkSync(path.join(f.skill, 'results.tsv'));
  fs.mkdirSync(path.join(f.skill, 'results.tsv'));
  checkReport(run(f), 'results_read_failed');
});

for (const code of ['EACCES', 'ENOENT', 'EIO']) {
  test(`results read ${code} keeps JSON report and unrelated checks`, t => {
    const f = fixture(t);
    const report = checkReport(run(f, { file: path.join(f.skill, 'results.tsv'), code }), 'results_read_failed');
    assert.ok(report.errors.some(error => error.code === 'results_read_failed' && error.message.includes(code)));
  });
}

for (const basename of ['SKILL.md', 'reference.md']) {
  test(`portable scan read failure in ${basename} preserves the report`, t => {
    const f = fixture(t);
    const file = path.join(f.skill, basename);
    fs.writeFileSync(file, '# Synthetic\n');
    checkReport(run(f, { file }), 'text_read_failed');
  });
}

test('text mode reports read errors without exposing underlying exception messages', t => {
  const f = fixture(t);
  const result = run(f, { file: path.join(f.skill, 'results.tsv'), json: false });
  assert.equal(result.status, 1);
  assert.match(result.stdout, /Skill asset validation: FAIL/);
  assert.match(result.stdout, /results_read_failed/);
  assert.match(result.stdout, /core\/zz-later/);
  assert.ok(!result.stdout.includes('sensitive-synthetic-read-detail'));
  assert.equal(result.stderr, '');
});

test('readable canonical assets retain success with optional assets in another Skill', t => {
  const f = fixture(t);
  fs.rmSync(path.join(f.root, 'core', 'zz-later'), { recursive: true });
  const result = run(f);
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.ok, true);
  assert.equal(report.summary.errors, 0);
  assert.equal(report.summary.warnings, 0);
});
