import test, { after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { parseFindOptions, parseProxyOptions } from "./cdp-cli-options.mjs";

const scripts = path.dirname(fileURLToPath(import.meta.url));
const fixture = fs.mkdtempSync(path.join(os.tmpdir(), "web-access-cli-test-"));
after(() => fs.rmSync(fixture, { recursive: true, force: true }));
const guard = path.join(fixture, "network-guard.mjs");
// Every transport is replaced. These tests never attach to a user browser.
fs.writeFileSync(guard, `
import fs from "node:fs";
const calls = (kind, data) => fs.appendFileSync(process.env.CLI_CALLS, JSON.stringify({ kind, ...data }) + "\\n");
const targets = [
  { id: "fixture-1", type: "page", title: "Fixture dashboard", url: "https://fixture.invalid/app", webSocketDebuggerUrl: "ws://127.0.0.1:9222/devtools/page/fixture-1" },
  { id: "fixture-2", type: "page", title: "Other", url: "https://second.invalid/" },
  { id: "devtools-1", type: "page", title: "Devtools", url: "devtools://inspect" },
  { id: "worker-1", type: "worker", title: "Worker", url: "https://worker.invalid/" }
];
globalThis.fetch = async (url, options = {}) => {
  calls("fetch", { url: String(url), method: options.method || "GET" });
  const payload = String(url).includes("/json/list") ? targets : String(url).includes("/json/version")
    ? { webSocketDebuggerUrl: "ws://127.0.0.1:9222/devtools/browser/fixture" } : targets[0];
  return { ok: true, status: 200, json: async () => payload, text: async () => "ok" };
};
globalThis.WebSocket = class {
  constructor(url) { this.handlers = {}; calls("websocket", { url: String(url) }); queueMicrotask(() => this.handlers.open?.()); }
  addEventListener(name, fn) { this.handlers[name] = fn; }
  send(message) {
    const request = JSON.parse(message); calls("send", request);
    queueMicrotask(() => this.handlers.message?.({ data: JSON.stringify({ id: request.id, result: { fixture: true } }) }));
  }
  close() { this.handlers.close?.(); }
};
`);

function run(script, args, overrides = {}) {
  const callsPath = path.join(fixture, "calls.jsonl");
  fs.writeFileSync(callsPath, "");
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith("WEB_ACCESS_")));
  const result = spawnSync(process.execPath, ["--import", guard, path.join(scripts, script), ...args], {
    env: { ...env, CLI_CALLS: callsPath, ...overrides }, encoding: "utf8", timeout: 10000,
  });
  assert.equal(result.error, undefined);
  return { ...result, calls: fs.readFileSync(callsPath, "utf8").split("\n").filter(Boolean).map(JSON.parse) };
}

function failBeforeTransport(script, args, pattern) {
  const result = run(script, [...args, "--json"]);
  assert.equal(result.status, 1, result.stdout + result.stderr);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.ok, false);
  assert.match(payload.error, pattern);
  assert.equal(result.stderr, "");
  assert.deepEqual(result.calls, []);
  return payload;
}

test("all required option values reject a following switch before transport", () => {
  const findFlags = ["--endpoint", "--host", "--port", "--contains", "--url", "--match", "--type", "--mode", "--value", "--only", "--limit", "--since", "--sort", "--profile-dir", "--bookmarks-path", "--history-path"];
  const proxyFlags = ["--endpoint", "--host", "--port", "--ws-url", "--method", "--params", "--id", "--timeout", "--file", "--selector", "--x", "--y", "--direction"];
  for (const flag of findFlags) failBeforeTransport("find-url.mjs", [flag, "--dry-run"], /Missing value/);
  for (const flag of proxyFlags) failBeforeTransport("cdp-proxy.mjs", ["open", "https://fixture.invalid", flag, "--dry-run", "--allow-unsafe"], /Missing value/);
  assert.throws(() => parseFindOptions(["--contains"]), /Missing value/);
  assert.throws(() => parseProxyOptions(["--timeout", ""]), /Missing value/);
});

