#!/usr/bin/env node

/**
 * 提供最小 CDP 操作：诊断端点、列出 targets、打开标签页、截图、导航、点击、滚动、关闭和透传原始命令。
 * 默认只读；会改变页面或浏览器状态的命令需要 `--allow-unsafe`。
 */

import fs from "node:fs";

const HARD_BLOCKED_METHODS = new Set(["Browser.close", "Browser.crash", "Page.crash"]);
const UNSAFE_PREFIXES = [
  "Runtime.evaluate",
  "Runtime.callFunctionOn",
  "Page.navigate",
  "Input.",
  "DOM.set",
  "Storage.",
  "Fetch.",
  "Network.set",
  "Emulation.set",
  "Target.createTarget",
  "Target.closeTarget",
  "Browser.grantPermissions",
];

function printHelp() {
  console.log(`Usage:
  node scripts/cdp-proxy.mjs doctor [options]
  node scripts/cdp-proxy.mjs probe [options]
  node scripts/cdp-proxy.mjs list [options]
  node scripts/cdp-proxy.mjs open <url> [options]
  node scripts/cdp-proxy.mjs info <target> [options]
  node scripts/cdp-proxy.mjs screenshot <target> [options]
  node scripts/cdp-proxy.mjs navigate <target> <url> [options]
  node scripts/cdp-proxy.mjs back <target> [options]
  node scripts/cdp-proxy.mjs click <target> <selector> [options]
  node scripts/cdp-proxy.mjs scroll <target> [options]
  node scripts/cdp-proxy.mjs close <target> [options]
  node scripts/cdp-proxy.mjs send <target> <method> [params-json] [options]
  node scripts/cdp-proxy.mjs send --ws-url <ws://...> --method <Domain.command> [--params <json>] [options]

Options:
  --endpoint <url>        CDP HTTP endpoint, e.g. http://127.0.0.1:9222
  --host <host>           CDP HTTP host, default from WEB_ACCESS_CDP_HOST
  --port <port>           CDP HTTP port, default from WEB_ACCESS_CDP_PORT
  --ws-url <url>          Explicit target or browser WebSocket endpoint
  --method <name>         CDP method name for flag-based send
  --params <json>         CDP params for flag-based send
  --id <number>           Explicit CDP request id
  --timeout <ms>          Timeout in milliseconds, default 5000
  --file <path>           Output file path for screenshot
  --selector <css>        CSS selector for click
  --x <number>            Horizontal position for scroll
  --y <number>            Vertical position for scroll
  --direction <bottom>    Scroll shortcut, currently supports bottom
  --json                  Emit JSON output
  --dry-run               Print the planned request without executing it
  --allow-unsafe          Allow commands that can execute JS or mutate browser/page state
  --help                  Show this help
`);
}

function parseGlobalOptions(argv) {
  const parsed = {
    host: process.env.WEB_ACCESS_CDP_HOST || "127.0.0.1",
    port: Number(process.env.WEB_ACCESS_CDP_PORT || "9222"),
    endpoint: null,
    wsUrl: process.env.WEB_ACCESS_CDP_WS_URL || null,
    timeout: 5000,
    json: false,
    dryRun: false,
    allowUnsafe: false,
    method: null,
    params: null,
    id: null,
    file: null,
    selector: null,
    x: 0,
    y: null,
    direction: null,
    positionals: [],
    help: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    switch (token) {
      case "--endpoint":
        parsed.endpoint = argv[++index];
        break;
      case "--host":
        parsed.host = argv[++index];
        break;
      case "--port":
        parsed.port = Number(argv[++index]);
        break;
      case "--ws-url":
        parsed.wsUrl = argv[++index];
        break;
      case "--method":
        parsed.method = argv[++index];
        break;
      case "--params":
        parsed.params = argv[++index];
        break;
      case "--id":
        parsed.id = Number(argv[++index]);
        break;
      case "--timeout":
        parsed.timeout = Number(argv[++index]);
        break;
      case "--file":
        parsed.file = argv[++index];
        break;
      case "--selector":
        parsed.selector = argv[++index];
        break;
      case "--x":
        parsed.x = Number(argv[++index]);
        break;
      case "--y":
        parsed.y = Number(argv[++index]);
        break;
      case "--direction":
        parsed.direction = argv[++index];
        break;
      case "--json":
        parsed.json = true;
        break;
      case "--dry-run":
        parsed.dryRun = true;
        break;
      case "--allow-unsafe":
        parsed.allowUnsafe = true;
        break;
      case "--help":
      case "-h":
        parsed.help = true;
        break;
      default:
        parsed.positionals.push(token);
        break;
    }
  }

  return parsed;
}

