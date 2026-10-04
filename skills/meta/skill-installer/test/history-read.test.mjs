import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

// A frozen source root permits the same cases to demonstrate the old behavior.
const root = process.env.SKILL_HISTORY_TEST_ROOT || fileURLToPath(new URL("..", import.meta.url));
const moduleUrl = pathToFileURL(path.join(root, "src/history.mjs")).href;
const cli = path.join(root, "bin/skill-installer.mjs");
const oldRecord = { timestamp: "2026-01-01T00:00:00Z", action: "update", skill: "core/demo" };
const newRecord = { timestamp: "2026-02-01T00:00:00Z", action: "update", skill: "core/demo" };

async function fixture(t, content) {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), "history-read-"));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const home = path.join(base, "home");
  const source = path.join(base, "source");
  const history = path.join(home, ".skill-installer/history.jsonl");
  await fs.mkdir(path.dirname(history), { recursive: true });
  await fs.mkdir(source);
  if (content !== undefined) await fs.writeFile(history, content);
  const env = { ...process.env, HOME: home, USERPROFILE: home, AI_HOST_HOME: home,
    AI_SKILLS_HOME: source, XDG_CONFIG_HOME: path.join(base, "config"), APPDATA: path.join(base, "config") };
  return { base, home, source, history, env };
}

function runExport(f, expression) {
  const script = `import * as history from ${JSON.stringify(moduleUrl)};
try { console.log(JSON.stringify({ value: await (${expression}) })); }
catch (error) {
  console.log(JSON.stringify({ error: { code: error.code, lineNumber: error.lineNumber, message: error.message } }));
  process.exitCode = 1;
}`;
  const result = spawnSync(process.execPath, ["--input-type=module", "--eval", script], {
    encoding: "utf8", env: f.env,
  });
  assert.equal(result.error, undefined);
  return { ...result, payload: JSON.parse(result.stdout) };
}

function runCli(f, args = []) {
  return spawnSync(process.execPath, [cli, "history", ...args,
    "--source-root", f.source, "--home", f.home], { encoding: "utf8", env: f.env });
}

const invalidCases = [
  ["broken JSON", '{"PRIVATE_HISTORY_TOKEN":', "INVALID_HISTORY_JSON"],
  ["null", "null", "INVALID_HISTORY_RECORD"],
  ["false", "false", "INVALID_HISTORY_RECORD"],
  ["zero", "0", "INVALID_HISTORY_RECORD"],
  ["empty string", '""', "INVALID_HISTORY_RECORD"],
  ["true", "true", "INVALID_HISTORY_RECORD"],
  ["number", "7", "INVALID_HISTORY_RECORD"],
  ["string", '"PRIVATE_HISTORY_TOKEN"', "INVALID_HISTORY_RECORD"],
  ["empty array", "[]", "INVALID_HISTORY_RECORD"],
  ["array of records", JSON.stringify([newRecord]), "INVALID_HISTORY_RECORD"],
];

for (const [label, invalid, code] of invalidCases) {
  test(`history rejects ${label} without returning partial success or changing bytes`, async t => {
    const content = `${JSON.stringify(oldRecord)}\n\n${invalid}\n${JSON.stringify(newRecord)}\n`;
    const f = await fixture(t, content);
    const direct = runExport(f, "history.readHistory()");
    assert.equal(direct.status, 1);
    assert.deepEqual(direct.payload, { error: {
      code, lineNumber: 3, message: `${code}: 历史记录格式无效（第 3 行）`,
    } });
    const result = runCli(f, ["--json"]);
    assert.equal(result.status, 1);
    assert.equal(result.stdout, "");
    assert.equal(result.stderr.trim(), direct.payload.error.message);
    assert.equal((result.stdout + result.stderr).includes("PRIVATE_HISTORY_TOKEN"), false);
    assert.equal(await fs.readFile(f.history, "utf8"), content);
  });
}

