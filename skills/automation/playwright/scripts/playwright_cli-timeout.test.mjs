import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const source = process.env.PLAYWRIGHT_WRAPPER_TEST_SOURCE
  || fileURLToPath(new URL('./playwright_cli.mjs', import.meta.url));
const fixtureSource = `
const fs = require('node:fs');
fs.writeFileSync(process.env.TEST_PID, String(process.pid));
fs.appendFileSync(process.env.TEST_CALLS, JSON.stringify(process.argv.slice(2)) + '\\n');
const mode = process.env.TEST_MODE;
if (mode === 'ignore' || mode === 'graceful') {
  process.on('SIGTERM', () => {
    fs.appendFileSync(process.env.TEST_TERMS, 'term\\n');
    if (mode === 'graceful') process.exit(0);
  });
  setInterval(() => {}, 100);
} else if (mode === 'signal') {
  process.kill(process.pid, 'SIGTERM');
} else {
  setTimeout(() => process.exit(Number(process.env.TEST_EXIT_CODE)), 120);
}
`;

function killOwnedChild(pidFile) {
  if (!fs.existsSync(pidFile)) return;
  const pid = Number(fs.readFileSync(pidFile, 'utf8'));
  if (!Number.isSafeInteger(pid) || pid <= 0) return;
  try { process.kill(pid, 'SIGKILL'); } catch (error) {
    if (error.code !== 'ESRCH') throw error;
  }
}

