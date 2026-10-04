import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = process.env.SKILL_INSTALLER_TEST_ROOT || fileURLToPath(new URL("../", import.meta.url));
const oldHash = "a".repeat(40), newHash = "b".repeat(40);
const oldText = "---\nname: fixture\ndescription: Before\n---\n";
const newText = "---\nname: fixture\ndescription: After\n---\n";
const secret = "PRIVATE_METADATA_CONTENT";

async function fixture(t, mode = "valid") {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), "skill-metadata-read-"));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const sourceRoot = path.join(base, "source"), home = path.join(base, "home");
  await fs.mkdir(home);
  for (const name of ["a", "b"]) {
    const dir = path.join(sourceRoot, "core", name);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(path.join(dir, "SKILL.md"), oldText);
    const file = path.join(dir, ".skill-meta.json");
    if (name === "a" && mode === "missing") continue;
    if (name === "a" && mode === "eisdir") { await fs.mkdir(file); continue; }
    await fs.writeFile(file, name === "a" && mode === "invalid_json" ? `{"private":"${secret}", BAD`
      : JSON.stringify({ source: { type: "git", url: "https://github.com/offline/metadata", path: name, branch: "main" }, lastUpstreamHash: oldHash }));
  }
  const preload = path.join(base, "offline.mjs");
  await fs.writeFile(preload, `import fs from "node:fs/promises";
import cp from "node:child_process";
import { promisify } from "node:util";
import { syncBuiltinESMExports } from "node:module";
const deny = () => { throw new Error("UNEXPECTED_PROCESS_EXECUTION"); };
for (const key of ["exec", "execSync", "execFileSync", "spawn", "spawnSync", "fork"]) cp[key] = deny;
const stub = deny;
stub[promisify.custom] = async (command, args) => {
  if (command !== "git" || args.join(" ") !== "ls-remote https://github.com/offline/metadata refs/heads/main") throw new Error("UNEXPECTED_PROCESS_EXECUTION");
  return { stdout: ${JSON.stringify(newHash + "\trefs/heads/main\n")} };
};
cp.execFile = stub;
syncBuiltinESMExports();
globalThis.fetch = async url => {
  if (!["a", "b"].some(name => url === "https://raw.githubusercontent.com/offline/metadata/${newHash}/" + name + "/SKILL.md")) throw new Error("UNEXPECTED_FETCH");
  return { ok: true, text: async () => ${JSON.stringify(newText)} };
};
const mode = ${JSON.stringify(mode)};
const metaFile = ${JSON.stringify(path.join(sourceRoot, "core/a/.skill-meta.json"))};
const sourceFile = ${JSON.stringify(path.join(sourceRoot, "core/a/SKILL.md"))};
const read = fs.readFile.bind(fs), write = fs.writeFile.bind(fs);
let sourceWritten = false;
fs.readFile = async (file, ...args) => {
  if (String(file) === metaFile) {
    if (mode === "eacces" || mode === "unknown_code" || (sourceWritten && mode === "eacces_after_source")) {
      throw Object.assign(new Error(${JSON.stringify(secret)}), { code: mode === "unknown_code" ? "PRIVATE_METADATA_CODE" : "EACCES" });
    }
    if (sourceWritten && mode === "invalid_after_source") return ${JSON.stringify(secret + " INVALID JSON")};
    if (sourceWritten && mode === "missing_after_source") throw Object.assign(new Error(${JSON.stringify(secret)}), { code: "ENOENT" });
  }
  return read(file, ...args);
};
fs.writeFile = async (file, ...args) => {
  const result = await write(file, ...args);
  if (String(file) === sourceFile) sourceWritten = true;
  return result;
};
`);
  return { base, sourceRoot, home, preload };
}

function run(f, args, json = true) {
  return child(f, [path.join(root, "bin/skill-installer.mjs"), ...args,
    "--source-root", f.sourceRoot, "--home", f.home, ...(json ? ["--json"] : [])]);
}

