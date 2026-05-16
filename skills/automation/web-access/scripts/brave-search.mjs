#!/usr/bin/env node

/**
 * 调用 Brave Search API 做可编程 Web 搜索。
 * 默认读取 BRAVE_SEARCH_API_KEY；`--dry-run` 只打印计划，不发请求。
 */

const DEFAULT_ENDPOINT =
  process.env.BRAVE_SEARCH_API_ENDPOINT || "https://api.search.brave.com/res/v1/web/search";

function printHelp() {
  console.log(`Usage:
  node scripts/brave-search.mjs <query> [options]

Options:
  --api-key <key>          Explicit Brave API key, default BRAVE_SEARCH_API_KEY
  --endpoint <url>         Search endpoint, default BRAVE_SEARCH_API_ENDPOINT or official web endpoint
  --count <n>              Result count, default 5
  --country <code>         Country hint, e.g. US
  --search-lang <code>     Search language, e.g. en
  --freshness <range>      Freshness hint, e.g. pd/pw/pm/py
  --json                   Emit normalized JSON
  --raw                    Emit raw API payload
  --dry-run                Print planned request without fetching
  --help                   Show this help
`);
}

function parseArgs(argv) {
  const parsed = {
    apiKey: process.env.BRAVE_SEARCH_API_KEY || null,
    endpoint: DEFAULT_ENDPOINT,
    count: 5,
    country: null,
    searchLang: null,
    freshness: null,
    json: false,
    raw: false,
    dryRun: false,
    help: false,
    query: null,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    switch (token) {
      case "--api-key":
        parsed.apiKey = argv[++index];
        break;
      case "--endpoint":
        parsed.endpoint = argv[++index];
        break;
      case "--count":
        parsed.count = Number(argv[++index]);
        break;
      case "--country":
        parsed.country = argv[++index];
        break;
      case "--search-lang":
        parsed.searchLang = argv[++index];
        break;
      case "--freshness":
        parsed.freshness = argv[++index];
        break;
      case "--json":
        parsed.json = true;
        break;
      case "--raw":
        parsed.raw = true;
        break;
      case "--dry-run":
        parsed.dryRun = true;
        break;
      case "--help":
      case "-h":
        parsed.help = true;
        break;
      default:
        if (!token.startsWith("--") && !parsed.query) {
          parsed.query = token;
        } else {
          throw new Error(`Unknown argument: ${token}`);
        }
        break;
    }
  }

  return parsed;
}

function buildRequestUrl(options) {
  const url = new URL(options.endpoint);
  url.searchParams.set("q", options.query);
  url.searchParams.set("count", String(options.count));
  if (options.country) {
    url.searchParams.set("country", options.country);
  }
  if (options.searchLang) {
    url.searchParams.set("search_lang", options.searchLang);
  }
  if (options.freshness) {
    url.searchParams.set("freshness", options.freshness);
  }
  return url;
}

function normalizeResult(item, index) {
  return {
    rank: index + 1,
    title: item.title || item.meta_title || "",
    url: item.url || item.link || "",
    description: item.description || item.snippet || "",
    age: item.age || item.page_age || null,
    language: item.language || null,
  };
}

function printText(payload) {
  if (payload.results.length === 0) {
    console.log("No results.");
    return;
  }

  for (const result of payload.results) {
    console.log(`${result.rank}. ${result.title}`);
    console.log(`   ${result.url}`);
    if (result.description) {
      console.log(`   ${result.description}`);
    }
    if (result.age) {
      console.log(`   age=${result.age}`);
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

if (!options.query) {
  console.error("Missing search query.");
  printHelp();
  process.exit(1);
}

if (!Number.isFinite(options.count) || options.count <= 0) {
  console.error("--count must be a positive number.");
  process.exit(1);
}

const requestUrl = buildRequestUrl(options);

if (options.dryRun) {
  console.log(
    JSON.stringify(
      {
        ok: true,
        dryRun: true,
        endpoint: options.endpoint,
        requestUrl: requestUrl.toString(),
        hasApiKey: Boolean(options.apiKey),
        count: options.count,
      },
      null,
      2,
    ),
  );
  process.exit(0);
}

if (!options.apiKey) {
  console.error("Missing Brave API key. Set BRAVE_SEARCH_API_KEY or pass --api-key.");
  process.exit(2);
}

let response;
try {
  response = await fetch(requestUrl, {
    headers: {
      Accept: "application/json",
      "Accept-Encoding": "gzip",
      "X-Subscription-Token": options.apiKey,
    },
    signal: AbortSignal.timeout(5000),
  });
} catch (error) {
  console.error(error instanceof Error ? error.message : "Failed to reach Brave Search API.");
  process.exit(3);
}

if (!response.ok) {
  const body = await response.text().catch(() => "");
  console.error(`Brave Search API error: HTTP ${response.status}${body ? ` ${body}` : ""}`);
  process.exit(4);
}

const payload = await response.json();
if (options.raw) {
  console.log(JSON.stringify(payload, null, 2));
  process.exit(0);
}

const results = Array.isArray(payload?.web?.results)
  ? payload.web.results
  : Array.isArray(payload?.results)
    ? payload.results
    : [];

const normalized = {
  query: options.query,
  endpoint: options.endpoint,
  total: results.length,
  results: results.map(normalizeResult),
};

if (options.json) {
  console.log(JSON.stringify(normalized, null, 2));
} else {
  printText(normalized);
}
