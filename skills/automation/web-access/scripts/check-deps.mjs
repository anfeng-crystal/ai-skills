#!/usr/bin/env node

/**
 * 检查 web-access 最小运行条件：Node 版本、浏览器路径和默认 CDP 端点。
 * 默认只读取本地环境；`--dry-run` 只输出计划，不访问浏览器或端点。
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const MIN_NODE_MAJOR = 22;

function printHelp() {
  console.log(`Usage:
  node scripts/check-deps.mjs [options]

Options:
  --host <host>           CDP HTTP host, default from WEB_ACCESS_CDP_HOST or 127.0.0.1
  --port <port>           CDP HTTP port, default from WEB_ACCESS_CDP_PORT or 9222
  --browser-path <path>   Explicit browser executable path
  --json                  Emit JSON output
  --dry-run               Print the planned checks without executing them
  --auto-launch           CDP unreachable时自动调用 cdp-launch.mjs 临时启动
  --strict                Exit non-zero when readyForCdp is false
  --help                  Show this help
`);
}

function parseArgs(argv) {
  const parsed = {
    host: process.env.WEB_ACCESS_CDP_HOST || "127.0.0.1",
    port: Number(process.env.WEB_ACCESS_CDP_PORT || "9222"),
    browserPath: process.env.WEB_ACCESS_BROWSER_PATH || null,
    json: false,
    autoLaunch: false,
    dryRun: false,
    strict: false,
    help: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    switch (token) {
      case "--host":
        parsed.host = argv[++index];
        break;
      case "--port":
        parsed.port = Number(argv[++index]);
        break;
      case "--browser-path":
        parsed.browserPath = argv[++index];
        break;
      case "--json":
        parsed.json = true;
        break;
      case "--auto-launch":
        parsed.autoLaunch = true;
        break;
      case "--dry-run":
        parsed.dryRun = true;
        break;
      case "--strict":
        parsed.strict = true;
        break;
      case "--help":
      case "-h":
        parsed.help = true;
        break;
      default:
        throw new Error(`Unknown argument: ${token}`);
    }
  }

  return parsed;
}

function browserCandidates(explicitPath) {
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
    explicitPath,
    ...(byPlatform[process.platform] || byPlatform.linux),
  ].filter(Boolean);
}

function detectBrowserPath(explicitPath) {
  for (const candidate of browserCandidates(explicitPath)) {
    try {
      fs.accessSync(candidate, process.platform === "win32" ? fs.constants.F_OK : fs.constants.X_OK);
      return candidate;
    } catch {
      continue;
    }
  }
  return null;
}

function allowRemoteHost(host) {
  if (host === "127.0.0.1" || host === "localhost" || host === "::1") {
    return true;
  }
  return process.env.WEB_ACCESS_ALLOW_REMOTE === "1";
}

async function detectCdp(host, port) {
  if (!allowRemoteHost(host)) {
    return {
      reachable: false,
      reason: "remote_host_blocked",
      webSocketUrl: null,
      host,
      port,
    };
  }

  try {
    const response = await fetch(`http://${host}:${port}/json/version`, {
      signal: AbortSignal.timeout(1500),
    });
    if (!response.ok) {
      return {
        reachable: false,
        reason: `http_${response.status}`,
        webSocketUrl: null,
        host,
        port,
      };
    }

    const payload = await response.json();
    return {
      reachable: true,
      reason: "ok",
      webSocketUrl: payload.webSocketDebuggerUrl || null,
      browser: payload.Browser || null,
      host,
      port,
    };
  } catch (error) {
    return {
      reachable: false,
      reason: error instanceof Error ? error.message : "unknown_error",
      webSocketUrl: null,
      host,
      port,
    };
  }
}

function printText(result) {
  if (result.dryRun) {
    console.log("mode=dry-run");
    console.log(`plannedHost=${result.plan.host}`);
    console.log(`plannedPort=${result.plan.port}`);
    for (const candidate of result.plan.browserCandidates) {
      console.log(`browserCandidate=${candidate}`);
    }
    return;
  }

  console.log(`Node: ${result.node.version} (${result.node.ok ? "ok" : "too_old"})`);
  console.log(`Browser: ${result.browser.path || "not_found"}`);
  console.log(
    `CDP: ${result.cdp.reachable ? "reachable" : "unreachable"} (${result.cdp.host}:${result.cdp.port}${result.cdp.reason ? `, ${result.cdp.reason}` : ""})`,
  );
  console.log(`Brave Search: ${result.backends.braveSearch.configured ? "configured" : "not_configured"}`);
  console.log(`Ready for CDP: ${result.readyForCdp ? "yes" : "no"}`);
  if (result.recommendations.length > 0) {
    console.log("Recommendations:");
    for (const line of result.recommendations) {
      console.log(`- ${line}`);
    }
  }
}

let options;
try {
  options = parseArgs(process.argv.slice(2));
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  printHelp();
  process.exit(1);
}

if (options.help) {
  printHelp();
  process.exit(0);
}

if (options.dryRun) {
  const payload = {
    ok: true,
    dryRun: true,
    plan: {
      host: options.host,
      port: options.port,
      browserCandidates: browserCandidates(options.browserPath),
      remoteAllowed: allowRemoteHost(options.host),
      autoLaunch: options.autoLaunch,
      checks: ["node-version", "browser-path", "cdp-json-version", "brave-search-key"],
    },
  };
  if (options.json) {
    console.log(JSON.stringify(payload, null, 2));
  } else {
    printText(payload);
  }
  process.exit(0);
}

const nodeMajor = Number(process.versions.node.split(".")[0]);
const browserPath = detectBrowserPath(options.browserPath);
const cdp = await detectCdp(options.host, options.port);

const result = {
  ok: nodeMajor >= MIN_NODE_MAJOR && Boolean(browserPath),
  readyForCdp: nodeMajor >= MIN_NODE_MAJOR && Boolean(browserPath) && cdp.reachable,
  node: {
    version: process.version,
    ok: nodeMajor >= MIN_NODE_MAJOR,
    minimumMajor: MIN_NODE_MAJOR,
  },
  browser: {
    found: Boolean(browserPath),
    path: browserPath,
  },
  cdp,
  backends: {
    braveSearch: {
      configured: Boolean(process.env.BRAVE_SEARCH_API_KEY),
      endpoint: process.env.BRAVE_SEARCH_API_ENDPOINT || "https://api.search.brave.com/res/v1/web/search",
    },
  },
  recommendations: [
    ...(nodeMajor >= MIN_NODE_MAJOR ? [] : [`升级 Node 到 ${MIN_NODE_MAJOR}+`]),
    ...(browserPath ? [] : ["安装或显式指定可执行浏览器路径"]),
    ...(cdp.reachable ? [] : options.autoLaunch ? ["CDP 不可达，尝试自动启动..."] : ["CDP 未开启；加 --auto-launch 可自动临时启动"]),
  ],
};

// Auto-launch CDP if requested and unreachable
if (options.autoLaunch && !result.readyForCdp && browserPath) {
  const launchScript = new URL("./cdp-launch.mjs", import.meta.url).pathname;
  try {
    const { execFileSync } = await import("node:child_process");
    const out = execFileSync(process.execPath, [launchScript], { encoding: "utf-8", timeout: 15000 });
    const launchResult = JSON.parse(out);
    if (launchResult.ok) {
      result.cdp = {
        reachable: true,
        reason: launchResult.launched ? "auto_launched" : "already_running",
        webSocketUrl: launchResult.webSocketDebuggerUrl,
        browser: launchResult.browser,
        host: launchResult.host,
        port: launchResult.port,
        pid: launchResult.pid,
        tmpDir: launchResult.tmpDir,
      };
      result.readyForCdp = true;
      if (options.json) {
        result.recommendations = result.recommendations.filter(r => !r.includes("CDP"));
      }
    }
  } catch {
    // launch failed, keep original result
  }
}

if (options.json) {
  console.log(JSON.stringify(result, null, 2));
} else {
  printText(result);
}

if (options.strict && !result.readyForCdp) {
  process.exit(2);
}
