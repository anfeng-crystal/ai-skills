import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const scripts = process.env.READINESS_SCRIPT_DIR || path.dirname(fileURLToPath(import.meta.url));

// Replace all network/process effects. The only executable is a disposable fixture.
function run(script, { payload = {}, invalidJson = false, autoLaunch = false, afterSpawn = false } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cdp-ready-test-'));
  const browser = path.join(root, 'fixture-browser');
  const callsPath = path.join(root, 'calls.jsonl');
  const preload = path.join(root, 'preload.mjs');
  fs.writeFileSync(browser, 'fixture; never executed');
  fs.chmodSync(browser, 0o700);
  fs.writeFileSync(preload, `
    import fs from 'node:fs';
    import os from 'node:os';
    import cp from 'node:child_process';
    import { EventEmitter } from 'node:events';
    import { syncBuiltinESMExports } from 'node:module';
    const record = value => fs.appendFileSync(process.env.READINESS_CALLS, JSON.stringify(value)+'\\n');
    os.tmpdir = () => process.env.READINESS_ROOT;
    let spawned = false, identity, terminated = false;
    let now = Date.now();
    Date.now = () => (now += 1000);
    const realTimeout = setTimeout;
    globalThis.setTimeout = (fn, ms, ...args) => realTimeout(fn, Math.min(ms, 1), ...args);
    globalThis.fetch = async url => {
      record({ type: 'fetch', url });
      if (process.env.READINESS_AFTER_SPAWN && !spawned) throw new Error('fixture offline');
      return { ok:true, json:async () => {
        if (process.env.READINESS_INVALID_JSON) throw new SyntaxError('Unexpected token SYNTHETIC_PRIVATE_BODY');
        return JSON.parse(process.env.READINESS_PAYLOAD);
      } };
    };
    cp.spawn = (file, args) => {
      record({ type:'spawn', file, args });
      if (!process.env.READINESS_AFTER_SPAWN) throw new Error('unexpected spawn');
      spawned = true;
      identity = process.platform === 'win32'
        ? JSON.stringify({CreationDate:'fixture',ExecutablePath:file,CommandLine:file+' '+args.join(' ')})
        : 'Mon Oct  5 12:00:00 2026 '+file+' '+args.join(' ');
      const child = new EventEmitter();
      child.pid = 424242; child.exitCode = null; child.signalCode = null;
      child.unref = () => {};
      return child;
    };
    cp.execFileSync = (file, args) => {
      record({ type:'exec', file, args });
      if (!process.env.READINESS_AFTER_SPAWN || !['ps','powershell.exe'].includes(file)) throw new Error('unexpected exec');
      return identity;
    };
    process.kill = (pid, signal) => {
      record({ type:'signal', pid, signal });
      if (terminated) throw Object.assign(new Error('fixture exited'), {code:'ESRCH'});
      if (signal) terminated = true;
      return true;
    };
    const realRm = fs.rmSync;
    fs.rmSync = (target, options) => {
      if (!String(target).startsWith(process.env.READINESS_ROOT + pathSeparator())) throw new Error('removal escaped fixture');
      record({ type:'remove', target }); return realRm(target, options);
    };
    function pathSeparator() { return process.platform === 'win32' ? '\\\\' : '/'; }
    syncBuiltinESMExports();
  `);
  try {
    const args = script === 'check-deps.mjs' ? ['--json', '--strict', '--browser-path', browser, ...(autoLaunch ? ['--auto-launch'] : [])] : [];
    const result = spawnSync(process.execPath, ['--import', preload, path.join(scripts, script), ...args], {
      encoding:'utf8', timeout:6000,
      env:{ ...process.env, NODE_OPTIONS:'', WEB_ACCESS_CDP_HOST:'127.0.0.1', WEB_ACCESS_CDP_PORT:'9222',
        WEB_ACCESS_ALLOW_REMOTE:'', WEB_ACCESS_BROWSER_PATH:browser,
        READINESS_ROOT:root, READINESS_CALLS:callsPath, READINESS_PAYLOAD:JSON.stringify(payload),
        READINESS_INVALID_JSON:invalidJson ? '1' : '', READINESS_AFTER_SPAWN:afterSpawn ? '1' : '',
        BRAVE_SEARCH_API_KEY:'', BRAVE_SEARCH_API_ENDPOINT:'' },
    });
    assert.equal(result.error, undefined);
    assert.equal(result.stderr, '');
    return { ...result, value:JSON.parse(result.stdout),
      calls:fs.existsSync(callsPath) ? fs.readFileSync(callsPath,'utf8').trim().split('\n').map(JSON.parse) : [],
      remainingProfiles:fs.readdirSync(root).filter(name => name.startsWith('web-access-cdp-')) };
  } finally { fs.rmSync(root, {recursive:true, force:true}); }
}

