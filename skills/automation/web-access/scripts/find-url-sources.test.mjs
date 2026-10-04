import test, { after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const scripts = path.dirname(fileURLToPath(import.meta.url));
const fixture = fs.mkdtempSync(path.join(os.tmpdir(), "find-url-sources-test-"));
after(() => fs.rmSync(fixture, { recursive: true, force: true }));
const guard = path.join(fixture, "guard.mjs");
fs.writeFileSync(guard, `
import fs from 'node:fs';
import os from 'node:os';
import cp from 'node:child_process';
import { syncBuiltinESMExports } from 'node:module';
os.homedir = () => process.env.FIXTURE_HOME;
const realRead = fs.readFileSync;
fs.readFileSync = (file, ...args) => {
  if (String(file) === process.env.FAIL_READ) throw Object.assign(new Error('synthetic permission failure'), { code: 'EACCES' });
  return realRead(file, ...args);
};
const realReaddir = fs.readdirSync;
fs.readdirSync = (file, ...args) => {
  if (String(file) === process.env.FAIL_DISCOVERY) throw Object.assign(new Error('synthetic permission failure'), { code: 'EACCES' });
  return realReaddir(file, ...args);
};
if (process.env.FAIL_PYTHON) cp.spawnSync = () => ({ status: null, error: { code: 'ENOENT' } });
syncBuiltinESMExports();
globalThis.fetch = async () => {
  if (!process.env.ALLOW_TARGET_FIXTURE) throw new Error('network forbidden by fixture');
  return { ok: true, json: async () => [
    { id: 'fixture', type: 'page', title: 'Fixture target', url: 'https://fixture.invalid/target' },
    { id: 'devtools', type: 'page', title: 'Fixture tools', url: 'devtools://inspect' }
  ] };
};
`);

let sequence = 0;
function scenario() {
  const root = path.join(fixture, String(sequence++));
  const home = path.join(root, "home");
  fs.mkdirSync(home, { recursive: true });
  const file = (name, value) => {
    const target = path.join(root, name);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, value);
    return target;
  };
  const run = (args, overrides = {}) => {
    const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith("WEB_ACCESS_")));
    const result = spawnSync(process.execPath, ["--import", guard, path.join(scripts, "find-url.mjs"), ...args], {
      env: { ...env, FIXTURE_HOME: home, LOCALAPPDATA: path.join(home, "AppData/Local"), ...overrides },
      encoding: "utf8", timeout: 10000,
    });
    assert.equal(result.error, undefined);
    return result;
  };
  return { root, home, file, run };
}

function bookmark(title = "Fixture bookmark", url = "https://fixture.invalid/bookmark") {
  return JSON.stringify({ roots: { bookmark_bar: { type: "folder", name: "Fixture folder", children: [
    { type: "url", name: title, url, date_added: "13401072000000000" },
  ] } } });
}

function database(file, rows = []) {
  const result = spawnSync("python3", ["-c", `
import json,sqlite3,sys
conn=sqlite3.connect(sys.argv[1])
conn.execute('CREATE TABLE urls(url TEXT,title TEXT,visit_count INTEGER,last_visit_time INTEGER)')
conn.executemany('INSERT INTO urls VALUES(?,?,?,?)',json.loads(sys.argv[2]))
conn.commit()
conn.close()
`, file, JSON.stringify(rows)], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  return file;
}

function failed(result, source, code, partial = false) {
  assert.equal(result.status, 1, result.stdout + result.stderr);
  assert.equal(result.stderr, "");
  const value = JSON.parse(result.stdout);
  assert.equal(value.ok, false);
  assert.equal(value.command, "find-url");
  assert.equal(value.partial, partial);
  assert.ok(value.errors.some((error) => error.source === source && error.code === code), result.stdout);
  return value;
}

function chromeRoot(home) {
  if (process.platform === "darwin") return path.join(home, "Library/Application Support/Google/Chrome");
  if (process.platform === "win32") return path.join(home, "AppData/Local/Google/Chrome/User Data");
  return path.join(home, ".config/google-chrome");
}

test("explicit missing and corrupt local sources fail without quoting file contents", () => {
  const ctx = scenario();
  for (const [source, flag, name] of [["bookmarks", "--bookmarks-path", "Bookmarks"], ["history", "--history-path", "History"]]) {
    const missing = path.join(ctx.root, name);
    assert.deepEqual(failed(ctx.run(["--only", source, flag, missing, "--json"]), source, "ENOENT").results, []);
    const corrupt = ctx.file(name, '{"private_marker":"SYNTHETIC_SECRET",');
    const result = ctx.run(["--only", source, flag, corrupt, "--json"]);
    failed(result, source, source === "bookmarks" ? "INVALID_JSON" : "SQLITE_ERROR");
    assert.doesNotMatch(result.stdout + result.stderr, /SYNTHETIC_SECRET/);
  }
});

test("invalid Bookmarks root shape fails while legitimate empty sources keep array contract", () => {
  const ctx = scenario();
  for (const value of ["null", "[]", "{}", '{"roots":[]}']) {
    failed(ctx.run(["--only", "bookmarks", "--bookmarks-path", ctx.file("Bookmarks", value), "--json"]), "bookmarks", "INVALID_BOOKMARKS");
  }
  const bookmarks = ctx.file("Bookmarks", '{"roots":{}}');
  const history = database(path.join(ctx.root, "History"));
  const result = ctx.run(["--only", "chrome", "--bookmarks-path", bookmarks, "--history-path", history, "--json"]);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), []);
});

