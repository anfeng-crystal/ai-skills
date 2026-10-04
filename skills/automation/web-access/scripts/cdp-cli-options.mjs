import { optionValue, validateEndpoint, allowRemoteHost, versionUrl } from "./cdp-environment.mjs";

function requiredValue(argv, index, option) {
  const value = optionValue(argv, index, option);
  if (value === "-h") throw new Error(`Missing value for ${option}`);
  return value;
}

function integer(value, option, min = Number.MIN_SAFE_INTEGER, max = Number.MAX_SAFE_INTEGER) {
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < min || number > max) {
    throw new Error(`${option} must be an integer from ${min} to ${max}`);
  }
  return number;
}

function finiteNumber(value, option) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new Error(`${option} must be a finite number`);
  return number;
}

function choice(value, option, allowed) {
  if (!allowed.includes(value)) throw new Error(`Invalid ${option} value: ${value}; expected ${allowed.join("|")}`);
}

function endpointDefaults() {
  return {
    host: process.env.WEB_ACCESS_CDP_HOST || "127.0.0.1",
    port: process.env.WEB_ACCESS_CDP_PORT || "9222",
    endpoint: null,
    json: false,
    dryRun: false,
    help: false,
  };
}

// Both consumers share the same HTTP endpoint contract. Host checks remain at
// execution boundaries so dry-run can still describe an opted-out remote plan.
function normalizeHost(host) {
  return host.replace(/^\[(.*)\]$/, "$1").toLowerCase();
}

export function resolveHttpEndpoint(options) {
  let url;
  if (options.endpoint) {
    const hasScheme = /^[a-z][a-z\d+.-]*:\/\//i.test(options.endpoint);
    url = new URL(hasScheme ? options.endpoint : `http://${options.endpoint}`);
    if (!["http:", "https:"].includes(url.protocol)) throw new Error("CDP endpoint must use http:// or https://");
  } else {
    const host = normalizeHost(options.host);
    if (options.wsOnly) {
      // doctor/send with an explicit WS route do not consume default HTTP
      // settings. Keep these informational fields without blocking that route.
      return { base: versionUrl(host, options.port).replace(/\/json\/version$/, ""), host, port: options.port };
    }
    validateEndpoint(host, options.port);
    url = new URL(versionUrl(host, options.port).replace(/\/json\/version$/, ""));
  }
  return {
    base: url.href.replace(/\/+$/, ""),
    host: normalizeHost(url.hostname),
    port: Number(url.port || (url.protocol === "https:" ? "443" : "80")),
  };
}

export function assertAllowedHost(host) {
  if (!allowRemoteHost(normalizeHost(host))) {
    throw new Error(`Refusing remote host ${host}; set WEB_ACCESS_ALLOW_REMOTE=1 to override.`);
  }
}

export function validateWsUrl(wsUrl) {
  const url = new URL(wsUrl);
  if (!["ws:", "wss:"].includes(url.protocol)) throw new Error("WebSocket endpoint must use ws:// or wss://");
  return url;
}

export function assertAllowedWsUrl(wsUrl) {
  assertAllowedHost(validateWsUrl(wsUrl).hostname);
}

function validateCommon(parsed) {
  parsed.port = parsed.endpoint || parsed.wsOnly
    ? Number(parsed.port) : integer(parsed.port, "--port", 1, 65535);
  // Validate syntax even in dry-run, before any source or transport can be read.
  resolveHttpEndpoint(parsed);
}

