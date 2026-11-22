import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { appendFileSync, copyFileSync, cpSync, mkdirSync, mkdtempSync, rmSync, unlinkSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

const repo = path.resolve(import.meta.dirname, '..');

function fixture(t) {
  const root = mkdtempSync(path.join(os.tmpdir(), 'check-upstream-originals-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  for (const file of ['config/skills-manifest.json', 'scripts/validate-cross-platform.mjs', 'scripts/upstream-originals.mjs']) {
    mkdirSync(path.dirname(path.join(root, file)), { recursive: true });
    copyFileSync(path.join(repo, file), path.join(root, file));
  }
  for (const name of ['in-your-own-words', 'sharpen']) {
    const relative = path.join('skills', 'core', name);
    cpSync(path.join(repo, relative), path.join(root, relative), { recursive: true });
  }
  return root;
}

function runValidator(root) {
  return spawnSync(process.execPath, [path.join(root, 'scripts/validate-cross-platform.mjs')], { encoding: 'utf8' });
}

test('accepts both pinned pstack originals with their licences', t => {
  const result = runValidator(fixture(t));
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.match(result.stdout, /PASS  in-your-own-words \[upstream original\]/);
  assert.match(result.stdout, /PASS  sharpen \[upstream original\]/);
});

test('reports original and licence changes without rewriting either file', t => {
  const root = fixture(t);
  appendFileSync(path.join(root, 'skills/core/sharpen/SKILL.md'), '\n');
  appendFileSync(path.join(root, 'skills/core/in-your-own-words/LICENSE'), '\n');
  const result = runValidator(root);
  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.match(result.stdout, /SHA-256 mismatch for core\/sharpen\/SKILL\.md/);
  assert.match(result.stdout, /SHA-256 mismatch for core\/in-your-own-words\/LICENSE/);
});

test('a missing pinned skill still fails when discovery skips its directory', t => {
  const root = fixture(t);
  unlinkSync(path.join(root, 'skills/core/sharpen/SKILL.md'));
  const result = runValidator(root);
  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.match(result.stdout, /Missing upstream original core\/sharpen\/SKILL\.md/);
});

test('the exception applies only to the registered path', t => {
  const root = fixture(t);
  const dir = path.join(root, 'skills/core/example');
  mkdirSync(path.join(dir, 'agents'), { recursive: true });
  writeFileSync(path.join(dir, 'SKILL.md'), [
    '---', 'name: example', 'description: Example skill.', 'disable-model-invocation: true', '---', '', 'Body.',
  ].join('\n'));
  const result = runValidator(root);
  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.match(result.stdout, /FAIL  example \[multi-platform\]/);
  assert.match(result.stdout, /Host-specific top-level field "disable-model-invocation"/);
  assert.match(result.stdout, /Missing cross-platform header blockquote/);
  assert.match(result.stdout, /Missing H1 heading/);
});
