import assert from "node:assert/strict";
import test from "node:test";

import { SearchWebService } from "../src/search-service.js";
import type { FetchProvider, SearchProvider } from "../src/types.js";

test("web_search returns compact agent-shaped results without legacy metadata", async () => {
  const provider: SearchProvider = {
    name: "fake",
    kind: "search",
    configured: () => true,
    search: async () => [
      {
        title: "A very long title that should be shortened because the MCP output should stay compact for agent consumption",
        url: "https://example.com/docs?utm_source=test#section",
        snippet: "This snippet is intentionally verbose so the service has to shorten it before returning results to the MCP caller. It should not become a page summary.",
        source: "fake",
        score: 0.2,
      },
    ],
    status: () => ({ enabled: true, configured: true, keyCount: 0, cooldownCount: 0, disabledCount: 0 }),
  };
  const service = new SearchWebService({ searchProviders: [provider], fetchProviders: [] });

  const result = await service.webSearch({ query: "docs", max_results: 3 });

  assert.deepEqual(Object.keys(result).sort(), ["query", "results", "trace"]);
  assert.equal(result.results[0].id, "r1");
  assert.equal(result.results[0].url, "https://example.com/docs");
  assert.equal(result.results[0].domain, "example.com");
  assert.equal(result.results[0].source, "fake");
  assert.ok(result.results[0].title.length <= 100);
  assert.ok(result.results[0].snippet.length <= 120);
  assert.equal(Object.hasOwn(result, "variants"), false);
  assert.equal(Object.hasOwn(result, "meta"), false);
  assert.equal(Object.hasOwn(result, "prompt_pack"), false);
});

test("web_search falls back to the next provider when the first provider fails", async () => {
  const failing: SearchProvider = {
    name: "brave",
    kind: "search",
    configured: () => true,
    search: async () => {
      throw new Error("rate limited");
    },
    status: () => ({ enabled: true, configured: true, keyCount: 1, cooldownCount: 1, disabledCount: 0, lastErrorType: "rate_limited" }),
  };
  const fallback: SearchProvider = {
    name: "duckduckgo",
    kind: "search",
    configured: () => true,
    search: async () => [{ title: "Fallback", url: "https://fallback.test", snippet: "fallback", source: "duckduckgo", score: 0.1 }],
    status: () => ({ enabled: true, configured: true, keyCount: 0, cooldownCount: 0, disabledCount: 0 }),
  };
  const service = new SearchWebService({ searchProviders: [failing, fallback], fetchProviders: [] });

  const result = await service.webSearch({ query: "anything" });

  assert.equal(result.results[0].source, "duckduckgo");
  assert.deepEqual(result.trace.providers, ["brave", "duckduckgo"]);
  assert.equal(result.trace.fallbacks[0].provider, "brave");
});

test("web_fetch falls back after local extraction fails", async () => {
  const local: FetchProvider = {
    name: "local",
    kind: "fetch",
    configured: () => true,
    fetch: async () => {
      throw new Error("no main content");
    },
    status: () => ({ enabled: true, configured: true, keyCount: 0, cooldownCount: 0, disabledCount: 0, lastErrorType: "extract_failed" }),
  };
  const firecrawl: FetchProvider = {
    name: "firecrawl",
    kind: "fetch",
    configured: () => true,
    fetch: async () => ({
      url: "https://example.com",
      title: "Example",
      source: "firecrawl",
      summary: "Extracted evidence",
      evidence: [{ text: "Extracted evidence", score: 1 }],
    }),
    status: () => ({ enabled: true, configured: true, keyCount: 1, cooldownCount: 0, disabledCount: 0 }),
  };
  const service = new SearchWebService({ searchProviders: [], fetchProviders: [local, firecrawl] });

  const result = await service.webFetch({ url: "https://example.com", query: "evidence" });

  assert.equal(result.source, "firecrawl");
  assert.equal(result.evidence[0].text, "Extracted evidence");
});
