import { errorType, ProviderError } from "./errors.js";
import { canonicalizeUrl, domainOf, trimText } from "./text.js";
import type { FetchProvider, FetchRequest, FetchResult, SearchProvider, SearchRequest, WebSearchResponse } from "./types.js";

export interface SearchWebServiceOptions {
  searchProviders: SearchProvider[];
  fetchProviders: FetchProvider[];
  defaultMaxResults?: number;
}

export class SearchWebService {
  constructor(private readonly options: SearchWebServiceOptions) {}

  async webSearch(input: SearchRequest): Promise<WebSearchResponse> {
    const request: Required<SearchRequest> = {
      query: input.query,
      max_results: clamp(input.max_results ?? this.options.defaultMaxResults ?? 6, 1, 12),
      freshness: input.freshness ?? null,
      sites: input.sites ?? [],
      exclude_sites: input.exclude_sites ?? [],
      locale: input.locale ?? "auto",
    };
    if (!request.query.trim()) {
      throw new ProviderError("search-web", "bad_response", "query is required");
    }

    const providers: string[] = [];
    const fallbacks: Array<{ provider: string; reason: string }> = [];
    for (const provider of this.options.searchProviders) {
      if (!provider.configured()) {
        fallbacks.push({ provider: provider.name, reason: "not_configured" });
        continue;
      }
      providers.push(provider.name);
      try {
        const results = await provider.search(request);
        if (results.length === 0) {
          fallbacks.push({ provider: provider.name, reason: "no_results" });
          continue;
        }
        return {
          query: request.query,
          results: results
            .map((item) => ({
              id: "",
              title: trimText(item.title, 100),
              url: canonicalizeUrl(item.url),
              domain: item.domain || domainOf(item.url),
              snippet: trimText(item.snippet, 120),
              source: item.source,
              score: Number(item.score.toFixed(4)),
              published: item.published ?? null,
            }))
            .filter((item) => item.url && item.domain)
            .slice(0, request.max_results)
            .map((item, index) => ({ ...item, id: `r${index + 1}` })),
          trace: { providers, fallbacks },
        };
      } catch (error) {
        fallbacks.push({ provider: provider.name, reason: errorType(error) });
      }
    }
    return { query: request.query, results: [], trace: { providers, fallbacks } };
  }

  async webFetch(input: FetchRequest): Promise<FetchResult> {
    const request: Required<FetchRequest> = {
      url: input.url,
      query: input.query ?? "",
      max_chars: clamp(input.max_chars ?? 2400, 300, 6000),
    };
    if (!request.url.trim()) {
      throw new ProviderError("search-web", "bad_response", "url is required");
    }
    let lastError: unknown = new ProviderError("search-web", "not_configured", "no fetch provider configured");
    for (const provider of this.options.fetchProviders) {
      if (!provider.configured()) {
        continue;
      }
      try {
        return await provider.fetch(request);
      } catch (error) {
        lastError = error;
      }
    }
    throw lastError;
  }

  webStatus(): Record<string, unknown> {
    return {
      searchProviders: this.options.searchProviders.map((provider) => ({ name: provider.name, ...provider.status() })),
      fetchProviders: this.options.fetchProviders.map((provider) => ({ name: provider.name, ...provider.status() })),
    };
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
