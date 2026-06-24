import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { loadConfig } from "../src/config.js";

test("starts without an env file and keeps keyless providers available", () => {
  const config = loadConfig({ envFile: "/path/that/does/not/exist", env: {} });

  assert.deepEqual(config.searchProviders, ["brave", "exa", "tavily", "searxng", "duckduckgo"]);
  assert.deepEqual(config.fetchProviders, ["local", "firecrawl", "exa", "tavily"]);
  assert.equal(config.keys.brave.length, 0);
  assert.equal(config.keys.exa.length, 0);
  assert.equal(config.exa.mode, "auto");
  assert.equal(config.exa.trialEnabled, false);
});

test("loads comma-separated provider keys from a selected .env file", () => {
  const dir = mkdtempSync(join(tmpdir(), "search-web-mcp-"));
  const envFile = join(dir, ".env");
  writeFileSync(envFile, [
    "BRAVE_SEARCH_API_KEYS=brv1, brv2,,",
    "EXA_API_KEYS=exa1,exa2",
    "TAVILY_API_KEYS=tvly1",
    "FIRECRAWL_API_KEYS=fc1, fc2",
    "EXA_MODE=trial",
    "EXA_TRIAL_ENABLED=true",
    "SEARCH_PROVIDERS=exa,duckduckgo",
    "FETCH_PROVIDERS=local,exa",
  ].join("\n"));

  try {
    const config = loadConfig({ envFile, env: {} });

    assert.deepEqual(config.keys.brave, ["brv1", "brv2"]);
    assert.deepEqual(config.keys.exa, ["exa1", "exa2"]);
    assert.deepEqual(config.keys.tavily, ["tvly1"]);
    assert.deepEqual(config.keys.firecrawl, ["fc1", "fc2"]);
    assert.equal(config.exa.mode, "trial");
    assert.equal(config.exa.trialEnabled, true);
    assert.deepEqual(config.searchProviders, ["exa", "duckduckgo"]);
    assert.deepEqual(config.fetchProviders, ["local", "exa"]);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
