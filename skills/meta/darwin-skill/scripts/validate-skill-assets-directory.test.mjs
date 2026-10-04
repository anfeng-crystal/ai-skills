import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const validator = process.env.ASSET_VALIDATOR || fileURLToPath(new URL('./validate-skill-assets.mjs', import.meta.url));
const detail = 'SYNTHETIC_PRIVATE_DIRECTORY_DETAIL';

function fixture(t) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'asset-directory-'));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const root = path.join(temp, 'source');
  const category = path.join(root, 'core');
  const skill = path.join(category, 'example');
  const refs = path.join(skill, 'references');
  const later = path.join(root, 'zz-later', 'example');
  fs.mkdirSync(refs, { recursive: true });
  fs.mkdirSync(later, { recursive: true });
  fs.writeFileSync(path.join(skill, 'SKILL.md'), '# Example\n');
  fs.writeFileSync(path.join(refs, 'reference.md'), '# Reference\n');
  fs.writeFileSync(path.join(later, 'SKILL.md'), '# Later\n');
  fs.writeFileSync(path.join(later, 'test-prompts.json'), '[]');
  fs.writeFileSync(path.join(later, 'reference.md'), ['', 'home', 'synthetic', 'private'].join('/'));
  return { temp, root, category, skill, refs, later };
}

function run(f, { target, code = 'EACCES', phase = 'all', json = true, args = [] } = {}) {
  const cli = [];
  if (target) {
    const hook = path.join(f.temp, 'fault.mjs');
    fs.writeFileSync(hook, `import fs from 'node:fs';
const original = fs.readdirSync;
fs.readdirSync = function(directory, options) {
  const phase = options?.withFileTypes ? 'portable' : 'discovery';
  if (String(directory) === process.env.ASSET_FAULT_DIRECTORY &&
      (process.env.ASSET_FAULT_PHASE === 'all' || phase === process.env.ASSET_FAULT_PHASE)) {
    throw Object.assign(new Error('${detail}'), { code: process.env.ASSET_FAULT_CODE });
  }
  return original.call(this, directory, options);
};\n`);
    cli.push('--import', hook);
  }
  cli.push(validator, '--source-root', f.root, ...args);
  if (json) cli.push('--json');
  return spawnSync(process.execPath, cli, {
    encoding: 'utf8',
    env: { ...process.env, ASSET_FAULT_DIRECTORY: target || '', ASSET_FAULT_CODE: code, ASSET_FAULT_PHASE: phase },
  });
}

function reportFrom(result, exit = 1) {
  assert.equal(result.signal, null);
  assert.equal(result.status, exit);
  assert.equal(result.stderr, '');
  assert.ok(!result.stdout.includes(detail));
  const report = JSON.parse(result.stdout);
  assert.equal(report.ok, exit === 0);
  assert.equal(report.summary.errors, report.errors.length);
  return report;
}

function directoryIssue(report, target, code = 'EACCES') {
  const issue = report.errors.find(error => error.code === 'directory_read_failed' && error.path === target);
  assert.ok(issue, `Missing directory error for ${target}`);
  assert.equal(issue.skill, null);
  assert.match(issue.message, new RegExp(`\\(${code}\\)$`));
}

function laterEvaluation(report) {
  assert.ok(report.errors.some(error => error.code === 'empty_test_prompts' && error.skill === 'zz-later/example'));
}

function laterPortable(report) {
  assert.ok(report.errors.some(error => error.code === 'non_portable_text'));
}

test('unreadable source root produces a report without claiming no skills exist', t => {
  const f = fixture(t);
  const report = reportFrom(run(f, { target: f.root }));
  directoryIssue(report, f.root);
  assert.equal(report.summary.skills, 0);
  assert.ok(!report.errors.some(error => error.code === 'no_skills_found'));
});

test('unreadable category preserves later discovery and portable errors', t => {
  const f = fixture(t);
  const report = reportFrom(run(f, { target: f.category, code: 'EIO' }));
  directoryIssue(report, f.category, 'EIO');
  assert.equal(report.summary.skills, 1);
  laterEvaluation(report);
  laterPortable(report);
});