function resolveHttpEndpoint(options) {
  if (options.endpoint) {
    const normalized = /^https?:\/\//i.test(options.endpoint) ? options.endpoint : `http://${options.endpoint}`;
    const url = new URL(normalized);
    return {
      base: normalized.replace(/\/+$/, ""),
      host: url.hostname,
      port: Number(url.port || (url.protocol === "https:" ? "443" : "80")),
    };
  }

  return {
    base: `http://${options.host}:${options.port}`,
    host: options.host,
    port: options.port,
  };
}

function assertAllowedHost(host) {
  const localHosts = new Set(["127.0.0.1", "localhost", "::1"]);
  if (!localHosts.has(host) && process.env.WEB_ACCESS_ALLOW_REMOTE !== "1") {
    throw new Error(`Refusing remote host ${host}; set WEB_ACCESS_ALLOW_REMOTE=1 to override.`);
  }
}

function assertAllowedWsUrl(wsUrl) {
  const url = new URL(wsUrl);
  assertAllowedHost(url.hostname);
}

function classifyMethodSafety(method) {
  if (HARD_BLOCKED_METHODS.has(method)) {
    return "hard-blocked";
  }
  if (UNSAFE_PREFIXES.some((prefix) => method === prefix || method.startsWith(prefix))) {
    return "allow-unsafe-required";
  }
  return "safe";
}

function assertSafeMethod(method, allowUnsafe) {
  const safety = classifyMethodSafety(method);
  if (safety === "hard-blocked") {
    throw new Error(`Refusing blocked CDP method: ${method}`);
  }
  if (safety === "allow-unsafe-required" && !allowUnsafe) {
    throw new Error(`Method ${method} requires --allow-unsafe`);
  }
  return safety;
}

function parseParams(rawParams) {
  if (!rawParams) {
    return {};
  }
  return JSON.parse(rawParams);
}

async function getBrowserEndpoint(endpoint, wsUrlOverride) {
  if (wsUrlOverride) {
    assertAllowedWsUrl(wsUrlOverride);
    return {
      browserWSEndpoint: wsUrlOverride,
      source: "explicit_ws_url",
    };
  }

  assertAllowedHost(endpoint.host);
  let response;
  try {
    response = await fetch(`${endpoint.base}/json/version`, {
      signal: AbortSignal.timeout(2000),
    });
  } catch (error) {
    throw new Error(
      `Failed to reach CDP version endpoint at ${endpoint.base}/json/version: ${
        error instanceof Error ? error.message : "unknown_error"
      }`,
    );
  }

  if (!response.ok) {
    throw new Error(`Failed to reach /json/version: HTTP ${response.status}`);
  }

  const payload = await response.json();
  return {
    browserWSEndpoint: payload.webSocketDebuggerUrl || null,
    browser: payload.Browser || null,
    protocolVersion: payload["Protocol-Version"] || null,
    source: "http_version_endpoint",
  };
}

async function listTargets(endpoint) {
  assertAllowedHost(endpoint.host);
  let response;
  try {
    response = await fetch(`${endpoint.base}/json/list`, {
      signal: AbortSignal.timeout(2000),
    });
  } catch (error) {
    throw new Error(
      `Failed to reach CDP list endpoint at ${endpoint.base}/json/list: ${
        error instanceof Error ? error.message : "unknown_error"
      }`,
    );
  }

  if (!response.ok) {
    throw new Error(`Failed to reach /json/list: HTTP ${response.status}`);
  }

  return response.json();
}

function resolveTarget(targets, query) {
  const normalized = String(query || "").trim();
  if (!normalized) {
    throw new Error("Target is required.");
  }

  return (
    targets.find((target) => String(target.id).startsWith(normalized)) ||
    targets.find((target) => target.url === normalized) ||
    targets.find(
      (target) =>
        String(target.url || "").includes(normalized) ||
        String(target.title || "").includes(normalized),
    ) ||
    null
  );
}

