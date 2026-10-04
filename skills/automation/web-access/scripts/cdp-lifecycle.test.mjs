import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const source = fileURLToPath(new URL('.', import.meta.url));
const identity = 'Mon Oct  5 12:00:00 2026 fixture-browser --user-data-dir=fixture';
const markerName = '.web-access-owner.json';

// All browser/network/process effects are replaced before importing either CLI.
// Only disposable files under this fixture root can be removed.
function run(script, args, { mode = 'reachable', fixtures = {}, launchStub = false, env = {}, setup } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'web cdp 测试 '));
  const temp = path.join(root, 'tmp');
  const calls = path.join(root, 'calls.jsonl');
  const browser = path.join(root, 'browser fixture');
  fs.mkdirSync(temp);
  fs.writeFileSync(browser, 'fixture');
  fs.chmodSync(browser, 0o700);
  for (const [name, marker] of Object.entries(fixtures)) {
    fs.mkdirSync(path.join(temp, name));
    if (marker !== null) fs.writeFileSync(path.join(temp, name, markerName), JSON.stringify(marker));
  }
  setup?.(root, temp);
  for (const name of fs.readdirSync(source).filter(name => name.endsWith('.mjs') && !name.endsWith('.test.mjs'))) {
    fs.copyFileSync(path.join(source, name), path.join(root, name));
  }
  if (launchStub) {
    fs.writeFileSync(path.join(root, 'cdp-launch.mjs'), `
      import fs from 'node:fs';
      fs.appendFileSync(process.env.TEST_CALLS, JSON.stringify({type:'launch', args:process.argv.slice(2), host:process.env.WEB_ACCESS_CDP_HOST, port:process.env.WEB_ACCESS_CDP_PORT, browser:process.env.WEB_ACCESS_BROWSER_PATH})+'\\n');
      if (process.env.TEST_LAUNCH_FAILURE) { console.log(process.env.TEST_LAUNCH_FAILURE); process.exit(2); }
      console.log(JSON.stringify({ok:true, launched:true, host:process.env.WEB_ACCESS_CDP_HOST, port:Number(process.env.WEB_ACCESS_CDP_PORT), browser:'fixture', pid:424242, tmpDir:'fixture-owned'}));
    `);
  }
  const preload = path.join(root, 'preload.mjs');
  fs.writeFileSync(preload, `
    import fs from 'node:fs';
    import os from 'node:os';
    import cp from 'node:child_process';
    import { EventEmitter } from 'node:events';
    import { syncBuiltinESMExports } from 'node:module';
    const record = value => fs.appendFileSync(process.env.TEST_CALLS, JSON.stringify(value)+'\\n');
    const mode = process.env.TEST_MODE;
    if (mode === 'timeout') {
      let now = Date.now();
      Date.now = () => (now += 1000);
      const realTimeout = globalThis.setTimeout;
      globalThis.setTimeout = (fn, ms, ...args) => realTimeout(fn, Math.min(ms, 1), ...args);
    }
    const realRm = fs.rmSync;
    fs.rmSync = (target, options) => {
      if (!String(target).startsWith(process.env.TEST_TMP + '/')) throw new Error('Unsafe removal escaped fixture');
      record({type:'remove', target}); return realRm(target, options);
    };
    os.tmpdir = () => process.env.TEST_TMP;
    let spawned = false;
    let spawnIdentity;
    let child;
    let spawnedFetches = 0;
    let terminated = false;
    process.kill = (pid, signal) => {
      record({type:'signal', pid, signal});
      if (mode === 'permission-error') throw Object.assign(new Error('Permission denied'), {code:'EPERM'});
      if (mode === 'gone' || (terminated && mode !== 'survives')) throw Object.assign(new Error('No such process'), {code:'ESRCH'});
      if (signal !== 0) terminated = true;
      return true;
    };
    const realExec = cp.execFileSync;
    cp.execFileSync = (file, args, options) => {
      if (file === 'ps' || file === 'powershell.exe') {
        record({type:'identity', file, args});
        if (mode === 'identity-error') throw new Error('Process identity unavailable');
        if (mode === 'initial-wrong-browser') return 'Mon Oct  5 12:00:00 2026 /usr/bin/unrelated-worker --user-data-dir='+spawnIdentity.split(' --user-data-dir=')[1];
        if (mode === 'initial-wrong-profile') return spawnIdentity.replace('--user-data-dir=', '--other-dir=');
        if (mode === 'initial-malformed') return 'unparseable '+spawnIdentity;
        if (spawnIdentity) return spawnIdentity;
        return mode === 'reused' ? 'different-process-identity' : process.env.TEST_IDENTITY;
      }
      return realExec(file, args, options);
    };
    cp.spawn = (file, args) => {
      record({type:'spawn', file, args}); spawned = true;
      child = new EventEmitter();
      child.pid = 424242;
      child.exitCode = null;
      child.signalCode = null;
      spawnIdentity = 'Mon Oct  5 12:00:00 2026 '+file+' '+args.join(' ');
      child.unref = () => record({type:'unref'});
      child.kill = signal => process.kill(child.pid, signal);
      if (mode === 'spawn-error') { child.pid = undefined; queueMicrotask(() => child.emit('error', new Error('spawn EACCES'))); }
      if (mode === 'child-exited-code') child.exitCode = 1;
      if (mode === 'child-exited-signal') child.signalCode = 'SIGTERM';
      if (mode === 'child-exit-event') queueMicrotask(() => child.emit('exit', 1));
      return child;
    };
    globalThis.fetch = async url => {
      record({type:'fetch', url});
      if (spawned) spawnedFetches++;
      if (mode === 'exit-after-owner' && spawnedFetches > 1) queueMicrotask(() => { child.exitCode = 1; child.emit('exit', 1); });
      const ready = spawned && (mode === 'launch' || mode.startsWith('initial-') || mode.startsWith('child-') || (mode === 'exit-after-owner' && spawnedFetches > 1));
      if (mode !== 'reachable' && !ready) throw new Error('Fixture endpoint unavailable');
      return {ok:true, json:async()=>({webSocketDebuggerUrl:'ws://fixture/devtools/browser/owned', Browser:'fixture'})};
    };
    syncBuiltinESMExports();
  `);
  try {
    const argsWithBrowser = args.map(arg => arg === '<browser>' ? browser : arg);
    const result = spawnSync(process.execPath, ['--import', preload, path.join(root, script), ...argsWithBrowser], {
      env: { ...process.env, WEB_ACCESS_CDP_HOST: '127.0.0.1', WEB_ACCESS_CDP_PORT: '9222',
        WEB_ACCESS_BROWSER_PATH: browser, WEB_ACCESS_ALLOW_REMOTE: '', NODE_OPTIONS: '', TEST_LAUNCH_FAILURE: '',
        TEST_TMP: temp, TEST_CALLS: calls, TEST_MODE: mode, TEST_IDENTITY: identity, ...env },
      encoding: 'utf8', timeout: 6000,
    });
    const remaining = fs.readdirSync(temp);
    const markers = remaining.filter(name => fs.existsSync(path.join(temp, name, markerName)))
      .map(name => JSON.parse(fs.readFileSync(path.join(temp, name, markerName), 'utf8')));
    return { ...result, remaining, markers, browser,
      calls: fs.existsSync(calls) ? fs.readFileSync(calls, 'utf8').trim().split('\n').map(JSON.parse) : [],
    };
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
}