async function runFixture({ route = 'local', mode = 'exit', timeout = '', args = ['snapshot'], exitCode = 0 } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'playwright timeout '));
  const wrapper = path.join(root, 'skills/automation/playwright/scripts/playwright_cli.mjs');
  const cli = path.join(root, route === 'local' ? 'node_modules/@playwright/cli/playwright-cli.js' : 'fixture.cjs');
  const bin = path.join(root, 'bin');
  const pidFile = path.join(root, 'pid');
  const callsFile = path.join(root, 'calls.jsonl');
  const termsFile = path.join(root, 'terms');
  let proc;
  let watchdog;
  let closed;
  try {
    fs.mkdirSync(path.dirname(wrapper), { recursive: true });
    fs.mkdirSync(path.dirname(cli), { recursive: true });
    fs.mkdirSync(bin);
    fs.copyFileSync(source, wrapper);
    fs.writeFileSync(cli, fixtureSource);
    if (route === 'npx') {
      const quote = (value) => `'${value.replaceAll("'", "'\\''")}'`;
      fs.writeFileSync(path.join(bin, 'npx'), `#!/bin/sh\nexec ${quote(process.execPath)} ${quote(cli)} "$@"\n`, { mode: 0o755 });
    }
    const start = performance.now();
    proc = spawn(process.execPath, [wrapper, ...args], {
      env: {
        ...process.env, PATH: bin,
        PLAYWRIGHT_CLI_TIMEOUT_MS: timeout,
        PLAYWRIGHT_CLI_SESSION: 'timeout-session',
        TEST_PID: pidFile, TEST_CALLS: callsFile, TEST_TERMS: termsFile,
        TEST_MODE: mode, TEST_EXIT_CODE: String(exitCode),
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    let supervised = false;
    proc.stdout.on('data', (chunk) => { stdout += chunk; });
    proc.stderr.on('data', (chunk) => { stderr += chunk; });
    closed = new Promise((resolve, reject) => {
      proc.once('error', reject);
      proc.once('close', (code, signal) => resolve({ code, signal }));
    });
    // Old implementations that never settle must not leave fixture processes behind.
    watchdog = setTimeout(() => {
      supervised = true;
      killOwnedChild(pidFile);
      proc.kill('SIGKILL');
    }, 2800);
    const result = await closed;
    clearTimeout(watchdog);
    return {
      ...result, stdout, stderr, supervised, elapsedMs: performance.now() - start,
      calls: fs.existsSync(callsFile) ? fs.readFileSync(callsFile, 'utf8').trim().split('\n').map(JSON.parse) : [],
      terms: fs.existsSync(termsFile) ? fs.readFileSync(termsFile, 'utf8').trim().split('\n') : [],
    };
  } finally {
    clearTimeout(watchdog);
    if (proc && proc.exitCode === null && proc.signalCode === null) {
      killOwnedChild(pidFile);
      proc.kill('SIGKILL');
      await closed?.catch(() => {});
    }
    fs.rmSync(root, { recursive: true, force: true });
  }
}

const posixOnly = { skip: process.platform === 'win32' };

test('local CLI ignoring SIGTERM still finishes timeout once with exit 124', posixOnly, async () => {
  const result = await runFixture({ mode: 'ignore', timeout: '500' });
  assert.equal(result.supervised, false, 'wrapper required external cleanup after ignoring SIGTERM');
  assert.equal(result.code, 124);
  assert.equal(result.signal, null);
  assert.deepEqual(result.terms, ['term']);
  assert.deepEqual(result.calls, [['--session', 'timeout-session', 'snapshot']]);
  assert.doesNotMatch(result.stderr, /CLI unavailable/);
});

for (const command of ['snapshot', '--help']) {
  test(`package launcher ignoring SIGTERM finishes ${command} with exit 124`, posixOnly, async () => {
    const result = await runFixture({ route: 'npx', mode: 'ignore', timeout: '500', args: [command] });
    assert.equal(result.supervised, false, 'wrapper required external cleanup after ignoring SIGTERM');
    assert.equal(result.code, 124);
    assert.equal(result.signal, null);
    assert.deepEqual(result.terms, ['term']);
    assert.deepEqual(result.calls, [['--yes', '--package', '@playwright/cli@0.1.17', 'playwright-cli', '--session', 'timeout-session', command]]);
    if (command === '--help') assert.match(result.stderr, /CLI unavailable/);
    else assert.doesNotMatch(result.stderr, /CLI unavailable/);
  });
}

test('CLI gets a graceful termination opportunity and timeout stays 124 after exit 0', posixOnly, async () => {
  const result = await runFixture({ mode: 'graceful', timeout: '500' });
  assert.equal(result.supervised, false);
  assert.equal(result.code, 124);
  assert.deepEqual(result.terms, ['term']);
  assert.equal(result.calls.length, 1);
  assert.ok(result.elapsedMs < 1400, `graceful exit retained an escalation timer: ${result.elapsedMs}`);
});

for (const timeout of ['', '0', '-1']) {
  test(`non-help CLI with timeout ${JSON.stringify(timeout)} preserves a later exit 7`, async () => {
    const result = await runFixture({ timeout, exitCode: 7 });
    assert.equal(result.supervised, false);
    assert.equal(result.code, 7);
    assert.equal(result.signal, null);
    assert.deepEqual(result.terms, []);
    assert.equal(result.calls.length, 1);
  });
}

test('normal child exit clears the deadline without escalation', async () => {
  const result = await runFixture({ timeout: '2000' });
  assert.equal(result.supervised, false);
  assert.equal(result.code, 0);
  assert.equal(result.calls.length, 1);
  assert.ok(result.elapsedMs < 1400, `normal exit retained a deadline: ${result.elapsedMs}`);
});

test('normal child SIGTERM is preserved as a signal rather than timeout status', posixOnly, async () => {
  const result = await runFixture({ mode: 'signal', timeout: '2000' });
  assert.equal(result.supervised, false);
  assert.equal(result.code, null);
  assert.equal(result.signal, 'SIGTERM');
  assert.equal(result.calls.length, 1);
});

test('missing launcher reports resolution failure and clears pending deadline', async () => {
  const result = await runFixture({ route: 'missing', timeout: '2000' });
  assert.equal(result.supervised, false);
  assert.equal(result.code, 1);
  assert.deepEqual(result.calls, []);
  assert.match(result.stderr, /CLI unavailable/);
  assert.ok(result.elapsedMs < 1400, `spawn failure retained a deadline: ${result.elapsedMs}`);
});
