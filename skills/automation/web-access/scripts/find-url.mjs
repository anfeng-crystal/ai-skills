#!/usr/bin/env node

/**
 * 查找当前 CDP targets，或检索本地 Chrome 书签/历史。
 * 保留旧参数，并新增 `--only/--limit/--since/--sort`。
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

function printHelp() {
  console.log(`Usage:
  node scripts/find-url.mjs [needle] [options]

Options:
  --endpoint <url>                CDP HTTP endpoint, e.g. http://127.0.0.1:9222
  --host <host>                   CDP HTTP host, default from WEB_ACCESS_CDP_HOST
  --port <port>                   CDP HTTP port, default from WEB_ACCESS_CDP_PORT
  --contains <text>               Match URL or title by substring
  --url <text>                    Match URL by exact or contains
  --title [text]                  Match title by substring
  --match <text>                  Generic matcher for --mode
  --mode <contains|exact|prefix|host|regex|url|title>
  --type <page>                   Filter target type, default page
  --value <summary|url|title|id|webSocketDebuggerUrl|json>
  --first                         Return only the first match
  --list-all                      Ignore match text and list filtered results
  --include-devtools              Include devtools:// targets
  --only <targets|bookmarks|history|chrome|all>
                                   Source selection. chrome=bookmarks+history
  --limit <n>                     Limit results, default 20
  --since <1d|7h|YYYY-MM-DD>      Time filter for history items
  --sort <recent|visits>          Sort history by recent or visit count
  --profile-dir <path>            Explicit Chrome profile directory
  --bookmarks-path <path>         Explicit Chrome Bookmarks file path
  --history-path <path>           Explicit Chrome History file path
  --json                          Emit JSON output
  --dry-run                       Print the planned request without fetching
  --help                          Show this help
`);
}

function parseArgs(argv) {
  const parsed = {
    host: process.env.WEB_ACCESS_CDP_HOST || "127.0.0.1",
    port: Number(process.env.WEB_ACCESS_CDP_PORT || "9222"),
    endpoint: null,
    json: false,
    dryRun: false,
    first: false,
    listAll: false,
    includeDevtools: false,
    type: "page",
    mode: "contains",
    value: "summary",
    needle: null,
    only: "targets",
    limit: 20,
    since: null,
    sort: "recent",
    profileDir: process.env.WEB_ACCESS_CHROME_PROFILE_DIR || null,
    bookmarksPath: process.env.WEB_ACCESS_CHROME_BOOKMARKS_PATH || null,
    historyPath: process.env.WEB_ACCESS_CHROME_HISTORY_PATH || null,
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
      case "--json":
        parsed.json = true;
        break;
      case "--dry-run":
        parsed.dryRun = true;
        break;
      case "--first":
        parsed.first = true;
        break;
      case "--list-all":
        parsed.listAll = true;
        break;
      case "--include-devtools":
        parsed.includeDevtools = true;
        break;
      case "--type":
        parsed.type = argv[++index];
        break;
      case "--mode":
        parsed.mode = argv[++index];
        break;
      case "--value":
        parsed.value = argv[++index];
        break;
      case "--match":
        parsed.needle = argv[++index];
        break;
      case "--url":
        parsed.mode = "url";
        parsed.needle = argv[++index];
        break;
      case "--title":
        parsed.mode = "title";
        if (argv[index + 1] && !argv[index + 1].startsWith("--")) {
          parsed.needle = argv[++index];
        }
        break;
      case "--contains":
        parsed.mode = "contains";
        parsed.needle = argv[++index];
        break;
      case "--only":
        parsed.only = argv[++index];
        break;
      case "--limit":
        parsed.limit = Number(argv[++index]);
        break;
      case "--since":
        parsed.since = argv[++index];
        break;
      case "--sort":
        parsed.sort = argv[++index];
        break;
      case "--profile-dir":
        parsed.profileDir = argv[++index];
        break;
      case "--bookmarks-path":
        parsed.bookmarksPath = argv[++index];
        break;
      case "--history-path":
        parsed.historyPath = argv[++index];
        break;
      case "--help":
      case "-h":
        parsed.help = true;
        break;
      default:
        if (!token.startsWith("--") && !parsed.needle) {
          parsed.needle = token;
        } else {
          throw new Error(`Unknown argument: ${token}`);
        }
        break;
    }
  }

  return parsed;
}

function resolveEndpoint(parsed) {
  if (parsed.endpoint) {
    const normalized = /^https?:\/\//i.test(parsed.endpoint) ? parsed.endpoint : `http://${parsed.endpoint}`;
    const url = new URL(normalized);
    return {
      base: normalized.replace(/\/+$/, ""),
      host: url.hostname,
      port: Number(url.port || (url.protocol === "https:" ? "443" : "80")),
    };
  }

  return {
    base: `http://${parsed.host}:${parsed.port}`,
    host: parsed.host,
    port: parsed.port,
  };
}

function assertAllowedHost(host) {
  const localHosts = new Set(["127.0.0.1", "localhost", "::1"]);
  if (!localHosts.has(host) && process.env.WEB_ACCESS_ALLOW_REMOTE !== "1") {
    throw new Error(`Refusing remote host ${host}; set WEB_ACCESS_ALLOW_REMOTE=1 to override.`);
  }
}

async function listTargets(baseUrl, host) {
  assertAllowedHost(host);
  let response;
  try {
    response = await fetch(`${baseUrl}/json/list`, {
      signal: AbortSignal.timeout(2000),
    });
  } catch (error) {
    throw new Error(
      `Failed to reach CDP list endpoint at ${baseUrl}/json/list: ${
        error instanceof Error ? error.message : "unknown_error"
      }`,
    );
  }

  if (!response.ok) {
    throw new Error(`Failed to fetch targets: HTTP ${response.status}`);
  }

  return response.json();
}

function splitNeedle(needle) {
  return String(needle || "")
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
}

function genericMatch(title, url, parsed) {
  if (parsed.listAll || !parsed.needle) {
    return true;
  }

  const bundle = `${title}\n${url}`;
  switch (parsed.mode) {
    case "url":
      return url === parsed.needle || url.includes(parsed.needle);
    case "title":
      return title.includes(parsed.needle);
    case "exact":
      return url === parsed.needle || title === parsed.needle || bundle === parsed.needle;
    case "prefix":
      return url.startsWith(parsed.needle) || title.startsWith(parsed.needle);
    case "host":
      try {
        return new URL(url).host === parsed.needle;
      } catch {
        return false;
      }
    case "regex":
      return new RegExp(parsed.needle, "i").test(bundle);
    case "contains":
    default: {
      const terms = splitNeedle(parsed.needle);
      if (terms.length === 0) {
        return true;
      }
      const lowered = bundle.toLowerCase();
      return terms.every((term) => lowered.includes(term));
    }
  }
}

function matchesTarget(target, parsed) {
  if (parsed.type && target.type !== parsed.type) {
    return false;
  }
  if (!parsed.includeDevtools && String(target.url || "").startsWith("devtools://")) {
    return false;
  }
  return genericMatch(String(target.title || ""), String(target.url || ""), parsed);
}

function formatItem(item, value) {
  if (value === "json") {
    return JSON.stringify(item);
  }
  if (value === "summary") {
    const parts = [item.source || "item"];
    if (item.id) parts.push(item.id);
    if (item.type) parts.push(item.type);
    parts.push(item.title || "");
    parts.push(item.url || "");
    return parts.join("\t");
  }
  return item[value] ?? "";
}

function chromeUserDataCandidates() {
  const home = os.homedir();
  switch (process.platform) {
    case "darwin":
      return [
        path.join(home, "Library/Application Support/Google/Chrome"),
        path.join(home, "Library/Application Support/Chromium"),
        path.join(home, "Library/Application Support/BraveSoftware/Brave-Browser"),
      ];
    case "win32": {
      const local = process.env.LOCALAPPDATA || path.join(home, "AppData/Local");
      return [
        path.join(local, "Google/Chrome/User Data"),
        path.join(local, "Chromium/User Data"),
        path.join(local, "BraveSoftware/Brave-Browser/User Data"),
      ];
    }
    default:
      return [
        path.join(home, ".config/google-chrome"),
        path.join(home, ".config/chromium"),
        path.join(home, ".config/BraveSoftware/Brave-Browser"),
      ];
  }
}

function resolveProfileDirs(parsed) {
  if (parsed.profileDir) {
    return [path.resolve(parsed.profileDir)];
  }

  const profileDirs = [];
  for (const root of chromeUserDataCandidates()) {
    if (!fs.existsSync(root)) continue;
    let entries = [];
    try {
      entries = fs.readdirSync(root, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      if (entry.name === "Default" || /^Profile \d+$/.test(entry.name) || entry.name === "Guest Profile") {
        profileDirs.push(path.join(root, entry.name));
      }
    }
  }
  return [...new Set(profileDirs)];
}

function resolveBookmarkPaths(parsed) {
  if (parsed.bookmarksPath) {
    return [path.resolve(parsed.bookmarksPath)];
  }
  return resolveProfileDirs(parsed)
    .map((profileDir) => path.join(profileDir, "Bookmarks"))
    .filter((file) => fs.existsSync(file));
}

function resolveHistoryPaths(parsed) {
  if (parsed.historyPath) {
    return [path.resolve(parsed.historyPath)];
  }
  return resolveProfileDirs(parsed)
    .map((profileDir) => path.join(profileDir, "History"))
    .filter((file) => fs.existsSync(file));
}

function collectBookmarkNodes(node, profileName, bucket = [], folder = null) {
  if (!node || typeof node !== "object") {
    return bucket;
  }
  if (node.type === "url") {
    bucket.push({
      source: "bookmark",
      title: node.name || "",
      url: node.url || "",
      addedAt: node.date_added || null,
      profile: profileName,
      folder,
    });
    return bucket;
  }
  const children = Array.isArray(node.children) ? node.children : [];
  for (const child of children) {
    collectBookmarkNodes(child, profileName, bucket, node.name || folder);
  }
  return bucket;
}

function chromeMicrosToIso(value) {
  const micros = Number(value || 0);
  if (!Number.isFinite(micros) || micros <= 0) return null;
  const unixMs = micros / 1000 - 11644473600000;
  return new Date(unixMs).toISOString();
}

function loadBookmarks(parsed) {
  const items = [];
  for (const bookmarksPath of resolveBookmarkPaths(parsed)) {
    try {
      const profileName = path.basename(path.dirname(bookmarksPath));
      const raw = JSON.parse(fs.readFileSync(bookmarksPath, "utf8"));
      const roots = raw.roots || {};
      for (const key of Object.keys(roots)) {
        collectBookmarkNodes(roots[key], profileName, items);
      }
    } catch {
      continue;
    }
  }
  return items.map((item) => ({
    source: "bookmark",
    title: item.title,
    url: item.url,
    profile: item.profile,
    folder: item.folder,
    addedAt: chromeMicrosToIso(item.addedAt),
  }));
}

function parseSince(spec) {
  if (!spec) return null;
  if (/^\d+[dhm]$/.test(spec)) {
    const value = Number(spec.slice(0, -1));
    const unit = spec.slice(-1);
    const factors = { m: 60_000, h: 3_600_000, d: 86_400_000 };
    return Date.now() - value * factors[unit];
  }
  const timestamp = Date.parse(spec);
  if (Number.isNaN(timestamp)) {
    throw new Error(`Invalid --since value: ${spec}`);
  }
  return timestamp;
}

function loadHistory(parsed) {
  const historyPaths = resolveHistoryPaths(parsed);
  if (historyPaths.length === 0) {
    return [];
  }
  const sinceMs = parseSince(parsed.since);
  const pythonProgram = String.raw`import json, os, shutil, sqlite3, sys, tempfile
payload = json.loads(sys.argv[1])
rows = []
for history_path in payload['paths']:
    if not os.path.exists(history_path):
        continue
    profile = os.path.basename(os.path.dirname(history_path))
    fd, tmp = tempfile.mkstemp(prefix='web-access-history-', suffix='.sqlite3')
    os.close(fd)
    try:
        shutil.copy2(history_path, tmp)
        conn = sqlite3.connect(tmp)
        conn.row_factory = sqlite3.Row
        query = """
            SELECT url, title, visit_count, last_visit_time
            FROM urls
            ORDER BY last_visit_time DESC
            LIMIT 5000
        """
        for row in conn.execute(query):
            last_visit_time = row['last_visit_time'] or 0
            unix_ms = last_visit_time / 1000 - 11644473600000 if last_visit_time else None
            if payload['sinceMs'] and unix_ms and unix_ms < payload['sinceMs']:
                continue
            rows.append({
                'source': 'history',
                'profile': profile,
                'title': row['title'] or '',
                'url': row['url'] or '',
                'visitCount': row['visit_count'] or 0,
                'lastVisitedAt': unix_ms,
                'lastVisitedIso': None if unix_ms is None else __import__('datetime').datetime.utcfromtimestamp(unix_ms / 1000).isoformat() + 'Z',
            })
        conn.close()
    except Exception:
        pass
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
print(json.dumps(rows, ensure_ascii=False))`;
  const result = spawnSync("python3", ["-c", pythonProgram, JSON.stringify({ paths: historyPaths, sinceMs })], {
    encoding: "utf8",
  });
  if (result.status !== 0) {
    throw new Error(result.stderr?.trim() || "Failed to query Chrome history with python3.");
  }
  const rows = JSON.parse(result.stdout || "[]");
  if (parsed.sort === "visits") {
    rows.sort((a, b) => (b.visitCount || 0) - (a.visitCount || 0) || (b.lastVisitedAt || 0) - (a.lastVisitedAt || 0));
  } else {
    rows.sort((a, b) => (b.lastVisitedAt || 0) - (a.lastVisitedAt || 0));
  }
  return rows;
}

function matchResource(item, parsed) {
  return genericMatch(String(item.title || ""), String(item.url || ""), parsed);
}

function collectSources(parsed) {
  switch (parsed.only) {
    case "targets":
      return ["targets"];
    case "bookmarks":
      return ["bookmarks"];
    case "history":
      return ["history"];
    case "chrome":
      return ["bookmarks", "history"];
    case "all":
      return ["targets", "bookmarks", "history"];
    default:
      throw new Error(`Invalid --only value: ${parsed.only}`);
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

const sources = collectSources(options);
const endpoint = resolveEndpoint(options);
if (options.dryRun) {
  const payload = {
    ok: true,
    dryRun: true,
    sources,
    endpoint: sources.includes("targets")
      ? {
          requestUrl: `${endpoint.base}/json/list`,
          host: endpoint.host,
          port: endpoint.port,
        }
      : null,
    chrome: sources.some((source) => source !== "targets")
      ? {
          profileDirs: resolveProfileDirs(options),
          bookmarksPaths: resolveBookmarkPaths(options),
          historyPaths: resolveHistoryPaths(options),
          since: options.since,
          sort: options.sort,
          limit: options.limit,
        }
      : null,
    mode: options.mode,
    type: options.type,
    match: options.needle,
    value: options.value,
  };
  console.log(JSON.stringify(payload, null, 2));
  process.exit(0);
}

try {
  const matches = [];

  if (sources.includes("targets")) {
    const targets = await listTargets(endpoint.base, endpoint.host);
    for (const target of targets) {
      if (!matchesTarget(target, options)) continue;
      matches.push({
        source: "target",
        id: target.id,
        type: target.type,
        title: target.title,
        url: target.url,
        webSocketDebuggerUrl: target.webSocketDebuggerUrl || null,
        attached: Boolean(target.webSocketDebuggerUrl),
      });
    }
  }

  if (sources.includes("bookmarks")) {
    for (const item of loadBookmarks(options).filter((item) => matchResource(item, options))) {
      matches.push(item);
    }
  }

  if (sources.includes("history")) {
    for (const item of loadHistory(options).filter((item) => matchResource(item, options))) {
      matches.push(item);
    }
  }

  const limited = options.first ? matches.slice(0, 1) : matches.slice(0, Math.max(1, options.limit));
  if (options.json) {
    console.log(JSON.stringify(limited, null, 2));
  } else if (limited.length === 0) {
    console.log("No matching results.");
  } else {
    for (const item of limited) {
      console.log(formatItem(item, options.value));
    }
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
