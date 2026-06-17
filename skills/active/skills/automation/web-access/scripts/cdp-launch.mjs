#!/usr/bin/env node
/**
 * 检测 CDP 是否可达；不可达时自动临时启动 Chrome headless。
 * 输出 JSON：{ ok, launched, host, port, webSocketDebuggerUrl, pid, tmpDir }
 * 用法：node scripts/cdp-launch.mjs [--kill [pid]]
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const HOST = process.env.WEB_ACCESS_CDP_HOST || "127.0.0.1";
const PORT = Number(process.env.WEB_ACCESS_CDP_PORT || "9222");
const MAX_WAIT = 10_000;
const POLL = 300;

function log(s) { if (process.env.WEB_ACCESS_QUIET !== "1") console.error(`[cdp-launch] ${s}`); }

function findBrowser() {
  for (const p of browserCandidates()) {
    try {
      fs.accessSync(p, process.platform === "win32" ? fs.constants.F_OK : fs.constants.X_OK);
      return p;
    } catch {
      continue;
    }
  }
  return null;
}

function browserCandidates() {
  const home = os.homedir();
  const localAppData = process.env.LOCALAPPDATA || path.join(home, "AppData", "Local");
  const programFiles = process.env.PROGRAMFILES || "C:\\Program Files";
  const programFilesX86 = process.env["PROGRAMFILES(X86)"] || "C:\\Program Files (x86)";
  const byPlatform = {
    darwin: [
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
      "/Applications/Chromium.app/Contents/MacOS/Chromium",
      "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
      "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
      path.join(home, "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    ],
    win32: [
      path.join(programFiles, "Google/Chrome/Application/chrome.exe"),
      path.join(programFilesX86, "Google/Chrome/Application/chrome.exe"),
      path.join(localAppData, "Google/Chrome/Application/chrome.exe"),
      path.join(programFiles, "Microsoft/Edge/Application/msedge.exe"),
      path.join(programFilesX86, "Microsoft/Edge/Application/msedge.exe"),
      path.join(localAppData, "Microsoft/Edge/Application/msedge.exe"),
      path.join(programFiles, "BraveSoftware/Brave-Browser/Application/brave.exe"),
      path.join(programFilesX86, "BraveSoftware/Brave-Browser/Application/brave.exe"),
      path.join(localAppData, "BraveSoftware/Brave-Browser/Application/brave.exe"),
    ],
    linux: [
      "/usr/bin/google-chrome",
      "/usr/bin/google-chrome-stable",
      "/usr/bin/chromium",
      "/usr/bin/chromium-browser",
      "/snap/bin/chromium",
      "/usr/bin/microsoft-edge",
      "/usr/bin/brave-browser",
    ],
  };
  return [
    process.env.WEB_ACCESS_BROWSER_PATH,
    ...(byPlatform[process.platform] || byPlatform.linux),
  ].filter(Boolean);
}

async function probe() {
  try {
    const r = await fetch(`http://${HOST}:${PORT}/json/version`, { signal: AbortSignal.timeout(1500) });
    if (!r.ok) return { ok: false };
    const j = await r.json();
    return { ok: true, ws: j.webSocketDebuggerUrl || null, browser: j.Browser || null };
  } catch { return { ok: false }; }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("--kill")) {
    const pid = args[args.indexOf("--kill") + 1];
    if (pid) {
      try { process.kill(Number(pid), "SIGTERM"); await sleep(2000); process.kill(Number(pid), 0); } catch { /* exited */ }
    }
    for (const e of fs.readdirSync(os.tmpdir())) {
      if (/^web-access-cdp-/.test(e)) {
        try { fs.rmSync(path.join(os.tmpdir(), e), { recursive: true, force: true }); } catch {}
      }
    }
    process.exit(0);
  }

  const existing = await probe();
  if (existing.ok) {
    console.log(JSON.stringify({ ok: true, launched: false, host: HOST, port: PORT, webSocketDebuggerUrl: existing.ws, browser: existing.browser, pid: null, tmpDir: null }, null, 2));
    return;
  }

  const browser = findBrowser();
  if (!browser) { console.log(JSON.stringify({ ok: false, reason: "browser_not_found" }, null, 2)); process.exit(2); }

  const tmpDir = path.join(os.tmpdir(), `web-access-cdp-${Date.now()}`);
  fs.mkdirSync(tmpDir, { recursive: true });
  const proc = spawn(browser, [
    `--remote-debugging-port=${PORT}`, `--user-data-dir=${tmpDir}`,
    "--no-first-run", "--no-default-browser-check", "--headless=new",
    "--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox", "about:blank",
  ], { detached: true, stdio: ["ignore", "ignore", "ignore"] });

  const t0 = Date.now();
  while (Date.now() - t0 < MAX_WAIT) {
    const s = await probe();
    if (s.ok) {
      console.log(JSON.stringify({ ok: true, launched: true, host: HOST, port: PORT, webSocketDebuggerUrl: s.ws, browser: s.browser, pid: proc.pid, tmpDir }, null, 2));
      return;
    }
    await sleep(POLL);
  }

  try { proc.kill("SIGKILL"); fs.rmSync(tmpDir, { recursive: true, force: true }); } catch {}
  console.log(JSON.stringify({ ok: false, reason: "launch_timeout" }, null, 2));
  process.exit(2);
}

main().catch(e => { log(`Fatal: ${e.message}`); process.exit(2); });