const owner = { version: 1, pid: 424242, identity };
const dangerous = result => result.calls.filter(call => call.type === 'remove' || (call.type === 'signal' && call.signal !== 0));

test('launcher help makes no browser, process or network calls', () => {
  const result = run('cdp-launch.mjs', ['--help']);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Usage:/);
  assert.deepEqual(result.calls, []);
});

for (const args of [['--kill'], ['--kill', '0'], ['--kill', '-1'], ['--kill', '1.5'], ['--kill', 'nope'], ['--wat']]) {
  test(`launcher rejects unsafe arguments: ${args.join(' ')}`, () => {
    const result = run('cdp-launch.mjs', args, { fixtures: { 'web-access-cdp-unowned': null } });
    assert.equal(result.status, 1, result.stderr);
    assert.deepEqual(result.calls, []);
    assert.deepEqual(result.remaining, ['web-access-cdp-unowned']);
  });
}

test('kill refuses unowned and legacy profiles without signaling arbitrary PID', () => {
  const result = run('cdp-launch.mjs', ['--kill', '424242'], { fixtures: { 'web-access-cdp-legacy': null } });
  assert.equal(result.status, 2, result.stderr);
  assert.deepEqual(dangerous(result), []);
  assert.deepEqual(result.remaining, ['web-access-cdp-legacy']);
});