let cdpRequestCounter = 1;
function nextCdpRequestId() {
  const id = cdpRequestCounter;
  cdpRequestCounter += 1;
  if (cdpRequestCounter > 2_000_000_000) {
    cdpRequestCounter = 1;
  }
  return id;
}

async function sendCdpCommand(webSocketUrl, method, params = {}, timeout = 5000, id = nextCdpRequestId()) {
  assertAllowedWsUrl(webSocketUrl);

  return new Promise((resolve, reject) => {
    const socket = new WebSocket(webSocketUrl);
    const timer = setTimeout(() => {
      try {
        socket.close();
      } catch {}
      reject(new Error(`CDP request timed out after ${timeout}ms`));
    }, timeout);

    socket.addEventListener("open", () => {
      socket.send(
        JSON.stringify({
          id,
          method,
          params,
        }),
      );
    });

    socket.addEventListener("message", (event) => {
      try {
        const payload = JSON.parse(String(event.data));
        if (payload.id !== id) {
          return;
        }
        clearTimeout(timer);
        socket.close();
        if (payload.error) {
          reject(new Error(JSON.stringify(payload.error)));
          return;
        }
        resolve(payload.result ?? null);
      } catch (error) {
        clearTimeout(timer);
        reject(error);
      }
    });

    socket.addEventListener("error", () => {
      clearTimeout(timer);
      reject(new Error("WebSocket connection failed."));
    });

    socket.addEventListener("close", () => {
      clearTimeout(timer);
    });
  });
}

async function resolveTargetSession(endpoint, targetQuery) {
  const targets = await listTargets(endpoint);
  const target = resolveTarget(targets, targetQuery);
  if (!target?.webSocketDebuggerUrl) {
    throw new Error(`Target not found or not attachable: ${targetQuery}`);
  }
  return { target, wsUrl: target.webSocketDebuggerUrl };
}

function jsString(value) {
  return JSON.stringify(String(value));
}

async function runDoctor(options) {
  const endpoint = resolveHttpEndpoint(options);

  if (options.dryRun) {
    const payload = {
      ok: true,
      dryRun: true,
      requests: [`${endpoint.base}/json/version`],
      endpoint,
      wsUrlOverride: options.wsUrl,
    };
    console.log(JSON.stringify(payload, null, 2));
    return;
  }

  const browserEndpoint = await getBrowserEndpoint(endpoint, options.wsUrl);
  const payload = {
    ok: Boolean(browserEndpoint.browserWSEndpoint),
    host: endpoint.host,
    port: endpoint.port,
    browser: browserEndpoint.browser,
    protocolVersion: browserEndpoint.protocolVersion,
    browserWSEndpoint: browserEndpoint.browserWSEndpoint,
    source: browserEndpoint.source,
  };
  console.log(JSON.stringify(payload, null, 2));
}

async function runList(options) {
  const endpoint = resolveHttpEndpoint(options);

  if (options.dryRun) {
    console.log(
      JSON.stringify(
        {
          ok: true,
          dryRun: true,
          requests: [`${endpoint.base}/json/list`],
          endpoint,
        },
        null,
        2,
      ),
    );
    return;
  }

  const targets = await listTargets(endpoint);
  const payload = targets.map((target) => ({
    id: target.id,
    type: target.type,
    title: target.title,
    url: target.url,
    webSocketDebuggerUrl: target.webSocketDebuggerUrl || null,
  }));
  if (options.json) {
    console.log(JSON.stringify(payload, null, 2));
  } else {
    for (const target of payload) {
      console.log(`${target.id}\t${target.type}\t${target.title}\t${target.url}`);
    }
  }
}

