import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

import type { SearchMcpConfig, FetchProvider, FetchRequest, FetchResult, ProviderStatus, SearchProvider, SearchRequest, SearchResult } from "./types.js";
import { ProviderError } from "./errors.js";
import { requestJson, requestText } from "./http.js";
import { KeyLease, KeyPool } from "./key-pool.js";
import { canonicalizeUrl, domainOf, evidenceFromText, extractTitle, htmlToText, trimText } from "./text.js";

abstract class KeyedProvider {
  protected lastErrorType: string | undefined;

  constructor(
    public readonly name: string,
    protected readonly timeoutMs: number,
    protected readonly pool: KeyPool,
  ) {}

  configured(): boolean {
    return this.pool.size > 0;
  }

  status(): ProviderStatus {
    return {
      enabled: true,
      configured: this.configured(),
      ...this.pool.status(),
      lastErrorType: this.lastErrorType,
    };
  }

  protected async withKey<T>(operation: (key: string, lease: KeyLease) => Promise<T>): Promise<T> {
    const attempts = Math.max(1, this.pool.size);
    let lastError: unknown = new ProviderError(this.name, "not_configured", `${this.name} has no API key`);
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      const lease = this.pool.next();
      if (!lease) {
        break;
      }
      try {
        const result = await operation(lease.value, lease);
        this.lastErrorType = undefined;
        return result;
      } catch (error) {
        lastError = error;
        this.lastErrorType = error instanceof ProviderError ? error.type : "unknown";
        if (error instanceof ProviderError && (error.type === "unauthorized" || error.type === "quota_exhausted" || error.type === "rate_limited")) {
          continue;
        }
        break;
      }
    }
    throw lastError;
  }

  protected rateLimit = (lease: KeyLease, retryAfterMs: number): void => {
    this.pool.cooldown(lease, retryAfterMs);
  };

  protected unauthorized = (lease: KeyLease): void => {
    this.pool.disable(lease, "unauthorized");
  };

  protected quotaExhausted = (lease: KeyLease): void => {
    this.pool.disable(lease, "quota_exhausted");
  };
}

export class BraveSearchProvider extends KeyedProvider implements SearchProvider {
  readonly kind = "search" as const;

  async search(request: Required<SearchRequest>): Promise<SearchResult[]> {
    return this.withKey(async (key, lease) => {
      const query = decorateQuery(request.query, request.sites, request.exclude_sites);
      const url = new URL("https://api.search.brave.com/res/v1/web/search");
      url.searchParams.set("q", query);
      url.searchParams.set("count", String(request.max_results));
      if (request.freshness) {
        url.searchParams.set("freshness", request.freshness);
      }
      const payload = await requestJson<{ web?: { results?: Array<Record<string, unknown>> } }>({
        provider: this.name,
        url: url.toString(),
        timeoutMs: this.timeoutMs,
        lease,
        onRateLimit: this.rateLimit,
        onUnauthorized: this.unauthorized,
        onQuotaExhausted: this.quotaExhausted,
        init: {
          headers: {
            Accept: "application/json",
            "X-Subscription-Token": key,
          },
        },
      });
      return (payload.web?.results ?? []).map((item, index) => ({
        title: String(item.title ?? item.url ?? ""),
        url: String(item.url ?? ""),
        snippet: String(item.description ?? item.extra_snippets ?? ""),
        source: "brave",
        score: 1 - index / 100,
        published: typeof item.age === "string" ? item.age : null,
      })).filter((item) => item.url);
    });
  }
}

export class ExaApiProvider extends KeyedProvider implements SearchProvider, FetchProvider {
  readonly kind = "search" as const;

  async search(request: Required<SearchRequest>): Promise<SearchResult[]> {
    return this.withKey(async (key, lease) => {
      const payload = await requestJson<{ results?: Array<Record<string, unknown>> }>({
        provider: this.name,
        url: "https://api.exa.ai/search",
        timeoutMs: this.timeoutMs,
        lease,
        onRateLimit: this.rateLimit,
        onUnauthorized: this.unauthorized,
        onQuotaExhausted: this.quotaExhausted,
        init: {
          method: "POST",
          headers: { "Content-Type": "application/json", "x-api-key": key },
          body: JSON.stringify({
            query: decorateQuery(request.query, request.sites, request.exclude_sites),
            numResults: request.max_results,
            contents: { highlights: true },
          }),
        },
      });
      return normalizeExaResults(payload.results ?? [], "exa");
    });
  }