test('kill removes only the uniquely owned profile after verified termination', () => {
  const result = run('cdp-launch.mjs', ['--kill', '424242'], { fixtures: {
    'web-access-cdp-owned': owner, 'web-access-cdp-other': { ...owner, pid: 424243 }, 'web-access-cdp-legacy': null,
  } });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(result.remaining, ['web-access-cdp-legacy', 'web-access-cdp-other']);
  assert.deepEqual(result.calls.filter(call => call.type === 'signal' && call.signal !== 0).map(call => call.pid), [424242]);
});

for (const mode of ['reused', 'identity-error', 'permission-error', 'survives']) {
  test(`kill preserves owned profile when termination cannot be confirmed: ${mode}`, () => {
    const result = run('cdp-launch.mjs', ['--kill', '424242'], { mode, fixtures: { 'web-access-cdp-owned': owner } });
    assert.equal(result.status, 2, result.stderr);
    assert.deepEqual(result.remaining, ['web-access-cdp-owned']);
    assert.equal(result.calls.some(call => call.type === 'remove'), false);
    if (mode !== 'survives') assert.deepEqual(dangerous(result), []);
  });
}

test('kill refuses duplicate ownership records', () => {
  const result = run('cdp-launch.mjs', ['--kill', '424242'], { fixtures: { 'web-access-cdp-a': owner, 'web-access-cdp-b': owner } });
  assert.equal(result.status, 2, result.stderr);
  assert.deepEqual(dangerous(result), []);
  assert.equal(result.remaining.length, 2);
});

test('kill refuses symlinked profiles and markers', () => {
  const result = run('cdp-launch.mjs', ['--kill', '424242'], {
    fixtures: { 'web-access-cdp-marker-link': null },
    setup(root, temp) {
      const outside = path.join(root, 'other-profile');
      fs.mkdirSync(outside);
      fs.writeFileSync(path.join(outside, markerName), JSON.stringify(owner));
      fs.symlinkSync(outside, path.join(temp, 'web-access-cdp-dir-link'), 'dir');
      fs.symlinkSync(path.join(outside, markerName), path.join(temp, 'web-access-cdp-marker-link', markerName), 'file');
    },
  });
  assert.equal(result.status, 2, result.stderr);
  assert.deepEqual(dangerous(result), []);
  assert.equal(result.remaining.length, 2);
});

test('kill can clean a confirmed exited owned process without sending SIGTERM', () => {
  const result = run('cdp-launch.mjs', ['--kill', '424242'], { mode: 'gone', fixtures: { 'web-access-cdp-owned': owner } });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(result.remaining, []);
  assert.equal(result.calls.some(call => call.type === 'signal' && call.signal !== 0), false);
});

test('launch records process identity and detaches only after successful launch', () => {
  const result = run('cdp-launch.mjs', [], { mode: 'launch' });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).launched, true);
  assert.equal(result.markers.length, 1);
  assert.equal(result.markers[0].pid, 424242);
  assert.ok(result.markers[0].identity.includes(result.browser));
  assert.ok(result.markers[0].identity.includes(JSON.parse(result.stdout).tmpDir));
  assert.equal(result.calls.filter(call => call.type === 'unref').length, 1);
});

for (const mode of ['child-exited-code', 'child-exited-signal', 'child-exit-event', 'exit-after-owner']) {
  test(`launch never claims a ready endpoint after its child exited: ${mode}`, () => {
    const result = run('cdp-launch.mjs', [], { mode });
    assert.equal(result.status, 2, result.stderr);
    assert.equal(JSON.parse(result.stdout).reason, 'launch_exited');
    assert.deepEqual(dangerous(result), []);
    if (mode !== 'exit-after-owner') assert.deepEqual(result.markers, []);
  });
}

for (const mode of ['initial-wrong-browser', 'initial-wrong-profile', 'initial-malformed']) {
  test(`launch cannot record an unrelated initial process identity: ${mode}`, () => {
    const result = run('cdp-launch.mjs', [], { mode });
    assert.equal(result.status, 2, result.stderr);
    assert.equal(JSON.parse(result.stdout).reason, 'process_identity_unavailable');
    assert.deepEqual(result.markers, []);
    assert.deepEqual(dangerous(result), []);
  });
}