test('portable root failure preserves completed evaluation results', t => {
  const f = fixture(t);
  const report = reportFrom(run(f, { target: f.root, code: 'ENOENT', phase: 'portable' }));
  directoryIssue(report, f.root, 'ENOENT');
  assert.equal(report.summary.skills, 2);
  laterEvaluation(report);
});

test('nested resource failure preserves independent results and stable JSON', t => {
  const f = fixture(t);
  const report = reportFrom(run(f, { target: f.refs }));
  directoryIssue(report, f.refs);
  laterEvaluation(report);
  laterPortable(report);
});

test('text output includes failed directory and later errors without exception detail', t => {
  const f = fixture(t);
  const result = run(f, { target: f.refs, json: false });
  assert.equal(result.status, 1);
  assert.equal(result.signal, null);
  assert.equal(result.stderr, '');
  assert.match(result.stdout, /Skill asset validation: FAIL/);
  assert.ok(result.stdout.includes(f.refs));
  assert.match(result.stdout, /directory_read_failed/);
  assert.match(result.stdout, /empty_test_prompts/);
  assert.match(result.stdout, /non_portable_text/);
  assert.ok(!result.stdout.includes(detail));
});

test('untrusted filesystem error code falls back to UNKNOWN', t => {
  const f = fixture(t);
  const report = reportFrom(run(f, { target: f.refs, code: 'EACCES:PRIVATE_CODE_DETAIL' }));
  directoryIssue(report, f.refs, 'UNKNOWN');
  assert.ok(!JSON.stringify(report).includes('PRIVATE_CODE_DETAIL'));
});

test('default incoming exclusion does not enumerate the excluded tree', t => {
  const f = fixture(t);
  fs.rmSync(path.dirname(f.later), { recursive: true });
  const incoming = path.join(f.root, 'incoming');
  fs.mkdirSync(path.join(incoming, 'candidate'), { recursive: true });
  fs.writeFileSync(path.join(incoming, 'candidate', 'SKILL.md'), '# Candidate\n');
  reportFrom(run(f, { target: incoming }), 0);
  directoryIssue(reportFrom(run(f, { target: incoming, args: ['--include-incoming'] })), incoming);
});

test('nested incoming resource remains checked when root incoming is excluded', t => {
  const f = fixture(t);
  const incoming = path.join(f.skill, 'incoming');
  fs.mkdirSync(incoming);
  const report = reportFrom(run(f, { target: incoming }));
  directoryIssue(report, incoming);
  laterPortable(report);
});

for (const name of ['.hidden', 'node_modules']) {
  test(`portable scan still skips nested ${name}`, t => {
    const f = fixture(t);
    fs.rmSync(path.dirname(f.later), { recursive: true });
    const excluded = path.join(f.skill, name);
    fs.mkdirSync(excluded);
    reportFrom(run(f, { target: excluded }), 0);
  });
}

test('missing root retains no_skills_found without directory errors', t => {
  const f = fixture(t);
  fs.rmSync(f.root, { recursive: true });
  const report = reportFrom(run(f));
  assert.deepEqual(report.errors.map(error => error.code), ['no_skills_found']);
});

test('empty root retains no_skills_found without directory errors', t => {
  const f = fixture(t);
  fs.rmSync(f.root, { recursive: true });
  fs.mkdirSync(f.root);
  const report = reportFrom(run(f));
  assert.deepEqual(report.errors.map(error => error.code), ['no_skills_found']);
});

test('a regular file source root returns a structured ENOTDIR failure', t => {
  const f = fixture(t);
  fs.rmSync(f.root, { recursive: true });
  fs.writeFileSync(f.root, 'synthetic regular file');
  const report = reportFrom(run(f));
  directoryIssue(report, f.root, 'ENOTDIR');
  assert.ok(!report.errors.some(error => error.code === 'no_skills_found'));
});