  async fetch(request: Required<FetchRequest>): Promise<FetchResult> {
    return this.withKey(async (key, lease) => {
      const payload = await requestJson<{ results?: Array<Record<string, unknown>> }>({
        provider: this.name,
        url: "https://api.exa.ai/contents",
        timeoutMs: this.timeoutMs,
        lease,
        onRateLimit: this.rateLimit,
        onUnauthorized: this.unauthorized,
        onQuotaExhausted: this.quotaExhausted,
        init: {
          method: "POST",
          headers: { "Content-Type": "application/json", "x-api-key": key },
          body: JSON.stringify({
            urls: [request.url],
            text: { maxCharacters: request.max_chars },
            highlights: request.query ? { query: request.query } : true,
          }),
        },
      });
      const first = payload.results?.[0];
      if (!first) {
        throw new ProviderError(this.name, "extract_failed", "Exa returned no contents");
      }
      const text = String(first.text ?? (Array.isArray(first.highlights) ? first.highlights.join(" ") : ""));
      if (!text.trim()) {
        throw new ProviderError(this.name, "extract_failed", "Exa returned empty contents");
      }
      const evidence = evidenceFromText(text, request.query || String(first.title ?? request.url), request.max_chars);
      return {
        url: canonicalizeUrl(String(first.url ?? request.url)),
        title: trimText(String(first.title ?? request.url), 160),
        source: "exa",
        ...evidence,
      };
    });
  }
}

export class ExaTrialProvider implements SearchProvider, FetchProvider {
  readonly kind = "search" as const;
  private lastErrorType: string | undefined;

  constructor(public readonly name: string, private readonly mcpUrl: string, private readonly enabled: boolean) {}

  configured(): boolean {
    return this.enabled;
  }

  status(): ProviderStatus {
    return {
      enabled: this.enabled,
      configured: this.enabled,
      keyCount: 0,
      cooldownCount: 0,
      disabledCount: 0,
      lastErrorType: this.lastErrorType,
    };
  }

  async search(request: Required<SearchRequest>): Promise<SearchResult[]> {
    const result = await this.callTool("web_search_exa", {
      query: decorateQuery(request.query, request.sites, request.exclude_sites),
      numResults: request.max_results,
    });
    return parseExaTrialSearchResult(result, "exa_trial");
  }

  async fetch(request: Required<FetchRequest>): Promise<FetchResult> {
    const result = await this.callTool("web_fetch_exa", { urls: [request.url], query: request.query });
    const text = extractMcpText(result);
    if (!text.trim()) {
      throw new ProviderError(this.name, "extract_failed", "Exa trial returned empty contents");
    }
    const evidence = evidenceFromText(text, request.query || request.url, request.max_chars);
    return { url: canonicalizeUrl(request.url), title: request.url, source: "exa_trial", ...evidence };
  }

  private async callTool(name: string, args: Record<string, unknown>): Promise<unknown> {
    if (!this.enabled) {
      throw new ProviderError(this.name, "not_configured", "Exa trial provider is disabled");
    }
    const client = new Client({ name: "search-web-mcp", version: "0.1.0" });
    const transport = new StreamableHTTPClientTransport(new URL(this.mcpUrl));
    try {
      await client.connect(transport);
      const result = await client.callTool({ name, arguments: args });
      this.lastErrorType = undefined;
      return result;
    } catch (error) {
      this.lastErrorType = "network";
      throw new ProviderError(this.name, "network", error instanceof Error ? error.message : "Exa trial call failed");
    } finally {
      await transport.close().catch(() => undefined);
    }
  }
}

export class TavilyProvider extends KeyedProvider implements SearchProvider, FetchProvider {
  readonly kind = "search" as const;

  async search(request: Required<SearchRequest>): Promise<SearchResult[]> {
    return this.withKey(async (key, lease) => {
      const payload = await requestJson<{ results?: Array<Record<string, unknown>> }>({
        provider: this.name,
        url: "https://api.tavily.com/search",
        timeoutMs: this.timeoutMs,
        lease,
        onRateLimit: this.rateLimit,
        onUnauthorized: this.unauthorized,
        onQuotaExhausted: this.quotaExhausted,
        init: {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
          body: JSON.stringify({
            query: decorateQuery(request.query, request.sites, request.exclude_sites),
            max_results: request.max_results,
            search_depth: "basic",
            include_answer: false,
            include_raw_content: false,
          }),
        },
      });
      return (payload.results ?? []).map((item, index) => ({
        title: String(item.title ?? item.url ?? ""),
        url: String(item.url ?? ""),
        snippet: String(item.content ?? ""),
        source: "tavily",
        score: Number(item.score ?? 1 - index / 100),
        published: null,
      })).filter((item) => item.url);
    });
  }

