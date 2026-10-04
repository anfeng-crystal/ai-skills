#!/usr/bin/env node
/** Probe CDP, launch an isolated local browser when needed, or stop one owned instance. */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { allowRemoteHost, localHost, validateEndpoint, versionUrl, detectBrowserPath, optionValue } from './cdp-environment.mjs';
import { findOwnedProfile, saveOwner, stopOwned, sleep } from './cdp-ownership.mjs';
import { readCdpVersion } from './cdp-response.mjs';

function printHelp() {
  console.log(`Usage:
  node scripts/cdp-launch.mjs
  node scripts/cdp-launch.mjs --kill <pid>

Uses WEB_ACCESS_CDP_HOST, WEB_ACCESS_CDP_PORT and WEB_ACCESS_BROWSER_PATH.
--kill stops only one uniquely recorded instance after checking its process identity.
Legacy/unowned profiles and profiles with uncertain termination are preserved.
--help shows this help without probing or launching.`);
}

function parseArgs(args) {
  if (args.length === 1 && ['--help', '-h'].includes(args[0])) return { help: true };
  if (args[0] === '--kill') {
    const value = optionValue(args, 1, '--kill');
    const pid = Number(value);
    if (args.length !== 2 || !/^\d+$/.test(value) || !Number.isSafeInteger(pid) || pid < 1 || pid > 2147483647) {
      throw new Error('--kill requires one positive process ID');
    }
    return { pid };
  }
  if (args.length) throw new Error(`Unknown argument: ${args[0]}`);
  const host = process.env.WEB_ACCESS_CDP_HOST || '127.0.0.1';
  const port = Number(process.env.WEB_ACCESS_CDP_PORT || '9222');
  validateEndpoint(host, port);
  return { host, port };
}

async function probe(host, port) {
  try {
    const response = await fetch(versionUrl(host, port), { signal: AbortSignal.timeout(1500) });
    if (!response.ok) return { ok: false };
    return await readCdpVersion(response);
  } catch { return { ok: false }; }
}

async function launch({ host, port }) {
  if (!allowRemoteHost(host)) return { ok: false, reason: 'remote_host_blocked' };
  const existing = await probe(host, port);
  if (existing.ok) {
    return { ok: true, launched: false, host, port, webSocketDebuggerUrl: existing.ws, browser: existing.browser, pid: null, tmpDir: null };
  }
  // A responding non-CDP service already occupies this endpoint; do not launch over it.
  if (existing.reason === 'invalid_cdp_response') return { ...existing, host, port };
  // A local child cannot bring a remote CDP endpoint online.
  if (!localHost(host)) return { ok: false, reason: 'remote_launch_unsupported', host, port };
  const browser = detectBrowserPath();
  if (!browser) return { ok: false, reason: 'browser_not_found' };

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'web-access-cdp-'));
  let proc;
  try {
    proc = spawn(browser, [
      `--remote-debugging-port=${port}`, `--user-data-dir=${tmpDir}`,
      '--no-first-run', '--no-default-browser-check', '--headless=new',
      '--disable-gpu', '--disable-dev-shm-usage', '--no-sandbox', 'about:blank',
    ], { detached: true, stdio: ['ignore', 'ignore', 'ignore'] });
  } catch (error) {
    fs.rmSync(tmpDir, { recursive: true, force: true });
    return { ok: false, reason: 'spawn_failed', detail: error.message };
  }
  let spawnError;
  let exited = false;
  proc.on('error', error => { spawnError = error; });
  proc.on('exit', () => { exited = true; });
  const childExited = () => exited || proc.exitCode != null || proc.signalCode != null;
  const exitedResult = () => ({ ok: false, reason: 'launch_exited', pid: proc.pid, tmpDir,
    exitCode: proc.exitCode ?? null, signalCode: proc.signalCode ?? null });
  // Detached children otherwise keep the launcher (and synchronous preflight) alive.
  proc.unref();
  let owner;
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    if (childExited()) return exitedResult();
    const status = await probe(host, port);
    if (spawnError) {
      fs.rmSync(tmpDir, { recursive: true, force: true });
      return { ok: false, reason: 'spawn_failed', detail: spawnError.message };
    }
    if (childExited()) return exitedResult();
    if (!owner && proc.pid) {
      try { owner = saveOwner(tmpDir, proc.pid, browser); }
      catch (error) {
        return { ok: false, reason: 'process_identity_unavailable', detail: error.message, pid: proc.pid, tmpDir };
      }
    }
    // Let pending child exit events run before claiming ownership of a ready endpoint.
    await new Promise(resolve => setImmediate(resolve));
    if (childExited()) return exitedResult();
    if (status.ok && owner) {
      return { ok: true, launched: true, host, port, webSocketDebuggerUrl: status.ws, browser: status.browser, pid: proc.pid, tmpDir };
    }
    await sleep(300);
  }
  try {
    if (!owner) throw new Error('process_identity_unavailable');
    await stopOwned({ tmpDir, owner });
    return { ok: false, reason: 'launch_timeout' };
  } catch (error) {
    return { ok: false, reason: 'launch_timeout', cleanupError: error.message, pid: proc.pid, tmpDir };
  }
}

async function main() {
  let options;
  try { options = parseArgs(process.argv.slice(2)); }
  catch (error) { console.error(error.message); process.exitCode = 1; return; }
  if (options.help) { printHelp(); return; }
  let result;
  if (options.pid) {
    try {
      const profile = findOwnedProfile(options.pid);
      await stopOwned(profile);
      result = { ok: true, stopped: true, pid: options.pid, tmpDir: profile.tmpDir };
    } catch (error) { result = { ok: false, reason: error.message, pid: options.pid }; }
  } else {
    result = await launch(options);
  }
  console.log(JSON.stringify(result, null, 2));
  if (!result.ok) process.exitCode = 2;
}

main().catch(error => {
  console.log(JSON.stringify({ ok: false, reason: error.message }, null, 2));
  process.exitCode = 2;
});
