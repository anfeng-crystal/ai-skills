#!/usr/bin/env node

/**
 * 提供最小 CDP 操作：诊断端点、列出 targets、打开标签页、截图、导航、点击、滚动、关闭和透传原始命令。
 * 默认只读；会改变页面或浏览器状态的命令需要 `--allow-unsafe`。
 */

import fs from "node:fs";
import { getBrowserEndpoint, listTargets, nextCdpRequestId, sendCdpCommand, resolveTargetSession, openTarget, closeTarget } from "./cdp-transport.mjs";
import { parseProxyOptions, resolveHttpEndpoint, reportCliError } from "./cdp-cli-options.mjs";

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

  const payload = await openTarget(endpoint, url);
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
  const text = await closeTarget(endpoint, target.id);
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
try {
  const options = parseProxyOptions(args.slice(1), normalizedCommand);
  if (options.help) {
    printHelp();
    process.exit(0);
  }

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
      throw new Error(`Unknown command: ${command}`);
  }
} catch (error) {
  reportCliError(error, args.includes("--json"), normalizedCommand);
}
