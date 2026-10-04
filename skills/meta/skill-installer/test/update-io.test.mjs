import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = process.env.SKILL_INSTALLER_TEST_ROOT || fileURLToPath(new URL("../", import.meta.url));
const oldHash = "1".repeat(40), newHash = "2".repeat(40);
const oldText = "---\nname: fixture\ndescription: Old synthetic content\n---\n";
const newText = "---\nname: fixture\ndescription: New synthetic content\n---\n";
const secret = "PRIVATE PERSISTENCE CONTENT MUST NOT ESCAPE";

async function fixture(t) {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), "skill-update-io-"));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const sourceRoot = path.join(base, "source"), home = path.join(base, "home");
  await fs.mkdir(path.join(home, ".codex", "skills"), { recursive: true });
  for (const name of ["a", "b"]) {
    const dir = path.join(sourceRoot, "core", name);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(path.join(dir, "SKILL.md"), oldText);
    await fs.writeFile(path.join(dir, ".skill-meta.json"), JSON.stringify({
      source: { type: "git", url: "https://github.com/offline/io", path: name, branch: "main" },
      lastUpstreamHash: oldHash,
    }));
  }
  const preload = path.join(base, "fault.mjs");
  await fs.writeFile(preload, `import fs from "node:fs/promises";
import cp from "node:child_process";
import { promisify } from "node:util";
import { syncBuiltinESMExports } from "node:module";
const stub = () => { throw new Error("Unexpected process execution"); };
stub[promisify.custom] = async (command, args) => {
  if (command !== "git" || args.join(" ") !== "ls-remote https://github.com/offline/io refs/heads/main") throw new Error("Unexpected execution");
  return { stdout: ${JSON.stringify(newHash + "\trefs/heads/main\n")} };
};
cp.execFile = stub;
syncBuiltinESMExports();
globalThis.fetch = async url => {
  if (!["a", "b"].some(name => url === "https://raw.githubusercontent.com/offline/io/${newHash}/" + name + "/SKILL.md")) throw new Error("Unexpected fetch");
  return { ok: true, text: async () => ${JSON.stringify(newText)} };
};
const sourceFile = ${JSON.stringify(path.join(sourceRoot, "core/a/SKILL.md"))};
const metaFile = ${JSON.stringify(path.join(sourceRoot, "core/a/.skill-meta.json"))};
const historyFile = ${JSON.stringify(path.join(home, ".skill-installer/history.jsonl"))};
const phase = process.env.OFFLINE_FAULT_PHASE;
const timing = process.env.OFFLINE_FAULT_TIMING || "before";
const fail = () => { throw Object.assign(new Error(${JSON.stringify(secret)}), { code: process.env.OFFLINE_ERROR_CODE || "EACCES" }); };
const write = fs.writeFile.bind(fs), append = fs.appendFile.bind(fs), read = fs.readFile.bind(fs);
let sourceWritten = false;
async function fault(operation, file, data, args) {
  if (timing === "after") await operation(file, data, ...args);
  if (timing === "partial") await operation(file, String(data).slice(0, 7), ...args);
  fail();
}
fs.writeFile = async (file, data, ...args) => {
  if (file === sourceFile && phase === "source_write") return fault(write, file, data, args);
  if (file === metaFile && phase === "metadata_write" && JSON.parse(data).lastUpstreamHash === ${JSON.stringify(newHash)}) return fault(write, file, data, args);
  const result = await write(file, data, ...args);
  if (file === sourceFile) sourceWritten = true;
  return result;
};
fs.readFile = async (file, ...args) => {
  if (file === metaFile && phase === "metadata_missing" && sourceWritten) fail();
  return read(file, ...args);
};
fs.appendFile = async (file, data, ...args) => {
  if (file === historyFile) {
    const entry = JSON.parse(data);
    if (entry.skill === "core/a" && phase === entry.action + "_history") return fault(append, file, data, args);
  }
  return append(file, data, ...args);
};
if (process.env.OFFLINE_FAIL_SYNC === "1") {
  const symlink = fs.symlink.bind(fs);
  fs.symlink = async (source, target, ...args) => target.startsWith(${JSON.stringify(path.join(home, ".codex/skills/a.tmp-"))})
    ? fail() : symlink(source, target, ...args);
}
`);
  return { base, sourceRoot, home, preload };
}