async function runOpen(options) {
  const [url] = options.positionals;
  if (!url) {
    throw new Error("Usage: open <url>");
  }

  const endpoint = resolveHttpEndpoint(options);
  if (options.dryRun) {
    console.log(
      JSON.stringify(
        {
          ok: true,
          dryRun: true,
          request: {
            method: "PUT",
            url: `${endpoint.base}/json/new?${encodeURIComponent(url)}`,
          },
          endpoint,
        },
        null,
        2,
      ),
    );
    return;
  }
  if (!options.allowUnsafe) {
    throw new Error("open mutates browser state; rerun with --allow-unsafe");
  }

  assertAllowedHost(endpoint.host);
  let response;
  try {
    response = await fetch(`${endpoint.base}/json/new?${encodeURIComponent(url)}`, {
      method: "PUT",
      signal: AbortSignal.timeout(2000),
    });
  } catch (error) {
    throw new Error(
      `Failed to reach CDP open endpoint at ${endpoint.base}/json/new: ${
        error instanceof Error ? error.message : "unknown_error"
      }`,
    );
  }

  if (!response.ok) {
    throw new Error(`Failed to open new target: HTTP ${response.status}`);
  }

  const payload = await response.json();
  if (options.json) {
    console.log(JSON.stringify(payload, null, 2));
  } else {
    console.log(`${payload.id}\t${payload.type}\t${payload.title}\t${payload.url}`);
  }
}

async function runInfo(options) {
  const [targetQuery] = options.positionals;
  if (!targetQuery) {
    throw new Error("Usage: info <target>");
  }
  const endpoint = resolveHttpEndpoint(options);
  const expression = `(() => ({ title: document.title, url: location.href, readyState: document.readyState, textLength: (document.body?.innerText || '').length }))()`;

  if (options.dryRun) {
    console.log(JSON.stringify({ ok: true, dryRun: true, targetQuery, endpoint, request: { method: "Runtime.evaluate", expression } }, null, 2));
    return;
  }

  const { target, wsUrl } = await resolveTargetSession(endpoint, targetQuery);
  const result = await sendCdpCommand(wsUrl, "Runtime.evaluate", { expression, returnByValue: true }, options.timeout);
  console.log(JSON.stringify({ target: { id: target.id, title: target.title, url: target.url }, result: result?.result?.value ?? null }, null, 2));
}

async function runScreenshot(options) {
  const [targetQuery] = options.positionals;
  if (!targetQuery) {
    throw new Error("Usage: screenshot <target> [--file /tmp/shot.png]");
  }
  const endpoint = resolveHttpEndpoint(options);
  const file = options.file || null;

  if (options.dryRun) {
    console.log(JSON.stringify({ ok: true, dryRun: true, targetQuery, endpoint, file, request: { method: "Page.captureScreenshot", params: { format: "png" } } }, null, 2));
    return;
  }

  const { target, wsUrl } = await resolveTargetSession(endpoint, targetQuery);
  await sendCdpCommand(wsUrl, "Page.enable", {}, options.timeout);
  const result = await sendCdpCommand(wsUrl, "Page.captureScreenshot", { format: "png" }, options.timeout);
  if (file) {
    fs.writeFileSync(file, Buffer.from(result.data, "base64"));
  }
  console.log(JSON.stringify({ target: { id: target.id, title: target.title, url: target.url }, file, bytes: result?.data ? Buffer.from(result.data, "base64").byteLength : 0 }, null, 2));
}

async function runNavigate(options) {
  const [targetQuery, url] = options.positionals;
  if (!targetQuery || !url) {
    throw new Error("Usage: navigate <target> <url>");
  }
  const endpoint = resolveHttpEndpoint(options);

  if (options.dryRun) {
    console.log(JSON.stringify({ ok: true, dryRun: true, targetQuery, endpoint, request: { method: "Page.navigate", params: { url } } }, null, 2));
    return;
  }
  if (!options.allowUnsafe) {
    throw new Error("navigate mutates page state; rerun with --allow-unsafe");
  }

  const { target, wsUrl } = await resolveTargetSession(endpoint, targetQuery);
  const result = await sendCdpCommand(wsUrl, "Page.navigate", { url }, options.timeout);
  console.log(JSON.stringify({ target: { id: target.id, title: target.title, url: target.url }, request: { url }, result }, null, 2));
}