  async fetch(request: Required<FetchRequest>): Promise<FetchResult> {
    return this.withKey(async (key, lease) => {
      const payload = await requestJson<{ results?: Array<Record<string, unknown>> }>({
        provider: this.name,
        url: "https://api.tavily.com/extract",
        timeoutMs: this.timeoutMs,
        lease,
        onRateLimit: this.rateLimit,
        onUnauthorized: this.unauthorized,
        onQuotaExhausted: this.quotaExhausted,
        init: {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
          body: JSON.stringify({ urls: [request.url], extract_depth: "basic" }),
        },
      });
      const first = payload.results?.[0];
      const text = String(first?.raw_content ?? first?.content ?? "");
      if (!text.trim()) {
        throw new ProviderError(this.name, "extract_failed", "Tavily returned empty contents");
      }
      const evidence = evidenceFromText(text, request.query || request.url, request.max_chars);
      return { url: canonicalizeUrl(String(first?.url ?? request.url)), title: request.url, source: "tavily", ...evidence };
    });
  }
}

export class FirecrawlProvider extends KeyedProvider implements FetchProvider {
  readonly kind = "fetch" as const;

  async fetch(request: Required<FetchRequest>): Promise<FetchResult> {
    return this.withKey(async (key, lease) => {
      const payload = await requestJson<Record<string, unknown>>({
        provider: this.name,
        url: "https://api.firecrawl.dev/v2/scrape",
        timeoutMs: this.timeoutMs,
        lease,
        onRateLimit: this.rateLimit,
        onUnauthorized: this.unauthorized,
        onQuotaExhausted: this.quotaExhausted,
        init: {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
          body: JSON.stringify({ url: request.url, formats: ["markdown"], onlyMainContent: true }),
        },
      });
      const data = (payload.data ?? payload) as Record<string, unknown>;
      const text = String(data.markdown ?? data.content ?? "");
      if (!text.trim()) {
        throw new ProviderError(this.name, "extract_failed", "Firecrawl returned empty contents");
      }
      const evidence = evidenceFromText(text, request.query || request.url, request.max_chars);
      return {
        url: canonicalizeUrl(String(data.url ?? request.url)),
        title: trimText(String(data.title ?? request.url), 160),
        source: "firecrawl",
        ...evidence,
      };
    });
  }
}

export class DuckDuckGoProvider implements SearchProvider {
  readonly name = "duckduckgo";
  readonly kind = "search" as const;
  private lastErrorType: string | undefined;

  constructor(private readonly timeoutMs: number) {}

  configured(): boolean {
    return true;
  }

  status(): ProviderStatus {
    return { enabled: true, configured: true, keyCount: 0, cooldownCount: 0, disabledCount: 0, lastErrorType: this.lastErrorType };
  }

  async search(request: Required<SearchRequest>): Promise<SearchResult[]> {
    const query = decorateQuery(request.query, request.sites, request.exclude_sites);
    const url = `https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`;
    try {
      const html = await requestText(url, { headers: { "User-Agent": "Mozilla/5.0 search-web-mcp" } }, this.timeoutMs);
      const results = parseDuckDuckGo(html, request.max_results);
      this.lastErrorType = undefined;
      return results;
    } catch (error) {
      this.lastErrorType = error instanceof ProviderError ? error.type : "network";
      throw error;
    }
  }
}

export class SearxngProvider implements SearchProvider {
  readonly name = "searxng";
  readonly kind = "search" as const;
  private lastErrorType: string | undefined;

  constructor(private readonly baseUrl: string | undefined, private readonly timeoutMs: number) {}

  configured(): boolean {
    return Boolean(this.baseUrl);
  }

  status(): ProviderStatus {
    return { enabled: true, configured: this.configured(), keyCount: 0, cooldownCount: 0, disabledCount: 0, lastErrorType: this.lastErrorType };
  }

