import assert from "node:assert/strict";
import test from "node:test";

import { KeyPool } from "../src/key-pool.js";
import { BraveSearchProvider } from "../src/providers.js";

test("keyed providers disable quota-exhausted keys until next month and try the next key", async () => {
  const originalFetch = globalThis.fetch;
  const seenTokens: string[] = [];
  let now = new Date(2026, 5, 17).getTime();

  globalThis.fetch = async (_url, init) => {
    const headers = init?.headers as Record<string, string>;
    seenTokens.push(headers["X-Subscription-Token"]);
    if (seenTokens.length === 1) {
      return new Response("monthly quota exceeded", { status: 402 });
    }
    return new Response(JSON.stringify({
      web: {
        results: [{ title: "Result", url: "https://example.com", description: "ok" }],
      },
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const provider = new BraveSearchProvider("brave", 1_000, new KeyPool("brave", ["k1", "k2"], () => now));
    const results = await provider.search({
      query: "test",
      max_results: 1,
      freshness: null,
      sites: [],
      exclude_sites: [],
      locale: "auto",
    });

    assert.deepEqual(seenTokens, ["k1", "k2"]);
    assert.equal(results[0].url, "https://example.com");
    assert.equal(provider.status().disabledCount, 1);

    now = new Date(2026, 6, 1).getTime();
    assert.equal(provider.status().disabledCount, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