async function runBack(options) {
  const [targetQuery] = options.positionals;
  if (!targetQuery) {
    throw new Error("Usage: back <target>");
  }
  const endpoint = resolveHttpEndpoint(options);

  if (options.dryRun) {
    console.log(JSON.stringify({ ok: true, dryRun: true, targetQuery, endpoint, requests: ["Page.getNavigationHistory", "Page.navigateToHistoryEntry"] }, null, 2));
    return;
  }
  if (!options.allowUnsafe) {
    throw new Error("back mutates page state; rerun with --allow-unsafe");
  }

  const { target, wsUrl } = await resolveTargetSession(endpoint, targetQuery);
  const history = await sendCdpCommand(wsUrl, "Page.getNavigationHistory", {}, options.timeout);
  const currentIndex = Number(history?.currentIndex ?? -1);
  const entries = Array.isArray(history?.entries) ? history.entries : [];
  if (currentIndex <= 0 || !entries[currentIndex - 1]?.id) {
    throw new Error("No back history entry available.");
  }
  const entryId = entries[currentIndex - 1].id;
  const result = await sendCdpCommand(wsUrl, "Page.navigateToHistoryEntry", { entryId }, options.timeout);
  console.log(JSON.stringify({ target: { id: target.id, title: target.title, url: target.url }, entryId, result }, null, 2));
}

async function runClick(options) {
  const [targetQuery, positionalSelector] = options.positionals;
  const selector = options.selector || positionalSelector;
  if (!targetQuery || !selector) {
    throw new Error("Usage: click <target> <selector> or click <target> --selector <css>");
  }
  const endpoint = resolveHttpEndpoint(options);
  const expression = `(() => { const el = document.querySelector(${jsString(selector)}); if (!el) return { ok: false, reason: 'not_found' }; el.click(); return { ok: true, tag: el.tagName, text: (el.innerText || el.textContent || '').trim().slice(0, 200) }; })()`;

  if (options.dryRun) {
    console.log(JSON.stringify({ ok: true, dryRun: true, targetQuery, endpoint, selector, request: { method: "Runtime.evaluate", expression } }, null, 2));
    return;
  }
  if (!options.allowUnsafe) {
    throw new Error("click mutates page state; rerun with --allow-unsafe");
  }

  const { target, wsUrl } = await resolveTargetSession(endpoint, targetQuery);
  const result = await sendCdpCommand(wsUrl, "Runtime.evaluate", { expression, returnByValue: true }, options.timeout);
  console.log(JSON.stringify({ target: { id: target.id, title: target.title, url: target.url }, selector, result: result?.result?.value ?? null }, null, 2));
}

async function runScroll(options) {
  const [targetQuery] = options.positionals;
  if (!targetQuery) {
    throw new Error("Usage: scroll <target> [--y 3000|--direction bottom]");
  }
  const endpoint = resolveHttpEndpoint(options);
  const y = options.direction === "bottom" ? Number.MAX_SAFE_INTEGER : Number.isFinite(options.y) ? options.y : 3000;
  const x = Number.isFinite(options.x) ? options.x : 0;
  const expression = `(() => { window.scrollTo(${x}, ${y}); return { ok: true, x: window.scrollX, y: window.scrollY, height: document.documentElement.scrollHeight }; })()`;

  if (options.dryRun) {
    console.log(JSON.stringify({ ok: true, dryRun: true, targetQuery, endpoint, x, y, direction: options.direction, request: { method: "Runtime.evaluate", expression } }, null, 2));
    return;
  }
  if (!options.allowUnsafe) {
    throw new Error("scroll mutates page state; rerun with --allow-unsafe");
  }

  const { target, wsUrl } = await resolveTargetSession(endpoint, targetQuery);
  const result = await sendCdpCommand(wsUrl, "Runtime.evaluate", { expression, returnByValue: true }, options.timeout);
  console.log(JSON.stringify({ target: { id: target.id, title: target.title, url: target.url }, result: result?.result?.value ?? null }, null, 2));
}