function run(f, args, env = {}, json = true) {
  const result = spawnSync(process.execPath, ["--import", f.preload, path.join(root, "bin/skill-installer.mjs"),
    ...args, "--source-root", f.sourceRoot, "--home", f.home, ...(json ? ["--json"] : [])], {
    encoding: "utf8", timeout: 15000, env: { ...process.env, HOME: f.home, USERPROFILE: f.home,
      AI_HOST_HOME: f.home, AI_SKILLS_HOME: f.sourceRoot,
      XDG_CONFIG_HOME: path.join(f.base, "config"), APPDATA: path.join(f.base, "config"), ...env },
  });
  assert.doesNotMatch(result.stdout + result.stderr, /PRIVATE PERSISTENCE|PRIVATE_CUSTOM_CODE/);
  return result;
}

function reports(result) {
  assert.equal(result.status, 2, result.stderr);
  assert.equal(result.stderr, "");
  return result.stdout.trim().split(/\n(?=\{\n)/).map(JSON.parse);
}

async function state(f, skill) {
  const dir = path.join(f.sourceRoot, "core", skill);
  const content = await fs.readFile(path.join(dir, "SKILL.md"), "utf8");
  const metaText = await fs.readFile(path.join(dir, ".skill-meta.json"), "utf8");
  let meta = null;
  try { meta = JSON.parse(metaText); } catch {}
  let history = [];
  try {
    history = (await fs.readFile(path.join(f.home, ".skill-installer/history.jsonl"), "utf8"))
      .trim().split("\n").filter(Boolean).map(JSON.parse);
  } catch (error) { if (error.code !== "ENOENT") throw error; }
  return { content, meta, metaText, history: history.filter(item => item.skill === `core/${skill}`) };
}

for (const phase of ["source_write", "metadata_write", "update_history"]) {
  for (const timing of ["before", "after"]) {
    test(`${phase} ${timing} write keeps honest stage states and later automatic updates`, async t => {
      const f = await fixture(t);
      const report = reports(run(f, ["update", "--all"], { OFFLINE_FAULT_PHASE: phase, OFFLINE_FAULT_TIMING: timing }))[0];
      const [a, b] = report.results;
      assert.equal(report.ok, false);
      assert.deepEqual(report.summary, { total: 2, updated: 1, failed: 1, syncIncomplete: 0 });
      assert.equal(a.status, "update_incomplete");
      assert.equal(a.ok, false);
      assert.equal(a.updateError.phase, phase);
      assert.equal(a.updateError.code, "EACCES");
      assert.equal(a.sourceUpdated, phase === "source_write" ? null : true);
      assert.equal(a.metadataUpdated, phase === "source_write" ? false : phase === "metadata_write" ? null : true);
      assert.equal(a.updateHistoryRecorded, phase === "update_history" ? null : false);
      assert.equal(a.syncHistoryRecorded, false);
      assert.equal(a.syncAttempted, false);
      assert.equal(a.synced, false);
      assert.equal(a.fromHash, oldHash);
      assert.equal(a.toHash, newHash);
      assert.equal(b.status, "updated");
      assert.equal(b.updateHistoryRecorded, true);
      const actual = await state(f, "a");
      assert.equal(actual.content, phase === "source_write" && timing === "before" ? oldText : newText);
      assert.equal(actual.meta.lastUpstreamHash,
        phase === "update_history" || (phase === "metadata_write" && timing === "after") ? newHash : oldHash);
      assert.equal(actual.history.length, phase === "update_history" && timing === "after" ? 1 : 0);
      assert.equal((await state(f, "b")).content, newText);
    });
  }
}

for (const phase of ["source_write", "metadata_write"]) {
  test(`${phase} partial write is unknown and is neither rolled back nor claimed unchanged`, async t => {
    const f = await fixture(t);
    const report = reports(run(f, ["update", "core/a"], { OFFLINE_FAULT_PHASE: phase, OFFLINE_FAULT_TIMING: "partial" }))[0];
    const actual = await state(f, "a");
    assert.equal(report[phase === "source_write" ? "sourceUpdated" : "metadataUpdated"], null);
    assert.equal((phase === "source_write" ? actual.content : actual.metaText).length, 7);
    assert.equal(report.updateHistoryRecorded, false);
    assert.equal(report.syncAttempted, false);
  });
}

for (const timing of ["before", "after"]) {
  test(`sync history ${timing} append preserves completed links and subsequent skills`, async t => {
    const f = await fixture(t);
    const report = reports(run(f, ["update", "--all", "--sync", "--tool", "codex"], {
      OFFLINE_FAULT_PHASE: "sync_history", OFFLINE_FAULT_TIMING: timing,
    }))[0];
    const [a, b] = report.results;
    assert.equal(a.status, "update_incomplete");
    assert.equal(a.updateError.phase, "sync_history");
    assert.deepEqual([a.sourceUpdated, a.metadataUpdated, a.updateHistoryRecorded, a.syncHistoryRecorded], [true, true, true, null]);
    assert.equal(a.syncAttempted, true);
    assert.equal(a.synced, true);
    assert.deepEqual(a.syncedTools, ["codex"]);
    assert.equal(a.syncVerification.records[0].status, "already_linked");
    assert.equal(await fs.realpath(path.join(f.home, ".codex/skills/a")), await fs.realpath(path.join(f.sourceRoot, "core/a")));
    assert.equal((await state(f, "a")).history.length, timing === "after" ? 2 : 1);
    assert.equal(b.synced, true);
    assert.equal(b.syncHistoryRecorded, true);
    assert.deepEqual(report.summary, { total: 2, updated: 1, failed: 1, syncIncomplete: 0 });
  });
}

test("explicit skill batch emits both failure and independent success", async t => {
  const f = await fixture(t);
  const result = run(f, ["update", "--skill", "core/a,core/b"], { OFFLINE_FAULT_PHASE: "update_history" });
  const [a, b] = reports(result);
  assert.equal(a.skill, "core/a");
  assert.equal(a.updateError.phase, "update_history");
  assert.equal(b.skill, "core/b");
  assert.equal(b.status, "updated");
  assert.equal((await state(f, "b")).content, newText);
});

test("missing metadata during hash update is a failure rather than false confirmation", async t => {
  const f = await fixture(t);
  const a = reports(run(f, ["update", "core/a", "--sync", "--tool", "codex"], { OFFLINE_FAULT_PHASE: "metadata_missing" }))[0];
  assert.equal(a.status, "update_incomplete");
  assert.equal(a.sourceUpdated, true);
  assert.equal(a.metadataUpdated, false);
  assert.equal(a.updateError.phase, "metadata_write");
  assert.equal(a.updateError.code, "METADATA_UNAVAILABLE");
  assert.equal(a.updateHistoryRecorded, false);
  assert.equal(a.syncAttempted, false);
  assert.equal((await state(f, "a")).meta.lastUpstreamHash, oldHash);
  await assert.rejects(fs.lstat(path.join(f.home, ".codex/skills/a")), { code: "ENOENT" });
});

test("sync history failure does not erase incomplete synchronization or its aggregate count", async t => {
  const f = await fixture(t);
  await fs.mkdir(path.join(f.home, ".codex/skills/a"));
  const report = reports(run(f, ["update", "--all", "--sync", "--tool", "codex"], { OFFLINE_FAULT_PHASE: "sync_history" }))[0];
  const [a, b] = report.results;
  assert.equal(a.status, "update_incomplete");
  assert.equal(a.synced, false);
  assert.equal(a.syncVerification.records[0].status, "real_path_conflict");
  assert.equal(report.summary.syncIncomplete, 1);
  assert.equal(b.synced, true);
});

test("host sync exceptions and unknown persistence codes never expose arbitrary error data", async t => {
  const f = await fixture(t);
  const report = reports(run(f, ["update", "core/a", "--sync", "--tool", "codex"], {
    OFFLINE_FAULT_PHASE: "sync_history", OFFLINE_FAIL_SYNC: "1", OFFLINE_ERROR_CODE: "PRIVATE_CUSTOM_CODE",
  }))[0];
  assert.equal(report.updateError.code, null);
  assert.equal(report.syncError.code, null);
  assert.equal(report.syncError.phase, "host_sync");
  assert.equal(report.synced, false);
  assert.equal(report.syncHistoryRecorded, null);
  assert.equal(report.syncVerification.records[0].status, "planned");
});

test("text output names the failed skill, phase and unknown versus completed stages", async t => {
  const f = await fixture(t);
  const result = run(f, ["update", "--all"], { OFFLINE_FAULT_PHASE: "metadata_write" }, false);
  assert.equal(result.status, 2, result.stderr);
  assert.match(result.stdout, /Skill: core\/a/);
  assert.match(result.stdout, /Update error: metadata_write EACCES/);
  assert.match(result.stdout, /sourceUpdated=complete\tmetadataUpdated=unknown\tupdateHistoryRecorded=not_attempted/);
  assert.match(result.stdout, /Skill: core\/b/);
  assert.match(result.stdout, /Status: updated/);
});

for (const selected of [["core/a"], ["--all"]]) {
  test(`dry-run ${selected.join(" ")} never enters persistence or sync`, async t => {
    const f = await fixture(t), before = await state(f, "a");
    const result = run(f, ["update", ...selected, "--dry-run", "--sync", "--tool", "codex"], { OFFLINE_FAULT_PHASE: "source_write" });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(JSON.parse(result.stdout).status, "would_update");
    assert.deepEqual(await state(f, "a"), before);
    await assert.rejects(fs.lstat(path.join(f.home, ".codex/skills/a")), { code: "ENOENT" });
  });
}