  async search(request: Required<SearchRequest>): Promise<SearchResult[]> {
    if (!this.baseUrl) {
      throw new ProviderError(this.name, "not_configured", "SearXNG URL is not configured");
    }
    const url = new URL("/search", this.baseUrl.endsWith("/") ? this.baseUrl : `${this.baseUrl}/`);
    url.searchParams.set("q", decorateQuery(request.query, request.sites, request.exclude_sites));
    url.searchParams.set("format", "json");
    const payload = await requestJson<{ results?: Array<Record<string, unknown>> }>({
      provider: this.name,
      url: url.toString(),
      timeoutMs: this.timeoutMs,
    });
    return (payload.results ?? []).slice(0, request.max_results).map((item, index) => ({
      title: String(item.title ?? item.url ?? ""),
      url: String(item.url ?? ""),
      snippet: String(item.content ?? ""),
      source: "searxng",
      score: Number(item.score ?? 1 - index / 100),
      published: typeof item.publishedDate === "string" ? item.publishedDate : null,
    })).filter((item) => item.url);
  }
}

export class LocalFetchProvider implements FetchProvider {
  readonly name = "local";
  readonly kind = "fetch" as const;
  private lastErrorType: string | undefined;

  constructor(private readonly timeoutMs: number) {}

  configured(): boolean {
    return true;
  }

  status(): ProviderStatus {
    return { enabled: true, configured: true, keyCount: 0, cooldownCount: 0, disabledCount: 0, lastErrorType: this.lastErrorType };
  }

  async fetch(request: Required<FetchRequest>): Promise<FetchResult> {
    try {
      const html = await requestText(request.url, { headers: { "User-Agent": "Mozilla/5.0 search-web-mcp" } }, this.timeoutMs);
      const text = htmlToText(html);
      if (text.length < 80) {
        throw new ProviderError(this.name, "extract_failed", "local extraction returned too little text");
      }
      const evidence = evidenceFromText(text, request.query || request.url, request.max_chars);
      this.lastErrorType = undefined;
      return { url: canonicalizeUrl(request.url), title: extractTitle(html, request.url), source: "local", ...evidence };
    } catch (error) {
      this.lastErrorType = error instanceof ProviderError ? error.type : "extract_failed";
      throw error;
    }
  }
}

class DisabledProvider implements SearchProvider, FetchProvider {
  readonly kind = "both" as const;

  constructor(public readonly name: string) {}

  configured(): boolean {
    return false;
  }

  status(): ProviderStatus {
    return {
      enabled: false,
      configured: false,
      keyCount: 0,
      cooldownCount: 0,
      disabledCount: 0,
    };
  }

  async search(): Promise<SearchResult[]> {
    throw new ProviderError(this.name, "not_configured", `${this.name} is disabled`);
  }

  async fetch(): Promise<FetchResult> {
    throw new ProviderError(this.name, "not_configured", `${this.name} is disabled`);
  }
}

export function buildProviders(config: SearchMcpConfig): { searchProviders: SearchProvider[]; fetchProviders: FetchProvider[] } {
  const exaApi = new ExaApiProvider("exa", config.timeoutMs, new KeyPool("exa", config.keys.exa));
  const exaTrial = new ExaTrialProvider("exa_trial", config.exa.trialMcpUrl, config.exa.mode === "trial" || (config.exa.mode === "auto" && config.keys.exa.length === 0 && config.exa.trialEnabled));
  const exaDisabled = new DisabledProvider("exa");
  const exaApiDisabled = new DisabledProvider("exa_api");
  const exaTrialDisabled = new DisabledProvider("exa_trial");
  const exaAlias = selectExaProvider(config, exaApi, exaTrial, exaDisabled);
  const exaApiProvider = config.exa.mode === "off" ? exaApiDisabled : exaApi;
  const exaTrialProvider = config.exa.mode === "off" ? exaTrialDisabled : exaTrial;
  const searchMap: Record<string, SearchProvider> = {
    brave: new BraveSearchProvider("brave", config.timeoutMs, new KeyPool("brave", config.keys.brave)),
    exa: exaAlias,
    exa_api: exaApiProvider,
    exa_trial: exaTrialProvider,
    tavily: new TavilyProvider("tavily", config.timeoutMs, new KeyPool("tavily", config.keys.tavily)),
    searxng: new SearxngProvider(config.searxngUrl, config.timeoutMs),
    duckduckgo: new DuckDuckGoProvider(config.timeoutMs),
  };
  const fetchMap: Record<string, FetchProvider> = {
    local: new LocalFetchProvider(config.timeoutMs),
    firecrawl: new FirecrawlProvider("firecrawl", config.timeoutMs, new KeyPool("firecrawl", config.keys.firecrawl)),
    exa: exaAlias,
    exa_api: exaApiProvider,
    exa_trial: exaTrialProvider,
    tavily: searchMap.tavily as TavilyProvider,
  };
  return {
    searchProviders: config.searchProviders.map((name) => searchMap[name]).filter(Boolean),
    fetchProviders: config.fetchProviders.map((name) => fetchMap[name]).filter(Boolean),
  };
}