const invalidCases = [
  ['unrelated JSON', { status:'ok' }], ['empty object', {}], ['array', []], ['null', null],
  ['empty websocket', { webSocketDebuggerUrl:'' }], ['number websocket', { webSocketDebuggerUrl:123 }],
  ['invalid URL', { webSocketDebuggerUrl:'not a URL' }],
  ['HTTP URL', { webSocketDebuggerUrl:'http://127.0.0.1:9222/' }],
  ['fragment', { webSocketDebuggerUrl:'ws://127.0.0.1:9222/devtools/browser/id#fragment' }],
  ['invalid JSON', {}, true],
];

for (const [name, payload, invalidJson = false] of invalidCases) {
  for (const script of ['check-deps.mjs', 'cdp-launch.mjs']) {
    test(`${script} rejects ${name} without claiming readiness or starting a browser`, () => {
      const result = run(script, {payload, invalidJson});
      assert.equal(result.status, 2, result.stdout);
      if (script === 'check-deps.mjs') {
        assert.equal(result.value.readyForCdp, false);
        assert.equal(result.value.cdp.reachable, false);
        assert.equal(result.value.cdp.reason, 'invalid_cdp_response');
      } else {
        assert.equal(result.value.ok, false);
        assert.equal(result.value.reason, 'invalid_cdp_response');
      }
      assert.deepEqual(result.calls.map(call => call.type), ['fetch']);
      assert.doesNotMatch(result.stdout, /SYNTHETIC_PRIVATE_BODY/);
    });
  }
}

for (const url of ['ws://127.0.0.1:9222/devtools/browser/id', 'wss://localhost:9222/custom-endpoint']) {
  for (const script of ['check-deps.mjs', 'cdp-launch.mjs']) {
    test(`${script} preserves valid ${new URL(url).protocol} discovery without requiring a product string`, () => {
      const result = run(script, {payload:{webSocketDebuggerUrl:url}});
      assert.equal(result.status, 0, result.stdout);
      if (script === 'check-deps.mjs') {
        assert.equal(result.value.readyForCdp, true);
        assert.equal(result.value.cdp.webSocketUrl, url);
      } else {
        assert.equal(result.value.ok, true);
        assert.equal(result.value.launched, false);
        assert.equal(result.value.webSocketDebuggerUrl, url);
      }
      assert.deepEqual(result.calls.map(call => call.type), ['fetch']);
    });
  }
}

test('auto-launch does not start another browser for a responding non-CDP endpoint', () => {
  const result = run('check-deps.mjs', {payload:{status:'ok'}, autoLaunch:true});
  assert.equal(result.status, 2, result.stdout);
  assert.equal(result.value.cdp.reason, 'invalid_cdp_response');
  assert.equal(result.value.readyForCdp, false);
  assert.deepEqual(result.calls.map(call => call.type), ['fetch']);
  assert.ok(result.value.recommendations.some(line => line.includes('响应无效')));
});

test('launch polling never claims an owned child is ready from an invalid CDP response', () => {
  const result = run('cdp-launch.mjs', {payload:{status:'ok'}, afterSpawn:true});
  assert.equal(result.status, 2, result.stdout);
  assert.equal(result.value.ok, false);
  assert.equal(result.value.reason, 'launch_timeout');
  assert.deepEqual(result.remainingProfiles, []);
  assert.equal(result.calls.filter(call => call.type === 'signal' && call.signal === 'SIGTERM').length, 1);
});

test('launch polling still accepts a valid endpoint and preserves its owned profile', () => {
  const result = run('cdp-launch.mjs', {payload:{webSocketDebuggerUrl:'ws://127.0.0.1:9222/devtools/browser/child'}, afterSpawn:true});
  assert.equal(result.status, 0, result.stdout);
  assert.equal(result.value.launched, true);
  assert.equal(result.remainingProfiles.length, 1);
  assert.equal(result.calls.some(call => call.type === 'signal'), false);
});
