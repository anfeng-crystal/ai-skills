import assert from "node:assert/strict";
import test from "node:test";

import { loadConfig } from "../src/config.js";
import { buildProviders } from "../src/providers.js";

function exaStatus(env: Record<string, string | undefined>) {
  const config = loadConfig({
    envFile: "/path/that/does/not/exist",
    env: {
      SEARCH_PROVIDERS: "exa",
      FETCH_PROVIDERS: "exa",
      ...env,
    },
  });
  const providers = buildProviders(config);
  return {
    search: providers.searchProviders[0].status(),
    fetch: providers.fetchProviders[0].status(),
  };
}

test("Exa auto mode uses API keys when configured", () => {
  const status = exaStatus({ EXA_MODE: "auto", EXA_API_KEYS: "exa_1,exa_2", EXA_TRIAL_ENABLED: "true" });

  assert.equal(status.search.enabled, true);
  assert.equal(status.search.configured, true);
  assert.equal(status.search.keyCount, 2);
  assert.equal(status.fetch.configured, true);
  assert.equal(status.fetch.keyCount, 2);
});

test("Exa auto mode can opt into trial MCP when no API key exists", () => {
  const status = exaStatus({ EXA_MODE: "auto", EXA_TRIAL_ENABLED: "true" });

  assert.equal(status.search.enabled, true);
  assert.equal(status.search.configured, true);
  assert.equal(status.search.keyCount, 0);
  assert.equal(status.fetch.configured, true);
});

test("Exa API mode does not use trial MCP without API keys", () => {
  const status = exaStatus({ EXA_MODE: "api", EXA_TRIAL_ENABLED: "true" });

  assert.equal(status.search.enabled, true);
  assert.equal(status.search.configured, false);
  assert.equal(status.search.keyCount, 0);
  assert.equal(status.fetch.configured, false);
});

test("Exa trial mode enables remote MCP explicitly", () => {
  const status = exaStatus({ EXA_MODE: "trial" });

  assert.equal(status.search.enabled, true);
  assert.equal(status.search.configured, true);
  assert.equal(status.search.keyCount, 0);
  assert.equal(status.fetch.configured, true);
});

test("Exa off mode disables Exa even when keys are present", () => {
  const status = exaStatus({ EXA_MODE: "off", EXA_API_KEYS: "exa_1", EXA_TRIAL_ENABLED: "true" });

  assert.equal(status.search.enabled, false);
  assert.equal(status.search.configured, false);
  assert.equal(status.search.keyCount, 0);
  assert.equal(status.fetch.enabled, false);
  assert.equal(status.fetch.configured, false);
});

test("Exa off mode also disables explicit Exa provider aliases", () => {
  const config = loadConfig({
    envFile: "/path/that/does/not/exist",
    env: {
      EXA_MODE: "off",
      EXA_API_KEYS: "exa_1",
      EXA_TRIAL_ENABLED: "true",
      SEARCH_PROVIDERS: "exa_api,exa_trial",
      FETCH_PROVIDERS: "exa_api,exa_trial",
    },
  });
  const providers = buildProviders(config);

  assert.deepEqual(providers.searchProviders.map((provider) => provider.status().enabled), [false, false]);
  assert.deepEqual(providers.fetchProviders.map((provider) => provider.status().configured), [false, false]);
});