function selectExaProvider(
  config: SearchMcpConfig,
  exaApi: ExaApiProvider,
  exaTrial: ExaTrialProvider,
  exaDisabled: DisabledProvider,
): SearchProvider & FetchProvider {
  if (config.exa.mode === "off") {
    return exaDisabled;
  }
  if (config.exa.mode === "trial") {
    return exaTrial;
  }
  if (config.exa.mode === "api") {
    return exaApi;
  }
  if (config.keys.exa.length > 0) {
    return exaApi;
  }
  return config.exa.trialEnabled ? exaTrial : exaApi;
}

function decorateQuery(query: string, sites: string[], excludeSites: string[]): string {
  const include = sites.map((site) => `site:${site}`).join(" ");
  const exclude = excludeSites.map((site) => `-site:${site}`).join(" ");
  return [query, include, exclude].filter(Boolean).join(" ");
}

function normalizeExaResults(items: Array<Record<string, unknown>>, source: string): SearchResult[] {
  return items.map((item, index) => ({
    title: String(item.title ?? item.url ?? ""),
    url: String(item.url ?? item.id ?? ""),
    snippet: String(Array.isArray(item.highlights) ? item.highlights.join(" ") : item.summary ?? item.text ?? ""),
    source,
    score: Number(item.score ?? 1 - index / 100),
    published: typeof item.publishedDate === "string" ? item.publishedDate : null,
  })).filter((item) => item.url);
}

function parseDuckDuckGo(html: string, maxResults: number): SearchResult[] {
  const results: SearchResult[] = [];
  const pattern = /<a[^>]*class=["']result__a["'][^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(html)) && results.length < maxResults) {
    let url = match[1];
    const redirect = url.match(/[?&]uddg=([^&]+)/);
    if (redirect) {
      url = decodeURIComponent(redirect[1]);
    }
    if (domainOf(url).includes("duckduckgo.com")) {
      continue;
    }
    results.push({
      title: htmlToText(match[2]),
      url,
      snippet: "",
      source: "duckduckgo",
      score: 1 - results.length / 100,
      published: null,
    });
  }
  return results;
}

function extractMcpText(result: unknown): string {
  const content = (result as { content?: unknown }).content;
  if (!Array.isArray(content)) {
    return typeof result === "string" ? result : JSON.stringify(result);
  }
  return content.map((item) => {
    if (item && typeof item === "object" && "text" in item) {
      return String((item as { text?: unknown }).text ?? "");
    }
    return "";
  }).filter(Boolean).join("\n");
}

export function parseExaTrialSearchResult(result: unknown, source: string): SearchResult[] {
  const text = extractMcpText(result);
  try {
    const parsed = JSON.parse(text);
    const items = Array.isArray(parsed) ? parsed : Array.isArray(parsed?.results) ? parsed.results : [];
    return normalizeExaResults(items, source);
  } catch {
    return parseExaTrialTextResults(text, source);
  }
}

function parseExaTrialTextResults(text: string, source: string): SearchResult[] {
  const results: SearchResult[] = [];
  const pattern = /(?:^|\n)Title:\s*(.+?)\nURL:\s*(\S+)([\s\S]*?)(?=\n---\s*\n\s*Title:|$)/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text))) {
    const title = trimText(match[1], 100);
    const url = match[2];
    const body = match[3] ?? "";
    const published = body.match(/\nPublished:\s*([^\n]+)/)?.[1]?.trim() ?? null;
    const highlights = body.split(/Highlights:\s*/i)[1] ?? body;
    results.push({
      title,
      url,
      snippet: trimText(highlights.replace(/\[\.{3}\]/g, " ").replace(/\s+/g, " "), 120),
      source,
      score: 1 - results.length / 100,
      published: published && published !== "N/A" ? published : null,
    });
  }
  return results.filter((item) => item.url);
}
