import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const validator = process.env.ASSET_VALIDATOR || fileURLToPath(new URL('./validate-skill-assets.mjs', import.meta.url));
const secret = 'PRIVATE-CANARY-INPUT';
function fixture(t, content = '[]') {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'asset-prompt-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const root = path.join(temp, 'skills');
  const skill = path.join(root, 'meta', 'example');
  fs.mkdirSync(skill, { recursive: true });
  fs.writeFileSync(path.join(skill, 'SKILL.md'), '# Example\n');
  const file = path.join(skill, 'test-prompts.json');
  fs.writeFileSync(file, content);
  const later = path.join(root, 'meta', 'later');
  fs.mkdirSync(later);
  fs.writeFileSync(path.join(later, 'SKILL.md'), '# Later\n');
  fs.writeFileSync(path.join(later, 'test-prompts.json'), '[]');
  return { temp, root, file };
}
function run(f, { json = true, code } = {}) {
  const args = [];
  if (code !== undefined) {
    const hook = path.join(f.temp, 'fault.mjs');
    fs.writeFileSync(hook, `import fs from 'node:fs';
const read = fs.readFileSync;
fs.readFileSync = function(file, ...args) {
  if (String(file) === process.env.PROMPT_FAULT_FILE) throw Object.assign(new Error('${secret}'), {code: process.env.PROMPT_FAULT_CODE});
  return read.call(this, file, ...args);
};`);
    args.push('--import', hook);
  }
  args.push(validator, '--source-root', f.root);
  if (json) args.push('--json');
  return spawnSync(process.execPath, args, { encoding: 'utf8', env: { ...process.env, PROMPT_FAULT_FILE: f.file, PROMPT_FAULT_CODE: code ?? '' } });
}
function checked(result, code, json = true) {
  assert.equal(result.status, 1);
  assert.equal(result.signal, null);
  assert.equal(result.stderr, '');
  assert.ok(!result.stdout.includes(secret));
  assert.ok(!result.stdout.includes('PRIVATE-'));
  if (!json) { assert.match(result.stdout, /Skill asset validation: FAIL/); assert.ok(result.stdout.includes(code)); return; }
  const report = JSON.parse(result.stdout);
  assert.equal(report.ok, false);
  assert.equal(report.summary.errors, report.errors.length);
  assert.ok(report.errors.some(e => e.code === code && e.skill === 'meta/example'));
  assert.ok(report.errors.some(e => e.code === 'empty_test_prompts' && e.skill === 'meta/later'));
  return report;
}
for (const json of [true, false]) {
  test(`invalid prompt JSON emits no input snippet in ${json ? 'JSON' : 'text'} mode`, t => {
    checked(run(fixture(t, secret), { json }), 'invalid_test_prompts_json', json);
  });
}
for (const code of ['EACCES', 'ENOENT', 'EIO', 'PRIVATE-CANARY-INPUT', '']) {
  test(`prompt read error ${code || 'missing code'} is distinct and sanitized`, t => {
    const report = checked(run(fixture(t), { code }), 'test_prompts_read_failed');
    const entry = report.errors.find(e => e.code === 'test_prompts_read_failed');
    assert.ok(entry.message.includes(/^E[A-Z0-9_]+$/.test(code) ? code : 'UNKNOWN'));
    assert.ok(!report.errors.some(e => e.code === 'invalid_test_prompts_json'));
  });
}
test('prompt read error keeps text report', t => {
  checked(run(fixture(t), { json: false, code: 'EACCES' }), 'test_prompts_read_failed', false);
});
test('directory in place of test-prompts.json reports a read failure', t => {
  const f = fixture(t); fs.unlinkSync(f.file); fs.mkdirSync(f.file);
  checked(run(f), 'test_prompts_read_failed');
});
test('valid prompt assets preserve optional results warning', t => {
  const f = fixture(t, JSON.stringify([{id:'case-1',prompt:'request',expected:'result',eval_focus:'routing',baseline_risk:'wrong route'}]));
  fs.rmSync(path.join(f.root, 'meta', 'later'), { recursive:true });
  const result = run(f); assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout); assert.equal(report.ok, true);
  assert.equal(report.summary.errors, 0); assert.ok(report.warnings.some(e=>e.code==='missing_results'));
});
