#!/usr/bin/env node
/**
 * 搜索聚合器：按优先级轮询多个搜索后端，返回第一个成功的结果。
 * 后端顺序：Brave → Tavily → Google CSE → Bing → SerpAPI → DuckDuckGo HTML
 * 用法：node scripts/search-aggregator.mjs "query" [--count 5] [--json] [--preset small]
 */

import { execFileSync } from "node:child_process";

const DEFAULT_COUNT = 5;
const TIMEOUT_MS = 8000;
const PRESET_MAP = { small: 3, medium: 5, large: 10, extra: 20 };

function log(s) { if (process.env.WEB_ACCESS_QUIET !== "1") console.error(`[search] ${s}`); }

function parseArgs(argv) {
  const parsed = { query: "", count: DEFAULT_COUNT, json: false, backend: null };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t === "--count") parsed.count = Number(argv[++i]);
    else if (t === "--json") parsed.json = true;
    else if (t === "--backend") parsed.backend = argv[++i];
    else if (t === "--preset") {
      const preset = argv[++i];
      parsed.count = PRESET_MAP[preset] ?? DEFAULT_COUNT;
    }
    else if (!parsed.query) parsed.query = t;
  }
  return parsed;
}

function normalizeResults(source, raw, count) {
  const results = [];
  if (source === "brave" && raw.results) {
    for (const r of raw.results.slice(0, count)) {
      results.push({ title: r.title, url: r.url, description: r.description, age: r.age });
    }
  } else if (source === "tavily" && raw.results) {
    for (const r of raw.results.slice(0, count)) {
      results.push({ title: r.title, url: r.url, description: r.content, score: r.score, raw_content: r.raw_content });
    }
  } else if (source === "google_cse" && raw.items) {
    for (const r of raw.items.slice(0, count)) {
      results.push({ title: r.title, url: r.link, description: r.snippet, age: null });
    }
  } else if (source === "bing" && raw.webPages?.value) {
    for (const r of raw.webPages.value.slice(0, count)) {
      results.push({ title: r.name, url: r.url, description: r.snippet, age: r.dateLastCrawled });
    }
  } else if (source === "serpapi" && raw.organic_results) {
    for (const r of raw.organic_results.slice(0, count)) {
      results.push({ title: r.title, url: r.link, description: r.snippet, age: r.date });
    }
  } else if (source === "duckduckgo" && raw.links) {
    for (const r of raw.links.slice(0, count)) {
      results.push({ title: r.title, url: r.url, description: null, age: null });
    }
  }
  return results;
}

function braveSearch(query, count) {
  const key = process.env.BRAVE_SEARCH_API_KEY;
  if (!key) return null;
  try {
    const out = execFileSync(process.execPath, [
      new URL("./brave-search.mjs", import.meta.url).pathname,
      query, "--count", String(count), "--json"
    ], { encoding: "utf-8", timeout: TIMEOUT_MS, env: { ...process.env, WEB_ACCESS_QUIET: "1" } });
    const data = JSON.parse(out);
    return { source: "brave", data: { query, results: normalizeResults("brave", data, count) } };
  } catch { return null; }
}

async function tavilySearch(query, count) {
  const key = process.env.TAVILY_API_KEY;
  if (!key) return null;
  try {
    const res = await fetch("https://api.tavily.com/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: key,
        query,
        max_results: count,
        search_depth: "basic",
        include_answer: false,
      }),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return { source: "tavily", data: { query, answer: data.answer || null, results: normalizeResults("tavily", data, count) } };
  } catch { return null; }
}

async function googleCse(query, count) {
  const key = process.env.GOOGLE_CSE_API_KEY;
  const cx = process.env.GOOGLE_CSE_ID;
  if (!key || !cx) return null;
  try {
    const url = `https://customsearch.googleapis.com/customsearch/v1?key=${encodeURIComponent(key)}&cx=${encodeURIComponent(cx)}&q=${encodeURIComponent(query)}&num=${count}`;
    const res = await fetch(url, { signal: AbortSignal.timeout(TIMEOUT_MS) });
    if (!res.ok) return null;
    const data = await res.json();
    return { source: "google_cse", data: { query, results: normalizeResults("google_cse", data, count) } };
  } catch { return null; }
}

async function bingSearch(query, count) {
  const key = process.env.BING_API_KEY;
  if (!key) return null;
  try {
    const url = `https://api.bing.microsoft.com/v7.0/search?q=${encodeURIComponent(query)}&count=${count}`;
    const res = await fetch(url, {
      headers: { "Ocp-Apim-Subscription-Key": key },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return { source: "bing", data: { query, results: normalizeResults("bing", data, count) } };
  } catch { return null; }
}

async function serpApi(query, count) {
  const key = process.env.SERPAPI_KEY;
  if (!key) return null;
  try {
    const url = `https://serpapi.com/search?api_key=${encodeURIComponent(key)}&engine=google&q=${encodeURIComponent(query)}&num=${count}`;
    const res = await fetch(url, { signal: AbortSignal.timeout(TIMEOUT_MS) });
    if (!res.ok) return null;
    const data = await res.json();
    return { source: "serpapi", data: { query, results: normalizeResults("serpapi", data, count) } };
  } catch { return null; }
}

async function duckDuckGo(query, count) {
  try {
    const res = await fetch(`https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`, {
      signal: AbortSignal.timeout(TIMEOUT_MS),
      headers: { "User-Agent": "Mozilla/5.0" },
    });
    if (!res.ok) return null;
    const html = await res.text();
    const links = [];
    const re = /class="result__a" href="([^"]+)"[^>]*>([^<]+)/g;
    let m;
    while ((m = re.exec(html)) && links.length < count) {
      links.push({ title: m[2].replace(/&amp;/g, "&"), url: m[1] });
    }
    return links.length ? { source: "duckduckgo", data: { query, results: normalizeResults("duckduckgo", { links }, count) } } : null;
  } catch { return null; }
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts.query) {
    console.error("Usage: search-aggregator.mjs <query> [--count N] [--json] [--preset small|medium|large|extra] [--backend brave|tavily|google_cse|bing|serpapi|duckduckgo]");
    process.exit(1);
  }

  const backendMap = {
    brave: () => braveSearch(opts.query, opts.count),
    tavily: () => tavilySearch(opts.query, opts.count),
    google_cse: () => googleCse(opts.query, opts.count),
    bing: () => bingSearch(opts.query, opts.count),
    serpapi: () => serpApi(opts.query, opts.count),
    duckduckgo: () => duckDuckGo(opts.query, opts.count),
  };

  let backends;
  if (opts.backend) {
    const chosen = backendMap[opts.backend];
    if (!chosen) {
      console.error(`Unknown backend: ${opts.backend}. Available: ${Object.keys(backendMap).join(", ")}`);
      process.exit(1);
    }
    backends = [chosen];
  } else {
    backends = Object.values(backendMap);
  }

  for (const backend of backends) {
    const result = await backend();
    if (result) {
      if (opts.json) {
        console.log(JSON.stringify({ ok: true, source: result.source, results: result.data }, null, 2));
      } else {
        console.log(`source=${result.source}`);
        console.log(JSON.stringify(result.data, null, 2));
      }
      return;
    }
  }

  const fail = { ok: false, reason: opts.backend ? `${opts.backend}_failed` : "all_backends_failed", query: opts.query };
  console.log(opts.json ? JSON.stringify(fail, null, 2) : `Failed: ${fail.reason}`);
  process.exit(2);
}

main().catch(e => { log(`Fatal: ${e.message}`); process.exit(2); });