test("numeric inputs and enums fail as structured JSON before requests", () => {
  for (const args of [["--port", "nope"], ["--port", "0"], ["--port", "65536"], ["--limit", "nope"], ["--limit", "0"], ["--limit", "1.5"], ["--mode", "typo"], ["--value", "typo"], ["--only", "typo"], ["--sort", "typo"], ["--typo"], ["--mode", "regex", "--match", "["]]) {
    failBeforeTransport("find-url.mjs", [...args, "--dry-run"], /integer|Invalid|Unknown/);
  }
  for (const args of [["--id", "1.5"], ["--id", "9007199254740992"], ["--timeout", "NaN"], ["--timeout", "0"], ["--timeout", "2147483648"], ["--x", "Infinity"], ["--y", "NaN"], ["--direction", "sideways"], ["--typo"]]) {
    failBeforeTransport("cdp-proxy.mjs", ["scroll", "fixture", ...args, "--dry-run"], /integer|finite|Invalid|Unknown/);
  }
  const result = run("find-url.mjs", ["--dry-run", "--json"], { WEB_ACCESS_CDP_PORT: "nope" });
  assert.equal(result.status, 1);
  assert.deepEqual(result.calls, []);
  assert.match(JSON.parse(result.stdout).error, /--port/);
});

test("HTTP and WS endpoint syntax rejects unsupported schemes", () => {
  failBeforeTransport("find-url.mjs", ["--endpoint", "ftp://127.0.0.1:9222", "--dry-run"], /http/);
  failBeforeTransport("find-url.mjs", ["--host", "http://127.0.0.1", "--dry-run"], /Invalid CDP host/);
  failBeforeTransport("cdp-proxy.mjs", ["doctor", "--ws-url", "ftp://127.0.0.1:9222/path"], /ws:\/\//);
  failBeforeTransport("cdp-proxy.mjs", ["list", "--endpoint", "http://[::1"], /Invalid URL/);
});

test("explicit HTTP and WS routes retain precedence over unused host/port defaults", () => {
  const env = { WEB_ACCESS_CDP_PORT: "nope", WEB_ACCESS_CDP_HOST: "bad host" };
  for (const [script, args] of [
    ["find-url.mjs", ["--endpoint", "http://127.0.0.1:9222"]],
    ["cdp-proxy.mjs", ["list", "--endpoint", "http://127.0.0.1:9222"]],
    ["cdp-proxy.mjs", ["doctor", "--ws-url", "ws://127.0.0.1:9222/page/fixture"]],
    ["cdp-proxy.mjs", ["send", "--ws-url", "ws://127.0.0.1:9222/page/fixture", "--method", "DOM.getDocument"]],
  ]) {
    const result = run(script, [...args, "--json"], env);
    assert.equal(result.status, 0, result.stderr + result.stdout);
    assert.ok(result.calls.every(call => !String(call.url).includes("bad host")));
  }
  // list does not use the WS override; its active HTTP default is still checked.
  const list = run("cdp-proxy.mjs", ["list", "--json"], { ...env, WEB_ACCESS_CDP_WS_URL: "ws://127.0.0.1:9222/page/fixture" });
  assert.equal(list.status, 1);
  assert.match(JSON.parse(list.stdout).error, /--port/);
  assert.deepEqual(list.calls, []);
});

test("HTTP routes ignore unused WS defaults while required values still fail early", () => {
  const env = { WEB_ACCESS_CDP_WS_URL: "stale-invalid-ws" };
  const result = run("cdp-proxy.mjs", ["list", "--endpoint", "http://127.0.0.1:9222", "--json"], env);
  assert.equal(result.status, 0, result.stderr + result.stdout);
  assert.equal(result.calls[0].url, "http://127.0.0.1:9222/json/list");
  assert.ok(result.calls.every(call => call.kind === "fetch"));
  failBeforeTransport("cdp-proxy.mjs", ["list", "--ws-url", "--dry-run"], /Missing value/);
  failBeforeTransport("find-url.mjs", ["--only", "bookmarks", "--port", "--dry-run"], /Missing value/);
});

test("IPv6 loopback works through explicit HTTP, host, and WebSocket paths", () => {
  for (const [script, command] of [["find-url.mjs", []], ["cdp-proxy.mjs", ["list"]]]) {
    const actual = run(script, [...command, "--endpoint", "http://[::1]:9222", "--json"]);
    assert.equal(actual.status, 0, actual.stderr);
    assert.equal(actual.calls[0].url, "http://[::1]:9222/json/list");
    const dry = run(script, [...command, "--host", "::1", "--dry-run", "--json"]);
    assert.equal(dry.status, 0, dry.stderr);
    assert.match(dry.stdout, /http:\/\/\[::1\]:9222/);
    assert.deepEqual(dry.calls, []);
  }
  const ws = run("cdp-proxy.mjs", ["send", "--ws-url", "ws://[::1]:9222/devtools/page/fixture", "--method", "DOM.getDocument", "--json"]);
  assert.equal(ws.status, 0, ws.stderr);
  assert.equal(ws.calls[0].url, "ws://[::1]:9222/devtools/page/fixture");
  assert.equal(JSON.parse(ws.stdout).result.fixture, true);
});

test("remote HTTP and WS still require explicit opt-in for execution", () => {
  for (const [script, args] of [
    ["find-url.mjs", ["--endpoint", "http://remote.invalid:9222"]],
    ["cdp-proxy.mjs", ["list", "--endpoint", "http://remote.invalid:9222"]],
    ["cdp-proxy.mjs", ["send", "--ws-url", "ws://remote.invalid:9222/page/fixture", "--method", "DOM.getDocument"]],
  ]) {
    failBeforeTransport(script, args, /WEB_ACCESS_ALLOW_REMOTE=1/);
    const allowed = run(script, [...args, "--json"], { WEB_ACCESS_ALLOW_REMOTE: "1" });
    assert.equal(allowed.status, 0, allowed.stderr + allowed.stdout);
    assert.ok(allowed.calls.length > 0);
    const dry = run(script, [...args, "--dry-run", "--json"]);
    assert.equal(dry.status, 0, dry.stderr);
    assert.deepEqual(dry.calls, []);
  }
});

test("legacy optional title, match modes, target filters, and output fields remain", () => {
  const title = run("find-url.mjs", ["Fixture", "--title", "--first", "--json"]);
  assert.equal(JSON.parse(title.stdout)[0].id, "fixture-1");
  for (const [mode, needle] of [["contains", "fixture dashboard"], ["exact", "Fixture dashboard"], ["prefix", "https://fixture"], ["host", "fixture.invalid"], ["regex", "Fixture.*dashboard"], ["url", "fixture.invalid/app"], ["title", "dashboard"]]) {
    const result = run("find-url.mjs", ["--mode", mode, "--match", needle, "--json"]);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(JSON.parse(result.stdout)[0].id, "fixture-1");
  }
  const all = run("find-url.mjs", ["--list-all", "--include-devtools", "--limit", "3", "--json"]);
  assert.equal(JSON.parse(all.stdout).length, 3);
  const worker = run("find-url.mjs", ["--type", "worker", "--value", "id"]);
  assert.equal(worker.stdout.trim(), "worker-1");
  for (const value of ["summary", "url", "title", "id", "webSocketDebuggerUrl", "json"]) {
    const result = run("find-url.mjs", ["Fixture", "--first", "--value", value]);
    assert.equal(result.status, 0, result.stderr);
    assert.ok(result.stdout.trim());
  }
});

test("explicit synthetic bookmarks and history preserve source modes and sorting", () => {
  const bookmarks = path.join(fixture, "Bookmarks");
  const history = path.join(fixture, "History");
  fs.writeFileSync(bookmarks, JSON.stringify({ roots: { bookmark_bar: { name: "Bar", children: [{ type: "url", name: "Saved fixture", url: "https://saved.invalid", date_added: "1" }] } } }));
  const setup = spawnSync("python3", ["-c", `import sqlite3,sys,time
c=sqlite3.connect(sys.argv[1]);c.execute('CREATE TABLE urls (url TEXT,title TEXT,visit_count INTEGER,last_visit_time INTEGER)')
now=int((time.time()+11644473600)*1000000)
c.executemany('INSERT INTO urls VALUES (?,?,?,?)',[('https://old.invalid','Old',5,now-1000000),('https://new.invalid','New',1,now)])
c.commit();c.close()`, history], { encoding: "utf8" });
  assert.equal(setup.status, 0, setup.stderr);
  for (const [source, length] of [["targets", 2], ["bookmarks", 1], ["history", 2], ["chrome", 3], ["all", 5]]) {
    const local = ["bookmarks", "history", "chrome"].includes(source);
    const result = run("find-url.mjs", ["--only", source, "--profile-dir", fixture, "--bookmarks-path", bookmarks, "--history-path", history, "--since", "1d", "--sort", "visits", "--json"], local ? { WEB_ACCESS_CDP_PORT: "nope", WEB_ACCESS_CDP_HOST: "bad host" } : {});
    assert.equal(result.status, 0, result.stderr);
    const rows = JSON.parse(result.stdout);
    assert.equal(rows.length, length);
    if (source === "history") assert.equal(rows[0].visitCount, 5);
    if (local) assert.deepEqual(result.calls, []);
  }
});

test("proxy command dry-runs keep prior request capabilities and negative coordinates", () => {
  for (const args of [["doctor"], ["probe"], ["list"], ["open", "https://fixture.invalid"], ["info", "fixture"], ["screenshot", "fixture", "--file", "fixture.png"], ["navigate", "fixture", "https://new.invalid"], ["back", "fixture"], ["click", "fixture", "--selector", "#button"], ["scroll", "fixture", "--x", "-2.5", "--y", "-300"], ["close", "fixture"], ["send", "fixture", "DOM.getDocument", '{"depth":1}', "--id", "-1"]]) {
    const result = run("cdp-proxy.mjs", [...args, "--dry-run", "--json"]);
    assert.equal(result.status, 0, result.stderr);
    const payload = JSON.parse(result.stdout);
    assert.equal(payload.dryRun, true);
    assert.deepEqual(result.calls, []);
    if (args[0] === "scroll") assert.deepEqual([payload.x, payload.y], [-2.5, -300]);
    if (args[0] === "send") assert.equal(payload.request.id, -1);
  }
});

test("method safety classification and mutation gates remain unchanged", () => {
  for (const [method, safety] of [["DOM.getDocument", "safe"], ["Runtime.evaluate", "allow-unsafe-required"], ["Browser.close", "hard-blocked"]]) {
    const args = ["send", "--ws-url", "ws://127.0.0.1:9222/page/fixture", "--method", method];
    const dry = run("cdp-proxy.mjs", [...args, "--dry-run", "--json"]);
    assert.equal(JSON.parse(dry.stdout).safety, safety);
    assert.deepEqual(dry.calls, []);
    if (safety !== "safe") failBeforeTransport("cdp-proxy.mjs", args, /blocked|allow-unsafe/);
    if (safety === "hard-blocked") failBeforeTransport("cdp-proxy.mjs", [...args, "--allow-unsafe"], /blocked/);
  }
  for (const args of [["open", "https://fixture.invalid"], ["navigate", "fixture", "https://new.invalid"], ["back", "fixture"], ["click", "fixture", "#button"], ["scroll", "fixture"], ["close", "fixture"]]) failBeforeTransport("cdp-proxy.mjs", args, /allow-unsafe/);
  const allowed = run("cdp-proxy.mjs", ["open", "https://fixture.invalid", "--allow-unsafe", "--json"]);
  assert.equal(allowed.status, 0, allowed.stderr);
  assert.equal(allowed.calls[0].method, "PUT");
});

test("target prefix/url/title resolution and both send forms remain", () => {
  for (const target of ["fixture-", "https://fixture.invalid/app", "dashboard"]) {
    const result = run("cdp-proxy.mjs", ["send", target, "DOM.getDocument", '{"depth":1}', "--json"]);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(JSON.parse(result.stdout).target.id, "fixture-1");
    assert.deepEqual(result.calls.at(-1).params, { depth: 1 });
  }
  const flag = run("cdp-proxy.mjs", ["send", "--ws-url", "ws://127.0.0.1:9222/page/fixture", "--method", "DOM.getDocument", "--params", '{"depth":2}', "--id", "0", "--json"]);
  assert.equal(flag.status, 0, flag.stderr);
  assert.deepEqual(JSON.parse(flag.stdout).request.params, { depth: 2 });
  assert.equal(JSON.parse(flag.stdout).request.id, 0);
});

test("help remains available and command/parse/runtime errors use JSON consistently", () => {
  for (const [script, args] of [["find-url.mjs", ["--help"]], ["cdp-proxy.mjs", ["--help"]], ["cdp-proxy.mjs", ["list", "--help"]]]) {
    const result = run(script, args);
    assert.equal(result.status, 0);
    assert.match(result.stdout, /Usage:/);
    assert.deepEqual(result.calls, []);
  }
  assert.equal(failBeforeTransport("cdp-proxy.mjs", ["typo"], /Unknown command/).command, "typo");
  failBeforeTransport("cdp-proxy.mjs", ["send", "fixture", "DOM.getDocument", "{"], /Invalid JSON params/);
  const plain = run("find-url.mjs", ["--only", "typo"]);
  assert.equal(plain.status, 1);
  assert.equal(plain.stdout, "");
  assert.match(plain.stderr, /Invalid --only/);
});
