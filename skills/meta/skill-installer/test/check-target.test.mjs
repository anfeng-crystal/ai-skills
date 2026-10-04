import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = process.env.SKILL_INSTALLER_TEST_ROOT || fileURLToPath(new URL('../', import.meta.url));
const cli = path.join(root, 'bin/skill-installer.mjs');
const text = '---\nname: fixture\ndescription: Offline fixture\n---\n';

async function fixture(t, kind, metadata = false) {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), 'check-target-'));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const sourceRoot = path.join(base, 'source');
  const target = path.join(sourceRoot, 'core/target');
  const good = path.join(sourceRoot, 'core/good');
  await fs.mkdir(target, { recursive: true });
  await fs.mkdir(good, { recursive: true });
  await fs.writeFile(path.join(good, 'SKILL.md'), text);
  const entry = path.join(target, 'SKILL.md');
  if (kind === 'directory') await fs.mkdir(entry);
  if (kind === 'regular' || kind === 'read-error' || kind === 'bad-code') await fs.writeFile(entry, text);
  if (kind === 'symlink') await fs.symlink(path.join(good, 'SKILL.md'), entry);
  if (kind === 'broken') await fs.symlink(path.join(base, 'absent'), entry);
  if (metadata) await fs.writeFile(path.join(target, '.skill-meta.json'), JSON.stringify({
    source: { type: 'git', url: 'https://example.invalid/offline' }, lastUpstreamHash: 'old',
  }));
  const preload = path.join(base, 'offline.mjs');
  const activity = path.join(base, 'activity.jsonl');
  await fs.writeFile(preload, `import fs from 'node:fs/promises';
import cp from 'node:child_process';
import { promisify } from 'node:util';
import { syncBuiltinESMExports } from 'node:module';
const activity = ${JSON.stringify(activity)};
const note = async stage => fs.appendFile(activity, JSON.stringify({stage})+'\\n');
const originalStat = fs.stat;
fs.stat = async (file, ...args) => {
  if (String(file) === ${JSON.stringify(entry)} && ${JSON.stringify(['read-error', 'bad-code'].includes(kind))}) {
    throw Object.assign(new Error('PRIVATE_TARGET_VALUE'), {code: ${JSON.stringify(kind === 'bad-code' ? 'PRIVATE_ERROR_VALUE' : 'EACCES')}});
  }
  return originalStat(file, ...args);
};
const originalRead = fs.readFile;
fs.readFile = async (file, ...args) => {
  if (String(file) === ${JSON.stringify(path.join(target, '.skill-meta.json'))}) await note('metadata');
  return originalRead(file, ...args);
};
const stub = () => { throw new Error('unexpected process'); };
stub[promisify.custom] = async () => { await note('upstream'); return { stdout: 'new\\trefs/heads/main\\n' }; };
cp.execFile = stub;
syncBuiltinESMExports();
globalThis.fetch = async () => { await note('fetch'); throw new Error('network forbidden'); };
`);
  return { base, sourceRoot, target, activity, preload };
}

function run(f, flags = [], json = true) {
  const home = path.join(f.base, 'home');
  return spawnSync(process.execPath, ['--import', f.preload, cli, '--check-updates', '--dry-run',
    '--source-root', f.sourceRoot, '--home', home, ...flags, ...(json ? ['--json'] : [])], {
    encoding: 'utf8', env: { ...process.env, HOME: home, USERPROFILE: home, AI_HOST_HOME: home,
      AI_SKILLS_HOME: f.sourceRoot, XDG_CONFIG_HOME: path.join(f.base, 'config'), APPDATA: path.join(f.base, 'config') },
  });
}

for (const kind of ['missing', 'directory', 'broken', 'read-error', 'bad-code']) {
  for (const metadata of [false, true]) {
    test(`invalid target ${kind}, metadata=${metadata} fails before metadata or upstream`, async t => {
      const f = await fixture(t, kind, metadata);
      const r = run(f, ['--skill', 'core/target']);
      assert.equal(r.status, 2, r.stderr);
      const report = JSON.parse(r.stdout);
      assert.equal(report.ok, false);
      assert.equal(report.skills['core/target'].status, 'check_failed');
      assert.equal(report.summary.failed, 1);
      assert.equal(report.summary.noSource, 0);
      assert.doesNotMatch(r.stdout + r.stderr, /PRIVATE_/);
      assert.equal(await fs.readFile(f.activity, 'utf8').catch(e => e.code === 'ENOENT' ? '' : Promise.reject(e)), '');
    });
  }
}

for (const kind of ['regular', 'symlink']) {
  test(`valid ${kind} without metadata remains no_source`, async t => {
    const f = await fixture(t, kind);
    const r = run(f, ['--skill', 'core/target']);
    const report = JSON.parse(r.stdout);
    assert.equal(r.status, 0, r.stderr);
    assert.equal(report.ok, true);
    assert.equal(report.skills['core/target'].status, 'no_source');
    assert.equal(report.summary.noSource, 1);
  });
}

test('valid git target still reaches upstream without writing metadata during dry-run', async t => {
  const f = await fixture(t, 'regular', true);
  const meta = path.join(f.target, '.skill-meta.json');
  const before = await fs.readFile(meta, 'utf8');
  const r = run(f, ['--skill', 'core/target']);
  assert.equal(r.status, 0, r.stderr);
  assert.equal(JSON.parse(r.stdout).skills['core/target'].status, 'updatable');
  assert.equal(await fs.readFile(meta, 'utf8'), before);
  assert.match(await fs.readFile(f.activity, 'utf8'), /upstream/);
});

for (const filtered of [false, true]) {
  test(`batch continues valid targets and preserves failed result, filtered=${filtered}`, async t => {
    const f = await fixture(t, 'directory');
    const r = run(f, ['--skill', 'core/target,core/good', ...(filtered ? ['--only-updatable'] : [])]);
    const report = JSON.parse(r.stdout);
    assert.equal(r.status, 2, r.stderr);
    assert.equal(report.summary.total, 2);
    assert.equal(report.summary.failed, 1);
    assert.equal(report.summary.noSource, 1);
    assert.equal((filtered ? report.checkErrors : report.skills)['core/target'].status, 'check_failed');
    if (filtered) assert.deepEqual(report.skills, {});
    else assert.equal(report.skills['core/good'].status, 'no_source');
  });
}

test('text identifies invalid target and subsequent successful target', async t => {
  const f = await fixture(t, 'missing');
  const r = run(f, ['--skill', 'core/target,core/good'], false);
  assert.equal(r.status, 2, r.stderr);
  assert.match(r.stdout, /core\/target: check_failed/);
  assert.match(r.stdout, /core\/good: no_source/);
});

test('default discovery still excludes invalid entries', async t => {
  const f = await fixture(t, 'directory');
  const r = run(f);
  assert.equal(r.status, 0, r.stderr);
  const report = JSON.parse(r.stdout);
  assert.deepEqual(Object.keys(report.skills), ['core/good']);
});
