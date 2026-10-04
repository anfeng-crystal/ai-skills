#!/usr/bin/env node

/**
 * 查找当前 CDP targets，或检索本地 Chrome 书签/历史。
 * 保留旧参数，并新增 `--only/--limit/--since/--sort`。
 */

import { resolveProfileDirs, resolveBookmarkPaths, resolveHistoryPaths, loadBookmarks, loadHistory } from "./find-url-sources.mjs";
import { parseFindOptions, resolveHttpEndpoint, assertAllowedHost, reportCliError } from "./cdp-cli-options.mjs";

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

const args = process.argv.slice(2);
try {
  const options = parseFindOptions(args);

  if (options.help) {
    printHelp();
    process.exit(0);
  }

  const sources = collectSources(options);
  const endpoint = sources.includes("targets") ? resolveHttpEndpoint(options) : null;
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

  const matches = [];
  const errors = [];
  let successfulSources = 0;

  if (sources.includes("targets")) {
    const targets = await listTargets(endpoint.base, endpoint.host);
    successfulSources += 1;
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

  for (const [source, loader] of [["bookmarks", loadBookmarks], ["history", loadHistory]]) {
    if (!sources.includes(source)) continue;
    const result = loader(options);
    errors.push(...result.errors);
    successfulSources += result.successfulSources;
    matches.push(...result.items.filter((item) => matchResource(item, options)));
  }

  const limited = options.first ? matches.slice(0, 1) : matches.slice(0, Math.max(1, options.limit));
  if (errors.length > 0) {
    process.exitCode = 1;
    const error = "Failed to read one or more selected local sources.";
    if (options.json) {
      console.log(JSON.stringify({ ok: false, command: "find-url", error,
        partial: successfulSources > 0, errors, results: limited }, null, 2));
    } else {
      console.error(error);
      for (const failure of errors) console.error(`${failure.source}: ${failure.code}${failure.path ? ` (${failure.path})` : ""}`);
      for (const item of limited) console.log(formatItem(item, options.value));
    }
  } else if (options.json) {
    console.log(JSON.stringify(limited, null, 2));
  } else if (limited.length === 0) {
    console.log("No matching results.");
  } else {
    for (const item of limited) {
      console.log(formatItem(item, options.value));
    }
  }
} catch (error) {
  reportCliError(error, args.includes("--json"), "find-url");
}
