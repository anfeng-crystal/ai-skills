import test, { after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const scripts = process.env.CDP_TEST_SCRIPTS || path.dirname(fileURLToPath(import.meta.url));
const root = fs.mkdtempSync(path.join(os.tmpdir(), "cdp-transport-test-"));
after(() => fs.rmSync(root, { recursive: true, force: true }));
const preload = path.join(root, "transport-fixture.mjs");
fs.writeFileSync(preload, `
import fs from "node:fs";
const scenario = process.env.CDP_SCENARIO;
const record = (kind, value) => fs.appendFileSync(process.env.CDP_CALLS, JSON.stringify({ kind, value }) + "\\n");
globalThis.fetch = async () => { throw new Error("network forbidden by fixture"); };
globalThis.WebSocket = class {
  constructor(url) {
    record("connect", url);
    if (scenario === "constructor-error") throw new Error("synthetic constructor failure");
    this.handlers = {};
    queueMicrotask(() => {
      if (scenario === "before-open") this.emit("close", { code: 1006, reason: "PRIVATE_CLOSE_REASON" });
      else this.emit("open");
    });
  }
  addEventListener(name, handler) { this.handlers[name] = handler; }
  emit(name, value = {}) { this.handlers[name]?.(value); }
  close() { record("close"); this.emit("close", { code: 1000 }); }
  send(raw) {
    const request = JSON.parse(raw); record("send", request);
    if (scenario === "send-error") throw new Error("synthetic send failure");
    queueMicrotask(() => {
      const response = (value) => this.emit("message", { data: JSON.stringify(value) });
      if (scenario === "after-send") this.emit("close", { code: 1006, reason: "PRIVATE_CLOSE_REASON" });
      else if (scenario === "unrelated-close") {
        response({ method: "Page.loadEventFired", params: {} });
        response({ id: request.id + 1, result: {} });
        this.emit("close", { code: 1001, reason: "PRIVATE_CLOSE_REASON" });
      } else if (scenario === "connection-error") this.emit("error");
      else if (scenario === "malformed") this.emit("message", { data: "{" });
      else if (scenario === "protocol-error") response({ id: request.id, error: { code: -32601, message: "synthetic missing method" } });
      else if (scenario === "timeout") return;
      else {
        response({ method: "Page.loadEventFired", params: {} });
        response({ id: request.id + 1, result: { ignored: true } });
        response({ id: request.id, result: scenario === "null-result" ? null : { fixture: true } });
        // A second response and the synchronous close emitted by close() cannot change settlement.
        response({ id: request.id, error: { message: "late failure" } });
      }
    });
  }
};
`);

let sequence = 0;
function run(scenario, extra = [], json = true) {
  const calls = path.join(root, `calls-${sequence++}.jsonl`);
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith("WEB_ACCESS_")));
  const args = ["send", "--ws-url", "ws://127.0.0.1:9222/devtools/page/fixture", "--method", "DOM.getDocument", "--params", '{"depth":1}', "--id", "0", "--timeout", "40", ...extra];
  if (json) args.push("--json");
  const result = spawnSync(process.execPath, ["--import", preload, path.join(scripts, "cdp-proxy.mjs"), ...args], {
    env: { ...env, CDP_SCENARIO: scenario, CDP_CALLS: calls }, encoding: "utf8", timeout: 3000,
  });
  assert.equal(result.error, undefined, result.stderr);
  return { ...result, calls: fs.existsSync(calls) ? fs.readFileSync(calls, "utf8").trim().split("\n").map(JSON.parse) : [] };
}

function failure(result, pattern) {
  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.equal(result.stderr, "");
  const value = JSON.parse(result.stdout);
  assert.equal(value.ok, false);
  assert.equal(value.command, "send");
  assert.match(value.error, pattern);
  return value;
}

for (const scenario of ["before-open", "after-send", "unrelated-close"]) {
  test(`early close reports a controlled JSON failure: ${scenario}`, () => {
    const result = run(scenario);
    failure(result, /WebSocket closed before CDP response/);
    assert.doesNotMatch(result.stdout + result.stderr, /PRIVATE_CLOSE_REASON|unsettled top-level await/);
    assert.equal(result.calls.filter(call => call.kind === "send").length, scenario === "before-open" ? 0 : 1);
  });
}

test("early close preserves text-mode stderr failure", () => {
  const result = run("after-send", [], false);
  assert.equal(result.status, 1);
  assert.equal(result.stdout, "");
  assert.match(result.stderr, /WebSocket closed before CDP response/);
});

test("matching response retains explicit id, params and success shape despite unrelated or late events", () => {
  const result = run("success");
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stderr, "");
  assert.deepEqual(JSON.parse(result.stdout), {
    target: null, wsUrl: "ws://127.0.0.1:9222/devtools/page/fixture",
    request: { id: 0, method: "DOM.getDocument", params: { depth: 1 }, safety: "safe" },
    result: { fixture: true },
  });
  assert.equal(result.calls.filter(call => call.kind === "close").length, 1);
});

test("null result remains a successful null", () => {
  const result = run("null-result");
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).result, null);
});

for (const [scenario, pattern] of [
  ["protocol-error", /synthetic missing method/],
  ["connection-error", /WebSocket connection failed/],
  ["malformed", /JSON|property|position/],
  ["send-error", /synthetic send failure/],
  ["timeout", /CDP request timed out after 40ms/],
]) {
  test(`request failure settles and closes its transport: ${scenario}`, () => {
    const result = run(scenario);
    failure(result, pattern);
    assert.equal(result.calls.filter(call => call.kind === "close").length, 1);
  });
}

test("constructor errors use the existing CLI failure shape", () => {
  const result = run("constructor-error");
  failure(result, /synthetic constructor failure/);
  assert.equal(result.calls.filter(call => call.kind === "send").length, 0);
});

test("dry-run preserves request plan without opening a socket", () => {
  const result = run("after-send", ["--dry-run"]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).dryRun, true);
  assert.deepEqual(result.calls, []);
});
