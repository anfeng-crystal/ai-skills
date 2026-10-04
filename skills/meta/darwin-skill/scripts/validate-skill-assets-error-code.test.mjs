import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const validator = process.env.ASSET_VALIDATOR || fileURLToPath(new URL('./validate-skill-assets.mjs', import.meta.url));
const privateCode = 'EPRIVATE_SYNTHETIC_DETAIL';
const privateMessage = 'private-synthetic-exception';
const phases = [
  ['prompt', 'test_prompts_read_failed', 'Cannot read test-prompts.json'],
  ['results', 'results_read_failed', 'Cannot read results.tsv'],
  ['text', 'text_read_failed', 'Cannot check portable text'],
  ['directory', 'directory_read_failed', 'Cannot scan directory'],
];

function fixture(t, phase, code) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'asset-error-code-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const root = path.join(temp, 'skills');
  const skill = path.join(root, 'meta', 'example');
  const later = path.join(root, 'meta', 'later');
  fs.mkdirSync(skill, { recursive: true });
  fs.mkdirSync(later);
  for (const dir of [skill, later]) fs.writeFileSync(path.join(dir, 'SKILL.md'), '# Synthetic\n');
  fs.writeFileSync(path.join(skill, 'test-prompts.json'), JSON.stringify([{
    id: 'one', prompt: 'request', expected: 'response', eval_focus: 'routing', baseline_risk: 'wrong route',
  }]));
  fs.writeFileSync(path.join(skill, 'results.tsv'), 'skill\teval_mode\tnotes\nexample\tdry_run\tsynthetic\n');
  fs.writeFileSync(path.join(later, 'test-prompts.json'), '[]');
  const target = phase === 'directory' ? skill : path.join(skill, {
    prompt: 'test-prompts.json', results: 'results.tsv', text: 'SKILL.md',
  }[phase]);
  const hook = path.join(temp, 'fault.mjs');
  fs.writeFileSync(hook, `import fs from 'node:fs';
const method = ${JSON.stringify(phase === 'directory' ? 'readdirSync' : 'readFileSync')};
const original = fs[method];
fs[method] = function(file, ...args) {
  if (String(file) === ${JSON.stringify(target)}) throw Object.assign(new Error(${JSON.stringify(privateMessage)}), { code: ${JSON.stringify(code)} });
  return original.call(this, file, ...args);
};\n`);
  return { root, hook };
}

function run(t, phase, code, json = true) {
  const f = fixture(t, phase, code);
  const result = spawnSync(process.execPath, ['--import', f.hook, validator, '--source-root', f.root,
    ...(json ? ['--json'] : [])], { encoding: 'utf8', timeout: 10000 });
  assert.equal(result.signal, null);
  assert.equal(result.status, 1);
  assert.equal(result.stderr, '');
  assert.ok(!result.stdout.includes(privateCode), 'unrecognized code must not expose source data');
  assert.ok(!result.stdout.includes(privateMessage), 'exception text must remain private');
  return result.stdout;
}

for (const [phase, diagnostic, label] of phases) {
  for (const json of [true, false]) {
    test(`${phase} rejects an errno-shaped private code in ${json ? 'JSON' : 'text'} output`, t => {
      const stdout = run(t, phase, privateCode, json);
      if (!json) {
        assert.match(stdout, /Skill asset validation: FAIL/);
        assert.ok(stdout.includes(`${diagnostic}: ${label} (UNKNOWN)`));
        assert.ok(stdout.includes('empty_test_prompts'));
        return;
      }
      const report = JSON.parse(stdout);
      assert.equal(report.ok, false);
      assert.equal(report.summary.errors, report.errors.length);
      assert.ok(report.errors.some(e => e.code === diagnostic && e.message === `${label} (UNKNOWN)`));
      assert.ok(report.errors.some(e => e.code === 'empty_test_prompts' && e.skill === 'meta/later'));
    });
  }
  test(`${phase} retains a known system errno and later independent checks`, t => {
    const report = JSON.parse(run(t, phase, 'EACCES'));
    assert.ok(report.errors.some(e => e.code === diagnostic && e.message === `${label} (EACCES)`));
    assert.ok(report.errors.some(e => e.code === 'empty_test_prompts'));
  });
}

for (const code of ['toString', '', 13, null]) {
  test(`non-system code ${JSON.stringify(code)} becomes UNKNOWN`, t => {
    const report = JSON.parse(run(t, 'prompt', code));
    assert.ok(report.errors.some(e => e.code === 'test_prompts_read_failed'
      && e.message === 'Cannot read test-prompts.json (UNKNOWN)'));
  });
}
