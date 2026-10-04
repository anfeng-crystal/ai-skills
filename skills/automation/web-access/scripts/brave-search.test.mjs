import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const script = process.env.BRAVE_SEARCH_SCRIPT || fileURLToPath(new URL("./brave-search.mjs", import.meta.url));
const endpoint = "https://offline.invalid/search";
const fakeKey = "synthetic-key-never-real";

async function fixture(t) {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), "brave-args-"));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const events = path.join(base, "fetch.jsonl");
  const preload = path.join(base, "fetch.mjs");
  await fs.writeFile(preload, `
import fs from "node:fs";
globalThis.fetch = async (url, options) => {
  fs.appendFileSync(${JSON.stringify(events)}, JSON.stringify({ url: String(url), key: options.headers["X-Subscription-Token"] }) + "\\n");
  return { ok: true, json: async () => ({ web: { results: [{ title: "Fixture", url: "https://offline.invalid/result", description: "Synthetic" }] } }) };
};
`);
  return async (args, env = {}) => {
    await fs.rm(events, { force: true });
    const result = spawnSync(process.execPath, ["--import", preload, script, ...args], {
      encoding: "utf8", timeout: 10000,
      env: { ...process.env, BRAVE_SEARCH_API_KEY: fakeKey, BRAVE_SEARCH_API_ENDPOINT: endpoint, ...env },
    });
    assert.ifError(result.error);
    const calls = await fs.readFile(events, "utf8").then((s) => s.trim().split("\n").filter(Boolean).map(JSON.parse),
      (error) => { if (error.code === "ENOENT") return []; throw error; });
    return { ...result, calls };
  };
}

for (const flag of ["--api-key", "--endpoint", "--count", "--country", "--search-lang", "--freshness"]) {
  test(`${flag} rejects missing values without swallowing control options`, async (t) => {
    const run = await fixture(t);
    for (const tail of [[], ["--dry-run", "--json"], ["-h"], ["   "]]) {
      const result = await run(["fixture", flag, ...tail]);
      assert.equal(result.status, 1, result.stderr);
      assert.match(result.stderr, new RegExp(`${flag} requires a value`));
      assert.deepEqual(result.calls, []);
      assert.ok(!(result.stdout + result.stderr).includes(fakeKey));
    }
  });
}

test("valid dry-run preserves request parameters and hides the key", async (t) => {
  const run = await fixture(t);
  const result = await run(["two words", "--api-key", fakeKey, "--endpoint", endpoint,
    "--count", "7", "--country", "US", "--search-lang", "en", "--freshness", "pw", "--dry-run"]);
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.dryRun, true);
  assert.equal(report.hasApiKey, true);
  assert.equal(report.count, 7);
  const params = new URL(report.requestUrl).searchParams;
  assert.equal(params.get("q"), "two words");
  assert.equal(params.get("count"), "7");
  assert.equal(params.get("country"), "US");
  assert.equal(params.get("search_lang"), "en");
  assert.equal(params.get("freshness"), "pw");
  assert.deepEqual(result.calls, []);
  assert.ok(!result.stdout.includes(fakeKey));
});

test("valid JSON and raw searches retain explicit and environment credentials", async (t) => {
  const run = await fixture(t);
  const json = await run(["fixture", "--json"]);
  assert.equal(json.status, 0, json.stderr);
  assert.equal(JSON.parse(json.stdout).results[0].rank, 1);
  assert.equal(json.calls[0].key, fakeKey);
  const raw = await run(["fixture", "--api-key", "explicit-synthetic-key", "--raw"]);
  assert.equal(raw.status, 0, raw.stderr);
  assert.equal(JSON.parse(raw.stdout).web.results[0].title, "Fixture");
  assert.equal(raw.calls[0].key, "explicit-synthetic-key");
});

test("standalone help and keyless dry-run remain offline", async (t) => {
  const run = await fixture(t);
  for (const args of [["--help"], ["-h"], ["fixture", "--dry-run"]]) {
    const result = await run(args, { BRAVE_SEARCH_API_KEY: "" });
    assert.equal(result.status, 0, result.stderr);
    assert.deepEqual(result.calls, []);
  }
});

test("invalid numeric count and missing credentials preserve failure exits", async (t) => {
  const run = await fixture(t);
  for (const value of ["-1", "0", "NaN"]) {
    const result = await run(["fixture", "--count", value]);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /--count must be a positive number/);
    assert.deepEqual(result.calls, []);
  }
  const missing = await run(["fixture"], { BRAVE_SEARCH_API_KEY: "" });
  assert.equal(missing.status, 2);
  assert.deepEqual(missing.calls, []);
});