test('spawn failure is reported and only its new profile is removed', () => {
  const result = run('cdp-launch.mjs', [], { mode: 'spawn-error', fixtures: { 'web-access-cdp-legacy': null } });
  assert.equal(result.status, 2, result.stderr);
  assert.equal(JSON.parse(result.stdout).reason, 'spawn_failed');
  assert.deepEqual(result.remaining, ['web-access-cdp-legacy']);
});

test('launch preserves new profile and reports PID if identity cannot be established', () => {
  const result = run('cdp-launch.mjs', [], { mode: 'identity-error' });
  assert.equal(result.status, 2, result.stderr);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.reason, 'process_identity_unavailable');
  assert.equal(payload.pid, 424242);
  assert.equal(result.remaining.length, 1);
  assert.deepEqual(dangerous(result), []);
});

test('launch timeout stops only its owned child and preserves legacy profiles', () => {
  const result = run('cdp-launch.mjs', [], { mode: 'timeout', fixtures: { 'web-access-cdp-legacy': null } });
  assert.equal(result.status, 2, result.stderr);
  assert.equal(JSON.parse(result.stdout).reason, 'launch_timeout');
  assert.deepEqual(result.remaining, ['web-access-cdp-legacy']);
  assert.deepEqual(result.calls.filter(call => call.type === 'signal' && call.signal !== 0).map(call => call.pid), [424242]);
});

test('launcher rejects remote endpoint without opt-in before probing or launching', () => {
  const result = run('cdp-launch.mjs', [], { env: { WEB_ACCESS_CDP_HOST: 'remote.example' } });
  assert.equal(result.status, 2, result.stderr);
  assert.equal(JSON.parse(result.stdout).reason, 'remote_host_blocked');
  assert.deepEqual(result.calls, []);
});

for (const args of [['--host'], ['--host', '--json'], ['--port'], ['--port', '0'], ['--port', '65536'], ['--port', '1.5'], ['--port', 'NaN'], ['--browser-path'], ['--browser-path', '--json']]) {
  test(`preflight rejects malformed arguments before checks: ${args.join(' ')}`, () => {
    const result = run('check-deps.mjs', [...args, '--dry-run']);
    assert.equal(result.status, 1, result.stderr);
    assert.deepEqual(result.calls, []);
  });
}

test('auto-launch propagates selected endpoint and executable from a Unicode path', () => {
  const result = run('check-deps.mjs', ['--json', '--auto-launch', '--host', 'localhost', '--port', '9333', '--browser-path', '<browser>'], { mode: 'offline', launchStub: true });
  assert.equal(result.status, 0, result.stderr);
  const launch = result.calls.find(call => call.type === 'launch');
  assert.ok(launch, result.stdout);
  assert.equal(launch.host, 'localhost');
  assert.equal(launch.port, '9333');
  assert.equal(launch.browser, result.browser);
  assert.equal(JSON.parse(result.stdout).cdp.port, 9333);
});

test('remote preflight does not auto-launch a local browser even with opt-in', () => {
  const result = run('check-deps.mjs', ['--json', '--auto-launch', '--strict', '--host', 'remote.example'], { mode: 'offline', launchStub: true, env: { WEB_ACCESS_ALLOW_REMOTE: '1' } });
  assert.equal(result.status, 2, result.stderr);
  assert.equal(result.calls.some(call => call.type === 'launch'), false);
});

test('preflight reports launch failure and preserves cleanup evidence', () => {
  const result = run('check-deps.mjs', ['--json', '--auto-launch', '--strict'], {
    mode: 'offline', launchStub: true,
    env: { TEST_LAUNCH_FAILURE: JSON.stringify({ ok: false, reason: 'launch_timeout', cleanupError: 'termination_pending', pid: 424242, tmpDir: 'fixture-owned' }) },
  });
  assert.equal(result.status, 2, result.stderr);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.readyForCdp, false);
  assert.equal(payload.cdp.launchFailure.cleanupError, 'termination_pending');
  assert.equal(payload.cdp.launchFailure.tmpDir, 'fixture-owned');
  assert.match(payload.recommendations.at(-1), /launch_timeout/);
});

test('IPv6 loopback uses a valid bracketed CDP URL', () => {
  const result = run('check-deps.mjs', ['--json', '--host', '::1']);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.calls.find(call => call.type === 'fetch').url, 'http://[::1]:9222/json/version');
});
