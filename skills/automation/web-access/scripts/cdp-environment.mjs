import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { isIP } from 'node:net';

export function optionValue(argv, index, option) {
  const value = argv[index];
  if (value === undefined || value.trim() === '' || value.startsWith('--')) {
    throw new Error(`Missing value for ${option}`);
  }
  return value;
}

export function validateEndpoint(host, port) {
  if (typeof host !== 'string' || !host || /[\s/@?#]/.test(host)
    || (host.includes(':') && isIP(host) !== 6)) {
    throw new Error('Invalid CDP host; supply a hostname or unbracketed IP address');
  }
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('CDP port must be an integer from 1 to 65535');
  }
}

export function localHost(host) {
  return ['127.0.0.1', 'localhost', '::1'].includes(host);
}

export function allowRemoteHost(host) {
  return localHost(host) || process.env.WEB_ACCESS_ALLOW_REMOTE === '1';
}

export function versionUrl(host, port) {
  return `http://${isIP(host) === 6 ? `[${host}]` : host}:${port}/json/version`;
}

export function browserCandidates(explicitPath = process.env.WEB_ACCESS_BROWSER_PATH) {
  const home = os.homedir();
  const localAppData = process.env.LOCALAPPDATA || path.join(home, 'AppData', 'Local');
  const programFiles = process.env.PROGRAMFILES || 'C:\\Program Files';
  const programFilesX86 = process.env['PROGRAMFILES(X86)'] || 'C:\\Program Files (x86)';
  const byPlatform = {
    darwin: [
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Chromium.app/Contents/MacOS/Chromium',
      '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
      '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
      path.join(home, 'Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
    ],
    win32: [
      path.join(programFiles, 'Google/Chrome/Application/chrome.exe'),
      path.join(programFilesX86, 'Google/Chrome/Application/chrome.exe'),
      path.join(localAppData, 'Google/Chrome/Application/chrome.exe'),
      path.join(programFiles, 'Microsoft/Edge/Application/msedge.exe'),
      path.join(programFilesX86, 'Microsoft/Edge/Application/msedge.exe'),
      path.join(localAppData, 'Microsoft/Edge/Application/msedge.exe'),
      path.join(programFiles, 'BraveSoftware/Brave-Browser/Application/brave.exe'),
      path.join(programFilesX86, 'BraveSoftware/Brave-Browser/Application/brave.exe'),
      path.join(localAppData, 'BraveSoftware/Brave-Browser/Application/brave.exe'),
    ],
    linux: [
      '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium',
      '/usr/bin/chromium-browser', '/snap/bin/chromium', '/usr/bin/microsoft-edge', '/usr/bin/brave-browser',
    ],
  };
  return [explicitPath, ...(byPlatform[process.platform] || byPlatform.linux)].filter(Boolean);
}

export function detectBrowserPath(explicitPath) {
  for (const candidate of browserCandidates(explicitPath)) {
    try {
      fs.accessSync(candidate, process.platform === 'win32' ? fs.constants.F_OK : fs.constants.X_OK);
      return candidate;
    } catch { /* Try the next installed candidate. */ }
  }
  return null;
}