test("text history reports a truncated final line using its original CRLF line number", async t => {
  const content = ` \r\n${JSON.stringify(oldRecord)}\r\n\t\r\n{"PRIVATE_HISTORY_TOKEN":`;
  const f = await fixture(t, content);
  const result = runCli(f);
  assert.equal(result.status, 1);
  assert.equal(result.stdout, "");
  assert.equal(result.stderr.trim(), "INVALID_HISTORY_JSON: 历史记录格式无效（第 4 行）");
  assert.equal(await fs.readFile(f.history, "utf8"), content);
});

for (const [label, expression] of [
  ["query filters and limits", 'history.queryHistory({ skill: "core/demo", action: "update", last: 1 })'],
  ["latest sync lookup", 'history.getLastSyncRecord("core/demo")'],
  ["cleanup", "history.cleanupHistory(1)"],
]) {
  test(`${label} cannot hide a malformed record and leaves history intact`, async t => {
    const content = `${JSON.stringify(oldRecord)}\n{"PRIVATE_HISTORY_TOKEN":\n${JSON.stringify(newRecord)}\n`;
    const f = await fixture(t, content);
    const result = runExport(f, expression);
    assert.equal(result.status, 1);
    assert.equal(result.payload.error.code, "INVALID_HISTORY_JSON");
    assert.equal(result.payload.error.lineNumber, 2);
    assert.equal(await fs.readFile(f.history, "utf8"), content);
  });
}

test("missing and blank histories remain successful empty results", async t => {
  const f = await fixture(t);
  assert.deepEqual(runExport(f, "history.readHistory()").payload, { value: [] });
  const absent = runCli(f, ["--json"]);
  assert.equal(absent.status, 0);
  assert.deepEqual(JSON.parse(absent.stdout), { total: 0, history: [] });
  assert.equal(runExport(f, 'history.getLastSyncRecord("core/demo")').payload.value, null);
  await assert.rejects(fs.stat(f.history), { code: "ENOENT" });
  await fs.writeFile(f.history, " \r\n\t\n\n");
  assert.deepEqual(runExport(f, "history.readHistory()").payload, { value: [] });
});

test("read preserves record order, unknown fields and legacy objects without a field schema", async t => {
  const records = [newRecord, {}, { custom: "legacy", nested: [1, null] }, oldRecord];
  const f = await fixture(t, `\n${records.map(JSON.stringify).join("\r\n\t\r\n")}\r\n`);
  const result = runExport(f, "history.readHistory()");
  assert.equal(result.status, 0);
  assert.deepEqual(result.payload.value, records);
});

test("query preserves sorting, skill/action filtering, limits and latest update selection", async t => {
  const other = { ...newRecord, skill: "core/other" };
  const sync = { ...newRecord, timestamp: "2026-03-01T00:00:00Z", action: "sync" };
  const f = await fixture(t, [oldRecord, other, sync, newRecord].map(JSON.stringify).join("\n"));
  const query = runExport(f, 'history.queryHistory({ skill: "core/demo", action: "update", last: 1 })');
  assert.equal(query.status, 0);
  assert.deepEqual(query.payload.value, { total: 1, history: [newRecord] });
  const all = runExport(f, 'history.queryHistory({ skill: "core/demo", last: 0 })');
  assert.deepEqual(all.payload.value, { total: 3, history: [sync, newRecord, oldRecord] });
  assert.deepEqual(runExport(f, 'history.getLastSyncRecord("core/demo")').payload.value, newRecord);
});

test("append remains readable and successful cleanup retains the latest records", async t => {
  const f = await fixture(t, `${JSON.stringify(oldRecord)}\n`);
  const result = runExport(f, `history.appendHistory(${JSON.stringify(newRecord)})`);
  assert.equal(result.status, 0);
  assert.deepEqual(result.payload.value, newRecord);
  assert.deepEqual(runExport(f, "history.readHistory()").payload.value, [oldRecord, newRecord]);
  assert.deepEqual(runExport(f, "history.cleanupHistory(1)").payload.value, { removed: 1 });
  assert.equal(await fs.readFile(f.history, "utf8"), `${JSON.stringify(newRecord)}\n`);
});