export function parseFindOptions(argv) {
  const parsed = {
    ...endpointDefaults(),
    first: false, listAll: false, includeDevtools: false,
    type: "page", mode: "contains", value: "summary", needle: null,
    only: "targets", limit: 20, since: null, sort: "recent",
    profileDir: process.env.WEB_ACCESS_CHROME_PROFILE_DIR || null,
    bookmarksPath: process.env.WEB_ACCESS_CHROME_BOOKMARKS_PATH || null,
    historyPath: process.env.WEB_ACCESS_CHROME_HISTORY_PATH || null,
  };
  const values = {
    "--endpoint": "endpoint", "--host": "host", "--port": "port",
    "--type": "type", "--mode": "mode", "--value": "value", "--match": "needle",
    "--only": "only", "--limit": "limit", "--since": "since", "--sort": "sort",
    "--profile-dir": "profileDir", "--bookmarks-path": "bookmarksPath", "--history-path": "historyPath",
  };
  const flags = { "--json": "json", "--dry-run": "dryRun", "--first": "first", "--list-all": "listAll", "--include-devtools": "includeDevtools" };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (Object.hasOwn(values, token)) parsed[values[token]] = requiredValue(argv, ++index, token);
    else if (Object.hasOwn(flags, token)) parsed[flags[token]] = true;
    else if (token === "--help" || token === "-h") parsed.help = true;
    else if (["--url", "--contains", "--title"].includes(token)) {
      parsed.mode = token.slice(2);
      // Legacy --title deliberately takes an optional value (needle --title).
      if (token !== "--title" || (argv[index + 1] && !argv[index + 1].startsWith("--") && argv[index + 1] !== "-h")) {
        parsed.needle = requiredValue(argv, ++index, token);
      }
    } else if (!token.startsWith("--") && !parsed.needle) parsed.needle = token;
    else throw new Error(`Unknown argument: ${token}`);
  }
  if (parsed.help) return parsed;
  choice(parsed.only, "--only", ["targets", "bookmarks", "history", "chrome", "all"]);
  // Local Chrome sources do not use a CDP endpoint. Syntax/missing-value checks
  // above still apply to every supplied option, including inactive routes.
  if (["targets", "all"].includes(parsed.only)) validateCommon(parsed);
  parsed.limit = integer(parsed.limit, "--limit", 1);
  choice(parsed.mode, "--mode", ["contains", "exact", "prefix", "host", "regex", "url", "title"]);
  choice(parsed.value, "--value", ["summary", "url", "title", "id", "webSocketDebuggerUrl", "json"]);
  choice(parsed.sort, "--sort", ["recent", "visits"]);
  if (parsed.mode === "regex" && parsed.needle && !parsed.listAll) new RegExp(parsed.needle, "i");
  return parsed;
}

export function parseProxyOptions(argv, command) {
  const parsed = {
    ...endpointDefaults(),
    wsUrl: process.env.WEB_ACCESS_CDP_WS_URL || null,
    timeout: 5000, allowUnsafe: false, method: null, params: null, id: null,
    file: null, selector: null, x: 0, y: null, direction: null, positionals: [],
  };
  const values = {
    "--endpoint": "endpoint", "--host": "host", "--port": "port", "--ws-url": "wsUrl",
    "--method": "method", "--params": "params", "--id": "id", "--timeout": "timeout",
    "--file": "file", "--selector": "selector", "--x": "x", "--y": "y", "--direction": "direction",
  };
  const flags = { "--json": "json", "--dry-run": "dryRun", "--allow-unsafe": "allowUnsafe" };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (Object.hasOwn(values, token)) parsed[values[token]] = requiredValue(argv, ++index, token);
    else if (Object.hasOwn(flags, token)) parsed[flags[token]] = true;
    else if (token === "--help" || token === "-h") parsed.help = true;
    else if (token.startsWith("--")) throw new Error(`Unknown argument: ${token}`);
    else parsed.positionals.push(token);
  }
  if (parsed.help) return parsed;
  parsed.wsOnly = Boolean(parsed.wsUrl && ["doctor", "probe", "send"].includes(command));
  validateCommon(parsed);
  // Larger delays overflow Node's setTimeout and become approximately 1ms.
  parsed.timeout = integer(parsed.timeout, "--timeout", 1, 2_147_483_647);
  if (parsed.id !== null) parsed.id = integer(parsed.id, "--id");
  parsed.x = finiteNumber(parsed.x, "--x");
  if (parsed.y !== null) parsed.y = finiteNumber(parsed.y, "--y");
  if (parsed.direction !== null) choice(parsed.direction, "--direction", ["bottom"]);
  if (parsed.wsOnly) validateWsUrl(parsed.wsUrl);
  return parsed;
}

export function reportCliError(error, json, command) {
  const message = error instanceof Error ? error.message : String(error);
  if (json) console.log(JSON.stringify({ ok: false, command, error: message }, null, 2));
  else console.error(message);
  process.exitCode = 1;
}