test("explicit profile requires selected files, default absent browsers and optional files do not fail", () => {
  const ctx = scenario();
  const profile = path.join(ctx.root, "explicit-profile");
  const result = failed(ctx.run(["--only", "chrome", "--profile-dir", profile, "--json"]), "bookmarks", "ENOENT");
  assert.ok(result.errors.some((error) => error.source === "history" && error.code === "ENOENT"));
  fs.mkdirSync(path.join(chromeRoot(ctx.home), "Default"), { recursive: true });
  const empty = ctx.run(["--only", "chrome", "--json"]);
  assert.equal(empty.status, 0, empty.stdout + empty.stderr);
  assert.deepEqual(JSON.parse(empty.stdout), []);
});

test("permission failure during discovery or read is visible and dry-run does not read source content", () => {
  const ctx = scenario();
  const bookmarks = ctx.file("Bookmarks", bookmark());
  failed(ctx.run(["--only", "bookmarks", "--bookmarks-path", bookmarks, "--json"], { FAIL_READ: bookmarks }), "bookmarks", "EACCES");
  failed(ctx.run(["--only", "bookmarks", "--json"], { FAIL_DISCOVERY: chromeRoot(ctx.home) }), "bookmarks", "EACCES");
  const planned = ctx.run(["--only", "bookmarks", "--bookmarks-path", bookmarks, "--dry-run", "--json"], { FAIL_READ: bookmarks });
  assert.equal(planned.status, 0, planned.stdout + planned.stderr);
  assert.equal(JSON.parse(planned.stdout).dryRun, true);
});

test("partial local success retains matching records and marks successful empty sources", () => {
  const ctx = scenario();
  const bookmarks = ctx.file("Bookmarks", bookmark());
  const history = ctx.file("History", "corrupt fixture");
  const args = ["--only", "chrome", "--bookmarks-path", bookmarks, "--history-path", history];
  const value = failed(ctx.run([...args, "--contains", "fixture", "--json"]), "history", "SQLITE_ERROR", true);
  assert.equal(value.results.length, 1);
  assert.equal(value.results[0].folder, "Fixture folder");
  assert.equal(typeof value.results[0].addedAt, "string");
  assert.deepEqual(failed(ctx.run([...args, "--contains", "no-match", "--json"]), "history", "SQLITE_ERROR", true).results, []);
  const text = ctx.run([...args, "--value", "url"]);
  assert.equal(text.status, 1);
  assert.match(text.stdout, /https:\/\/fixture.invalid\/bookmark/);
  assert.match(text.stderr, /history: SQLITE_ERROR/);
  assert.doesNotMatch(text.stdout, /No matching results/);
});

test("default multi-profile discovery retains healthy bookmarks alongside corrupt profile", () => {
  const ctx = scenario();
  const root = chromeRoot(ctx.home);
  for (const [profile, content] of [["Default", bookmark()], ["Profile 2", "broken fixture"]]) {
    fs.mkdirSync(path.join(root, profile), { recursive: true });
    fs.writeFileSync(path.join(root, profile, "Bookmarks"), content);
  }
  const value = failed(ctx.run(["--only", "bookmarks", "--json"]), "bookmarks", "INVALID_JSON", true);
  assert.equal(value.results.length, 1);
  assert.equal(value.results[0].profile, "Default");
});

test("valid history keeps since, visits, recent, title matching, first and output fields", () => {
  const ctx = scenario();
  const micros = (iso) => (Date.parse(iso) + 11644473600000) * 1000;
  const history = database(path.join(ctx.root, "History"), [
    ["https://fixture.invalid/older", "Fixture older", 100, micros("2026-09-01")],
    ["https://fixture.invalid/newer", "Fixture newer", 2, micros("2026-10-01")],
  ]);
  const args = ["--only", "history", "--history-path", history];
  const visits = ctx.run([...args, "--sort", "visits", "--first", "--json"]);
  assert.equal(visits.status, 0, visits.stdout + visits.stderr);
  assert.match(JSON.parse(visits.stdout)[0].url, /older/);
  const recent = ctx.run([...args, "--sort", "recent", "--limit", "1", "--json"]);
  assert.match(JSON.parse(recent.stdout)[0].url, /newer/);
  const since = ctx.run([...args, "--since", "2026-09-15", "--title", "newer", "--value", "url"]);
  assert.equal(since.status, 0, since.stdout + since.stderr);
  assert.equal(since.stdout.trim(), "https://fixture.invalid/newer");
});

test("history schema failures and missing python retain bookmark results", () => {
  const ctx = scenario();
  const bookmarks = ctx.file("Bookmarks", bookmark());
  const history = ctx.file("History", "");
  const args = ["--only", "chrome", "--bookmarks-path", bookmarks, "--history-path", history, "--json"];
  assert.equal(failed(ctx.run(args), "history", "SQLITE_ERROR", true).results.length, 1);
  assert.equal(failed(ctx.run(args, { FAIL_PYTHON: "1" }), "history", "ENOENT", true).results.length, 1);
});

test("all-source partial failure keeps target order, filters devtools and respects limit", () => {
  const ctx = scenario();
  const bookmarks = ctx.file("Bookmarks", bookmark());
  const history = ctx.file("History", "corrupt");
  const args = ["--only", "all", "--bookmarks-path", bookmarks, "--history-path", history, "--json"];
  const value = failed(ctx.run(args, { ALLOW_TARGET_FIXTURE: "1" }), "history", "SQLITE_ERROR", true);
  assert.deepEqual(value.results.map((item) => item.source), ["target", "bookmark"]);
  const limited = failed(ctx.run([...args, "--limit", "1"], { ALLOW_TARGET_FIXTURE: "1" }), "history", "SQLITE_ERROR", true);
  assert.deepEqual(limited.results.map((item) => item.source), ["target"]);
});
