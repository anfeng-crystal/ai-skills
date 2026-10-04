import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const MARKER = '.web-access-owner.json';
export const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

export function isAlive(pid) {
  try { process.kill(pid, 0); return true; }
  catch (error) {
    if (error.code === 'ESRCH') return false;
    throw error; // Permission or lookup errors do not prove that the process exited.
  }
}

export function processIdentity(pid) {
  const options = { encoding: 'utf8', timeout: 2000, stdio: ['ignore', 'pipe', 'pipe'] };
  const identity = process.platform === 'win32'
    ? execFileSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
      `$p = Get-CimInstance Win32_Process -Filter 'ProcessId = ${pid}'; if ($null -eq $p) { exit 1 }; $p | Select-Object CreationDate,CommandLine,ExecutablePath | ConvertTo-Json -Compress`,
    ], options).trim()
    : execFileSync('ps', ['-p', String(pid), '-o', 'lstart=', '-o', 'command='], options).trim();
  if (!identity) throw new Error('Process identity unavailable');
  return identity;
}

function commandForIdentity(identity) {
  if (process.platform === 'win32') {
    const processInfo = JSON.parse(identity);
    if (!processInfo.CreationDate || !processInfo.ExecutablePath || !processInfo.CommandLine) {
      throw new Error('Incomplete process identity');
    }
    return { command: processInfo.CommandLine, executable: processInfo.ExecutablePath };
  }
  // ps lstart is followed by the complete command; never authorize from a substring alone.
  const match = identity.match(/^\S+\s+\S+\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4}\s+(.+)$/s);
  if (!match) throw new Error('Incomplete process identity');
  return { command: match[1], executable: null };
}

function initialIdentityMatches(identity, browser, tmpDir) {
  const { command, executable } = commandForIdentity(identity);
  const normalize = value => process.platform === 'win32' ? value.toLowerCase() : value;
  const expectedExecutables = [browser, fs.realpathSync(browser)].map(normalize);
  if (executable && !expectedExecutables.includes(normalize(executable))) return false;
  const normalizedCommand = normalize(command);
  const browserMatches = expectedExecutables.some(expected =>
    normalizedCommand.startsWith(`${expected} `) || normalizedCommand.startsWith(`"${expected}" `));
  const profileArguments = [`--user-data-dir=${tmpDir}`, `"--user-data-dir=${tmpDir}"`, `--user-data-dir="${tmpDir}"`];
  const profileMatches = profileArguments.some(argument => {
    const index = command.indexOf(` ${argument}`);
    const end = index + argument.length + 1;
    return index >= 0 && (end === command.length || /\s/.test(command[end]));
  });
  return browserMatches && profileMatches;
}

export function saveOwner(tmpDir, pid, browser) {
  const owner = { version: 1, pid, identity: processIdentity(pid) };
  if (!initialIdentityMatches(owner.identity, browser, tmpDir)) {
    throw new Error('initial_process_identity_mismatch');
  }
  fs.writeFileSync(path.join(tmpDir, MARKER), JSON.stringify(owner), { mode: 0o600, flag: 'wx' });
  return owner;
}

function ownedFile(target, directory) {
  const stat = fs.lstatSync(target);
  return !stat.isSymbolicLink() && (directory ? stat.isDirectory() : stat.isFile())
    && (typeof process.getuid !== 'function' || stat.uid === process.getuid());
}

export function findOwnedProfile(pid) {
  const matches = [];
  for (const name of fs.readdirSync(os.tmpdir())) {
    if (!name.startsWith('web-access-cdp-')) continue;
    const tmpDir = path.join(os.tmpdir(), name);
    try {
      if (!ownedFile(tmpDir, true) || !ownedFile(path.join(tmpDir, MARKER), false)) continue;
      const owner = JSON.parse(fs.readFileSync(path.join(tmpDir, MARKER), 'utf8'));
      if (owner.version === 1 && owner.pid === pid && typeof owner.identity === 'string' && owner.identity.trim()) {
        matches.push({ tmpDir, owner });
      }
    } catch { /* Legacy, unreadable or invalid records never authorize termination. */ }
  }
  if (matches.length !== 1) throw new Error(matches.length ? 'ambiguous_owned_profile' : 'owned_profile_not_found');
  return matches[0];
}

export async function stopOwned({ tmpDir, owner }) {
  const { pid } = owner;
  if (isAlive(pid)) {
    // Both start time and command line must still match before sending a signal.
    if (processIdentity(pid) !== owner.identity) throw new Error('process_identity_mismatch');
    process.kill(pid, 'SIGTERM');
    const deadline = Date.now() + 2000;
    while (isAlive(pid)) {
      if (Date.now() >= deadline) throw new Error('termination_pending');
      await sleep(100);
    }
  }
  fs.rmSync(tmpDir, { recursive: true, force: true });
}