async function runClose(options) {
  const [targetQuery] = options.positionals;
  if (!targetQuery) {
    throw new Error("Usage: close <target>");
  }
  const endpoint = resolveHttpEndpoint(options);

  if (options.dryRun) {
    console.log(JSON.stringify({ ok: true, dryRun: true, targetQuery, endpoint, request: `${endpoint.base}/json/close/<resolved-target-id>` }, null, 2));
    return;
  }
  if (!options.allowUnsafe) {
    throw new Error("close mutates browser state; rerun with --allow-unsafe");
  }

  const { target } = await resolveTargetSession(endpoint, targetQuery);
  assertAllowedHost(endpoint.host);
  const response = await fetch(`${endpoint.base}/json/close/${target.id}`, {
    signal: AbortSignal.timeout(2000),
  });
  if (!response.ok) {
    throw new Error(`Failed to close target: HTTP ${response.status}`);
  }
  const text = await response.text();
  console.log(JSON.stringify({ target: { id: target.id, title: target.title, url: target.url }, result: text.trim() || "ok" }, null, 2));
}

async function runSend(options) {
  const endpoint = resolveHttpEndpoint(options);
  const targetQuery = options.positionals[0];
  const method = options.method || options.positionals[1];
  const rawParams = options.params ?? options.positionals[2] ?? null;

  if (!method) {
    throw new Error("Usage: send <target> <method> [params-json] or send --ws-url <url> --method <method>");
  }

  const safety = classifyMethodSafety(method);
  if (!options.dryRun) {
    assertSafeMethod(method, options.allowUnsafe);
  }
  let params;
  try {
    params = parseParams(rawParams);
  } catch (error) {
    throw new Error(`Invalid JSON params: ${error instanceof Error ? error.message : String(error)}`);
  }

  if (options.dryRun) {
    console.log(
      JSON.stringify(
        {
          ok: true,
          dryRun: true,
          endpoint,
          wsUrl: options.wsUrl,
          targetQuery: options.wsUrl ? null : targetQuery ?? null,
          safety,
          request: {
            id: options.id ?? "<auto>",
            method,
            params,
          },
        },
        null,
        2,
      ),
    );
    return;
  }

  let wsUrl = options.wsUrl;
  let target = null;
  if (!wsUrl && method.startsWith("Browser.")) {
    const browserEndpoint = await getBrowserEndpoint(endpoint, options.wsUrl);
    wsUrl = browserEndpoint.browserWSEndpoint;
  }

  if (!wsUrl) {
    if (!targetQuery) {
      throw new Error("Target is required unless --ws-url is provided or method starts with Browser.");
    }
    const resolved = await resolveTargetSession(endpoint, targetQuery);
    target = resolved.target;
    wsUrl = resolved.wsUrl;
  }

  const requestId = Number.isFinite(options.id) ? options.id : nextCdpRequestId();
  const result = await sendCdpCommand(wsUrl, method, params, options.timeout, requestId);
  const payload = {
    target: target
      ? {
          id: target.id,
          title: target.title,
          url: target.url,
        }
      : null,
    wsUrl,
    request: {
      id: requestId,
      method,
      params,
      safety,
    },
    result,
  };

  console.log(JSON.stringify(payload, null, 2));
}

const args = process.argv.slice(2);
const command = args[0];
if (!command || command === "--help" || command === "-h") {
  printHelp();
  process.exit(0);
}

const normalizedCommand = command === "probe" ? "doctor" : command;
let options;
try {
  options = parseGlobalOptions(args.slice(1));
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  printHelp();
  process.exit(1);
}

if (options.help) {
  printHelp();
  process.exit(0);
}

try {
  switch (normalizedCommand) {
    case "doctor":
      await runDoctor(options);
      break;
    case "list":
      await runList(options);
      break;
    case "open":
      await runOpen(options);
      break;
    case "info":
      await runInfo(options);
      break;
    case "screenshot":
      await runScreenshot(options);
      break;
    case "navigate":
      await runNavigate(options);
      break;
    case "back":
      await runBack(options);
      break;
    case "click":
      await runClick(options);
      break;
    case "scroll":
      await runScroll(options);
      break;
    case "close":
      await runClose(options);
      break;
    case "send":
      await runSend(options);
      break;
    default:
      console.error(`Unknown command: ${command}`);
      printHelp();
      process.exit(1);
  }
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  if (options.json) {
    console.log(
      JSON.stringify(
        {
          ok: false,
          command: normalizedCommand,
          error: message,
        },
        null,
        2,
      ),
    );
  } else {
    console.error(message);
  }
  process.exitCode = 1;
}