function child(f, args) {
  const result = spawnSync(process.execPath, ["--import", f.preload, ...args], {
    encoding: "utf8", timeout: 15000, cwd: f.base,
    env: { PATH: process.env.PATH, LANG: "C", HOME: f.home, USERPROFILE: f.home,
      AI_HOST_HOME: f.home, AI_SKILLS_HOME: f.sourceRoot, XDG_CONFIG_HOME: path.join(f.base, "config"), APPDATA: path.join(f.base, "config") },
  });
  assert.equal(result.error, undefined);
  assert.doesNotMatch(result.stdout + result.stderr, /PRIVATE_METADATA|UNEXPECTED_PROCESS_EXECUTION|UNEXPECTED_FETCH/);
  return result;
}

function reports(result, exitCode = 2) {
  assert.equal(result.status, exitCode, result.stderr);
  assert.equal(result.stderr, "");
  return result.stdout.trim().split(/\n(?=\{\n)/).map(JSON.parse);
}

async function state(f, name = "a") {
  const dir = path.join(f.sourceRoot, "core", name);
  const content = await fs.readFile(path.join(dir, "SKILL.md"), "utf8");
  let metadata;
  try { metadata = await fs.readFile(path.join(dir, ".skill-meta.json"), "utf8"); }
  catch (error) { metadata = error.code; }
  let history = [];
  try { history = (await fs.readFile(path.join(f.home, ".skill-installer/history.jsonl"), "utf8")).trim().split("\n").filter(Boolean).map(JSON.parse); }
  catch (error) { if (error.code !== "ENOENT") throw error; }
  return { content, metadata, history: history.filter(entry => entry.skill === `core/${name}`) };
}

for (const [mode, code] of [["invalid_json", "INVALID_METADATA_JSON"], ["eacces", "EACCES"], ["eisdir", "EISDIR"], ["unknown_code", "METADATA_READ_FAILED"]]) {
  test(`${mode} check remains visible through filtering and keeps later success`, async t => {
    const f = await fixture(t, mode), before = await state(f);
    const report = reports(run(f, ["--check-updates", "--only-updatable"]))[0];
    assert.equal(report.ok, false);
    assert.equal(report.summary.failed, 1);
    assert.equal(report.summary.noSource, 0);
    assert.equal(report.skills["core/b"].status, "updatable");
    assert.equal(report.checkErrors["core/a"].status, "check_failed");
    assert.equal(report.checkErrors["core/a"].code, code);
    assert.deepEqual(await state(f), before);
  });

  test(`${mode} explicit diff and update preserve independent later objects`, async t => {
    for (const command of ["diff", "update"]) {
      const f = await fixture(t, mode), before = await state(f);
      const [a, b] = reports(run(f, [command, "--skill", "core/a,core/b"]));
      assert.equal(a.status, "metadata_read_failed");
      assert.equal(a.ok, false);
      assert.equal(a.code, code);
      assert.equal(a.skill, "core/a");
      assert.equal(b.skill, "core/b");
      assert.equal(b.status, command === "diff" ? "updatable" : "updated");
      assert.deepEqual(await state(f), before);
    }
  });

  test(`${mode} automatic update keeps check error and updates only valid object`, async t => {
    const f = await fixture(t, mode), before = await state(f);
    const report = reports(run(f, ["update", "--all"]))[0];
    assert.equal(report.ok, false);
    assert.equal(report.checkErrors["core/a"].code, code);
    assert.equal(report.results.length, 1);
    assert.equal(report.results[0].skill, "core/b");
    assert.equal(report.results[0].status, "updated");
    assert.deepEqual(await state(f), before);
  });
}

test("all-invalid metadata never reports nothing to update", async t => {
  const f = await fixture(t, "invalid_json");
  await fs.rm(path.join(f.sourceRoot, "core/b"), { recursive: true });
  const report = reports(run(f, ["update", "--all"]))[0];
  assert.equal(report.status, "check_failed");
  assert.equal(report.ok, false);
  assert.equal(report.checkErrors["core/a"].code, "INVALID_METADATA_JSON");
});

test("missing metadata and valid JSON without source remain successful no-ops", async t => {
  for (const value of [undefined, {}, null, [], [1], "text", 1, true]) {
    const f = await fixture(t, "missing");
    if (value !== undefined) await fs.writeFile(path.join(f.sourceRoot, "core/a/.skill-meta.json"), JSON.stringify(value));
    const before = await state(f);
    for (const command of ["diff", "update"]) {
      const report = reports(run(f, [command, "core/a"]), 0)[0];
      assert.equal(report.status, command === "diff" ? "no_source" : "skipped");
    }
    assert.deepEqual(await state(f), before);
  }
});

for (const mode of ["eacces_after_source", "invalid_after_source", "missing_after_source"]) {
  test(`${mode} preserves confirmed source write and unattempted metadata write`, async t => {
    const f = await fixture(t, mode);
    const [a, b] = reports(run(f, ["update", "--skill", "core/a,core/b"]));
    assert.equal(a.status, "update_incomplete");
    assert.equal(a.sourceUpdated, true);
    assert.equal(a.metadataUpdated, false);
    assert.equal(a.updateHistoryRecorded, false);
    assert.equal(a.updateError.phase, "metadata_write");
    assert.equal(a.updateError.code, "METADATA_UNAVAILABLE");
    assert.equal(a.syncAttempted, false);
    assert.equal(b.status, "updated");
    const actual = await state(f);
    assert.equal(actual.content, newText);
    assert.equal(JSON.parse(actual.metadata).lastUpstreamHash, oldHash);
    assert.equal(actual.history.length, 0);
  });
}

test("metadata helper APIs reject unreadable data without overwriting it", async t => {
  for (const mode of ["invalid_json", "eacces"]) {
    const f = await fixture(t, mode), before = await state(f);
    const script = `import * as meta from ${JSON.stringify(pathToFileURL(path.join(root, "src/meta.mjs")).href)};
const results = [];
for (const method of ["readMeta", "recordSource", "updateLastChecked", "updateUpstreamHash"]) {
  try { await meta[method](${JSON.stringify(path.join(f.sourceRoot, "core/a"))}, method === "recordSource" ? { type: "local", url: "/offline" } : "hash"); results.push({ method, threw: false }); }
  catch (error) { results.push({ method, threw: true, name: error.name, code: error.code, message: error.message }); }
}
console.log(JSON.stringify(results));`;
    const result = child(f, ["--input-type=module", "--eval", script]);
    assert.equal(result.status, 0, result.stderr);
    const items = JSON.parse(result.stdout);
    assert.equal(items.length, 4);
    assert.ok(items.every(item => item.threw && item.name === "MetadataReadError"));
    assert.deepEqual(await state(f), before);
  }
});

test("dry-run still reports read errors while preserving all files", async t => {
  for (const args of [["--check-updates"], ["update", "--all"], ["update", "core/a"], ["diff", "core/a"]]) {
    const f = await fixture(t, "invalid_json"), beforeA = await state(f), beforeB = await state(f, "b");
    reports(run(f, [...args, "--dry-run"]));
    assert.deepEqual(await state(f), beforeA);
    assert.deepEqual(await state(f, "b"), beforeB);
  }
});

test("text diff identifies metadata error and continues later object", async t => {
  const f = await fixture(t, "invalid_json");
  const result = run(f, ["diff", "--skill", "core/a,core/b"], false);
  assert.equal(result.status, 2, result.stderr);
  assert.match(result.stdout, /core\/a: metadata_read_failed/);
  assert.match(result.stdout, /core\/b:/);
});

test("text explicit update identifies metadata error and its code", async t => {
  const f = await fixture(t, "invalid_json");
  const result = run(f, ["update", "--skill", "core/a,core/b"], false);
  assert.equal(result.status, 2, result.stderr);
  assert.match(result.stdout, /Skill: core\/a/);
  assert.match(result.stdout, /Status: metadata_read_failed/);
  assert.match(result.stdout, /Metadata error: INVALID_METADATA_JSON/);
  assert.match(result.stdout, /Status: updated/);
});
