import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const source = fileURLToPath(new URL('./playwright_cli.mjs', import.meta.url));

for (const exitCode of [0, 7]) {
  test(`installed CLI runs once and preserves exit ${exitCode}`, () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'playwright local '));
    try {
      const wrapper = path.join(root, 'skills/automation/playwright/scripts/playwright_cli.mjs');
      const cli = path.join(root, 'node_modules/@playwright/cli/playwright-cli.js');
      const calls = path.join(root, 'calls.jsonl');
      fs.mkdirSync(path.dirname(wrapper), { recursive: true });
      fs.mkdirSync(path.dirname(cli), { recursive: true });
      fs.copyFileSync(source, wrapper);
      fs.writeFileSync(cli, `require('fs').appendFileSync(process.env.TEST_CALLS, JSON.stringify(process.argv.slice(2))+'\\n'); console.error('network: target response'); process.exit(${exitCode});`);
      const run = spawnSync(process.execPath, [wrapper, 'snapshot'], {
        env: { ...process.env, PATH: path.join(root, 'no-executables'), PLAYWRIGHT_CLI_SESSION: 'test-session', TEST_CALLS: calls },
        encoding: 'utf8', timeout: 5000,
      });
      assert.equal(run.status, exitCode, run.stderr);
      const rows = fs.readFileSync(calls, 'utf8').trim().split('\n');
      assert.equal(rows.length, 1);
      assert.deepEqual(JSON.parse(rows[0]), ['--session', 'test-session', 'snapshot']);
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });
}

test('explicit short session flag overrides the default session', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'playwright session '));
  try {
    const wrapper = path.join(root, 'skills/automation/playwright/scripts/playwright_cli.mjs');
    const cli = path.join(root, 'node_modules/@playwright/cli/playwright-cli.js');
    fs.mkdirSync(path.dirname(wrapper), { recursive: true });
    fs.mkdirSync(path.dirname(cli), { recursive: true });
    fs.copyFileSync(source, wrapper);
    fs.writeFileSync(cli, 'console.log(JSON.stringify({args:process.argv.slice(2),notifier:process.env.NO_UPDATE_NOTIFIER}));');
    const run = spawnSync(process.execPath, [wrapper, '-s=explicit', 'snapshot'], {
      env: { ...process.env, PLAYWRIGHT_CLI_SESSION: 'default', NO_UPDATE_NOTIFIER: '' },
      encoding: 'utf8', timeout: 5000,
    });
    assert.equal(run.status, 0, run.stderr);
    assert.deepEqual(JSON.parse(run.stdout), { args: ['-s=explicit', 'snapshot'], notifier: '1' });
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('missing installed CLI uses package launcher once', { skip: process.platform === 'win32' }, () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'playwright npx '));
  try {
    const wrapper = path.join(root, 'skills/automation/playwright/scripts/playwright_cli.mjs');
    const bin = path.join(root, 'bin');
    fs.mkdirSync(path.dirname(wrapper), { recursive: true });
    fs.mkdirSync(bin);
    fs.copyFileSync(source, wrapper);
    fs.writeFileSync(path.join(bin, 'npx'), '#!/bin/sh\nprintf "%s\\n" "$@"\n', { mode: 0o755 });
    const run = spawnSync(process.execPath, [wrapper, '--help'], {
      env: { ...process.env, PATH: bin, PLAYWRIGHT_CLI_SESSION: '' }, encoding: 'utf8', timeout: 5000,
    });
    assert.equal(run.status, 0, run.stderr);
    assert.deepEqual(run.stdout.trim().split('\n'), ['--yes', '--package', '@playwright/cli@0.1.17', 'playwright-cli', '--help']);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('target network failure is not misreported as a package installation failure', { skip: process.platform === 'win32' }, () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'playwright target '));
  try {
    const wrapper = path.join(root, 'skills/automation/playwright/scripts/playwright_cli.mjs');
    const bin = path.join(root, 'bin');
    fs.mkdirSync(path.dirname(wrapper), { recursive: true });
    fs.mkdirSync(bin);
    fs.copyFileSync(source, wrapper);
    fs.writeFileSync(path.join(bin, 'npx'), '#!/bin/sh\nprintf "network ETIMEDOUT: target request\\n" >&2\nexit 9\n', { mode: 0o755 });
    const run = spawnSync(process.execPath, [wrapper, 'snapshot'], {
      env: { ...process.env, PATH: bin }, encoding: 'utf8', timeout: 5000,
    });
    assert.equal(run.status, 9);
    assert.match(run.stderr, /target request/);
    assert.doesNotMatch(run.stderr, /npm-deps|CLI unavailable/);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
