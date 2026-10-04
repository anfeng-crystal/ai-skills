import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const inspector = process.env.SKILL_VETTER_SCRIPT || fileURLToPath(new URL('./inspect-skill.mjs', import.meta.url));

function inspect(t, body, options = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'vetter-frontmatter-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  let entry = `---\n${body}\n---\n`;
  if (options.crlf) entry = entry.replace(/\n/g, '\r\n');
  fs.writeFileSync(path.join(root, 'SKILL.md'), entry);
  const run = spawnSync(process.execPath, [inspector, '--path', root, '--json', '--strict'], {
    encoding: 'utf8', timeout: 5000,
  });
  assert.ok([0, 2].includes(run.status), run.stderr);
  return { ...run, report: JSON.parse(run.stdout) };
}

for (const [name, body, missing] of [
  ['empty name before another field', 'name:\ndescription: Demo', 'name'],
  ['empty description before another field', 'name: demo\ndescription:\nversion: 1', 'description'],
  ['whitespace name before another field', 'name: \t \ndescription: Demo', 'name'],
  ['whitespace description at end', 'name: demo\ndescription: \t ', 'description'],
  ['double-quoted empty name', 'name: ""\ndescription: Demo', 'name'],
  ['single-quoted empty name', "name: ''\ndescription: Demo", 'name'],
  ['double-quoted empty description', 'name: demo\ndescription: ""', 'description'],
  ['single-quoted empty description', "name: demo\ndescription: ''", 'description'],
  ['quoted whitespace name', 'name: "  \t  "\ndescription: Demo', 'name'],
  ['quoted whitespace description', "name: demo\ndescription: '   '", 'description'],
  ['missing name', 'description: Demo', 'name'],
]) {
  test(`${name} cannot pass the strict structure gate`, (t) => {
    const { status, report } = inspect(t, body);
    assert.equal(status, 2);
    assert.equal(report.recommendation, 'review_needed');
    assert.equal(report.frontmatter[missing], null);
    assert.ok(report.findings.some((finding) => finding.category === 'skill_structure' && finding.match === missing));
  });
}

test('both empty values remain separate and both structure findings are retained under CRLF', (t) => {
  const { status, report } = inspect(t, 'name: \ndescription: \nversion: 1', { crlf: true });
  assert.equal(status, 2);
  assert.deepEqual(report.frontmatter, { hasFrontmatter: true, name: null, description: null });
  assert.deepEqual(report.findings.filter((finding) => finding.category === 'skill_structure').map((finding) => finding.match).sort(), ['description', 'name']);
});

for (const [name, body, expected, options] of [
  ['plain scalars', 'name: demo\ndescription: Demo description', { name: 'demo', description: 'Demo description' }],
  ['double-quoted scalars', 'name: "demo"\ndescription: "Demo: 中文描述"', { name: 'demo', description: 'Demo: 中文描述' }],
  ['single-quoted scalars', "name: 'demo'\ndescription: 'Demo description'", { name: 'demo', description: 'Demo description' }],
  ['CRLF with spacing', 'name:   demo  \ndescription:\t Demo description  ', { name: 'demo', description: 'Demo description' }, { crlf: true }],
  ['an internal apostrophe', "name: demo\ndescription: A developer's helper", { name: 'demo', description: "A developer's helper" }],
]) {
  test(`${name} keep valid frontmatter and allow`, (t) => {
    const { status, report } = inspect(t, body, options);
    assert.equal(status, 0);
    assert.equal(report.recommendation, 'allow');
    assert.deepEqual(report.frontmatter, { hasFrontmatter: true, ...expected });
    assert.deepEqual(report.findings, []);
  });
}

test('quoted frontmatter retains credential redaction', (t) => {
  const { status, report, stdout, stderr } = inspect(t, 'name: demo\ndescription: "API_KEY=FAKE_FRONTMATTER_VALUE"');
  assert.equal(status, 2);
  assert.equal(report.recommendation, 'review_needed');
  assert.equal(report.frontmatter.description, '[REDACTED_CREDENTIAL_CONTEXT]');
  assert.doesNotMatch(stdout + stderr, /FAKE_FRONTMATTER_VALUE/);
  assert.ok(report.secretHits.includes('SKILL.md:3'));
});
