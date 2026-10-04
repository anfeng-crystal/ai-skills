#!/usr/bin/env node

/**
 * 检查 web-access 最小运行条件：Node 版本、浏览器路径和默认 CDP 端点。
 * 默认只读取本地环境；`--dry-run` 只输出计划，不访问浏览器或端点。
 */

import { fileURLToPath } from "node:url";
import { allowRemoteHost, localHost, versionUrl, validateEndpoint, optionValue, browserCandidates, detectBrowserPath } from "./cdp-environment.mjs";
import { readCdpVersion } from "./cdp-response.mjs";

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
        parsed.host = optionValue(argv, ++index, token);
        break;
      case "--port":
        parsed.port = Number(optionValue(argv, ++index, token));
        break;
      case "--browser-path":
        parsed.browserPath = optionValue(argv, ++index, token);
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

  if (!parsed.help) validateEndpoint(parsed.host, parsed.port);
  return parsed;
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
    const response = await fetch(versionUrl(host, port), {
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

    const status = await readCdpVersion(response);
    if (!status.ok) return { reachable: false, reason: status.reason, webSocketUrl: null, host, port };
    return {
      reachable: true,
      reason: "ok",
      webSocketUrl: status.ws,
      browser: status.browser,
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
    ...(cdp.reachable ? [] : cdp.reason === "invalid_cdp_response"
      ? ["CDP 端点响应无效；核对所选主机、端口及占用该端口的服务"]
      : options.autoLaunch ? ["CDP 不可达，尝试自动启动..."] : ["CDP 未开启；加 --auto-launch 可自动临时启动"]),
  ],
};

// Only an unreachable local endpoint can be repaired by starting a local child.
if (options.autoLaunch && !cdp.reachable && cdp.reason !== "invalid_cdp_response" && browserPath && result.node.ok && localHost(options.host)) {
  const launchScript = fileURLToPath(new URL("./cdp-launch.mjs", import.meta.url));
  try {
    const { execFileSync } = await import("node:child_process");
    const out = execFileSync(process.execPath, [launchScript], {
      encoding: "utf-8", timeout: 18000, stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, WEB_ACCESS_CDP_HOST: options.host,
        WEB_ACCESS_CDP_PORT: String(options.port), WEB_ACCESS_BROWSER_PATH: browserPath },
    });
    const launchResult = JSON.parse(out);
    if (!launchResult.ok) throw new Error(launchResult.reason || "launch_failed");
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
    result.recommendations = result.recommendations.filter(line => !line.includes("CDP"));
  } catch (error) {
    let failure;
    try { failure = JSON.parse(error.stdout?.toString() || "null"); } catch { /* Preserve a bounded generic reason. */ }
    result.cdp.launchFailure = failure || { reason: error.code || "launch_failed" };
    result.recommendations = result.recommendations.filter(line => !line.includes("CDP"));
    result.recommendations.push(`CDP 自动启动失败：${result.cdp.launchFailure.reason}`);
  }
} else if (options.autoLaunch && !cdp.reachable && cdp.reason !== "invalid_cdp_response" && !localHost(options.host)) {
  result.recommendations = result.recommendations.filter(line => !line.includes("CDP"));
  result.recommendations.push("远程 CDP 不可达；本地自动启动无法修复该端点");
}

if (options.json) {
  console.log(JSON.stringify(result, null, 2));
} else {
  printText(result);
}

if (options.strict && !result.readyForCdp) {
  process.exit(2);
}
