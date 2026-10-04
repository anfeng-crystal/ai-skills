import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = process.env.SKILL_INSTALLER_TEST_ROOT || fileURLToPath(new URL("../", import.meta.url));
const privateText = "PRIVATE MIGRATION FAILURE CONTENT";

async function fixture(t, categories = {}) {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), "skill-migrate-io-"));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const sourceRoot = path.join(base, "source"), home = path.join(base, "home");
  await fs.mkdir(path.join(sourceRoot, "core", "unrelated"), { recursive: true });
  await fs.writeFile(path.join(sourceRoot, "core", "unrelated", "SKILL.md"), "---\nname: unrelated\n---\n");
  await fs.mkdir(path.join(home, ".codex", "skills"), { recursive: true });
  for (const name of ["a-one", "b-two", "c-three"]) {
    await fs.mkdir(path.join(sourceRoot, name));
    const category = categories[name] ?? "core";
    await fs.writeFile(path.join(sourceRoot, name, "SKILL.md"),
      `---\nname: ${name}\ndescription: Sample\n${category ? `tags: [${category}]\n` : ""}---\n`);
  }
  const preload = path.join(base, "fault.mjs");
  await fs.writeFile(preload, `import fs from "node:fs/promises";
import path from "node:path";
import cp from "node:child_process";
import { syncBuiltinESMExports } from "node:module";
cp.execFile = () => { throw new Error("Unexpected process execution"); };
syncBuiltinESMExports();
globalThis.fetch = () => { throw new Error("Unexpected network execution"); };
const sourceRoot = ${JSON.stringify(sourceRoot)};
const phase = process.env.OFFLINE_MIGRATE_PHASE;
const failAt = Number(process.env.OFFLINE_MIGRATE_INDEX || "2");
const originalMkdir = fs.mkdir.bind(fs), originalRename = fs.rename.bind(fs), originalSymlink = fs.symlink.bind(fs);
const fail = () => { throw Object.assign(new Error(${JSON.stringify(privateText)}),
  { code: process.env.OFFLINE_MIGRATE_CODE || "EACCES" }); };
let mkdirCount = 0, renameCount = 0;
fs.mkdir = async (file, ...args) => {
  if (path.dirname(file) === sourceRoot && phase === "mkdir" && ++mkdirCount === failAt) fail();
  return originalMkdir(file, ...args);
};
fs.rename = async (source, target, ...args) => {
  if (path.dirname(source) === sourceRoot && phase === "rename" && ++renameCount === failAt) fail();
  return originalRename(source, target, ...args);
};
fs.symlink = async (source, target, ...args) => {
  if (process.env.OFFLINE_SYNC_CODE && target.includes(path.join(".claude", "skills"))) {
    throw Object.assign(new Error("PRIVATE SYNC FAILURE CONTENT"), { code: process.env.OFFLINE_SYNC_CODE });
  }
  return originalSymlink(source, target, ...args);
};
`);
  return { base, sourceRoot, home, preload };
}

function run(f, { phase = "", index = 2, code = "EACCES", apply = true, json = true, tools = "codex", syncCode = "" } = {}) {
  const result = spawnSync(process.execPath, ["--import", f.preload, path.join(root, "bin/skill-installer.mjs"),
    "migrate", "--source-root", f.sourceRoot, "--home", f.home, "--tool", tools,
    apply ? "--apply" : "--dry-run", ...(json ? ["--json"] : [])], {
    encoding: "utf8", timeout: 15000, env: { ...process.env, AI_HOST_HOME: f.home, AI_SKILLS_HOME: f.sourceRoot,
      XDG_CONFIG_HOME: path.join(f.base, "config"), APPDATA: path.join(f.base, "config"),
      OFFLINE_MIGRATE_PHASE: phase, OFFLINE_MIGRATE_INDEX: String(index), OFFLINE_MIGRATE_CODE: code, OFFLINE_SYNC_CODE: syncCode },
  });
  assert.doesNotMatch(result.stdout + result.stderr, /PRIVATE MIGRATION|PRIVATE_CUSTOM_CODE|PRIVATE SYNC|PRIVATE_SYNC_CODE/);
  return result;
}

function incomplete(result) {
  assert.equal(result.status, 2, result.stderr);
  assert.equal(result.stderr, "");
  const report = JSON.parse(result.stdout);
  assert.equal(report.status, "migration_incomplete");
  assert.equal(report.ok, false);
  return report;
}

async function exists(file) {
  try { await fs.lstat(file); return true; }
  catch (error) { if (["ENOENT", "ENOTDIR"].includes(error.code)) return false; throw error; }
}

async function assertUnrelatedUnlinked(f) {
  assert.equal(await exists(path.join(f.home, ".codex", "skills", "unrelated")), false);
}

for (const phase of ["mkdir", "rename"]) {
  for (const index of [1, 2]) {
    test(`${phase} failure at item ${index} preserves moved, failed and unattempted states`, async t => {
      const f = await fixture(t);
      const report = incomplete(run(f, { phase, index }));
      assert.equal(report.applied, index === 2);
      assert.equal(report.synced, index === 2);
      assert.deepEqual(report.migrations.map(item => item.status),
        index === 1 ? ["failed", "planned", "planned"] : ["migrated", "failed", "planned"]);
      const failedName = index === 1 ? "a-one" : "b-two";
      assert.equal(report.migrationError.phase, phase);
      assert.equal(report.migrationError.code, "EACCES");
      assert.equal(report.migrationError.skillName, failedName);
      assert.equal(report.migrationError.sourcePath, path.join(f.sourceRoot, failedName));
      assert.equal(report.migrationError.targetPath, path.join(f.sourceRoot, "core", failedName));
      for (const [position, name] of ["a-one", "b-two", "c-three"].entries()) {
        const moved = position < index - 1;
        assert.equal(await exists(path.join(f.sourceRoot, name)), !moved);
        assert.equal(await exists(path.join(f.sourceRoot, "core", name)), moved);
        assert.equal(await exists(path.join(f.home, ".codex", "skills", name)), moved);
      }
      if (index === 2) {
        assert.deepEqual(report.syncVerification.records.map(item => item.skill), ["core/a-one"]);
        assert.equal(report.syncVerification.records[0].status, "already_linked");
      } else assert.equal(report.syncPlan, null);
      await assertUnrelatedUnlinked(f);
    });
  }
}

test("an existing file at the second category yields an exact mkdir failure and remains intact", async t => {
  const f = await fixture(t, { "b-two": "zeta" });
  const blocker = path.join(f.sourceRoot, "zeta");
  await fs.writeFile(blocker, "keep original category file\n");
  const report = incomplete(run(f));
  assert.equal(report.migrationError.phase, "mkdir");
  assert.equal(report.migrationError.code, "EEXIST");
  assert.equal(report.migrationError.targetPath, path.join(blocker, "b-two"));
  assert.deepEqual(report.migrations.map(item => item.status), ["migrated", "failed", "planned"]);
  assert.equal(report.synced, true);
  assert.equal(await fs.readFile(blocker, "utf8"), "keep original category file\n");
  assert.equal(await exists(path.join(f.sourceRoot, "b-two")), true);
  assert.equal(await exists(path.join(f.sourceRoot, "c-three")), true);
});

test("unrecognized migration error codes and messages are redacted", async t => {
  const f = await fixture(t);
  const report = incomplete(run(f, { phase: "rename", code: "PRIVATE_CUSTOM_CODE" }));
  assert.equal(report.migrationError.code, null);
  assert.equal(report.migrationError.message, "源目录迁移未确认完成");
});

test("text output retains completed and pending objects, failed phase, exact paths and sync outcome", async t => {
  const f = await fixture(t);
  const result = run(f, { phase: "rename", json: false });
  assert.equal(result.status, 2);
  assert.equal(result.stderr, "");
  assert.match(result.stdout, /a-one\tcore\tmigrated/);
  assert.match(result.stdout, /b-two\tcore\tfailed/);
  assert.match(result.stdout, /c-three\tcore\tplanned/);
  assert.match(result.stdout, /Status: migration_incomplete/);
  assert.match(result.stdout, /Migration error: b-two rename EACCES/);
  assert.ok(result.stdout.includes(`Source: ${path.join(f.sourceRoot, "b-two")}`));
  assert.ok(result.stdout.includes(`Target: ${path.join(f.sourceRoot, "core", "b-two")}`));
  assert.match(result.stdout, /Host sync: complete/);
});

test("a moved incoming object stays unlinked and does not cause a full sync after later failure", async t => {
  const f = await fixture(t, { "a-one": "" });
  const report = incomplete(run(f, { phase: "rename" }));
  assert.equal(report.migrations[0].category, "incoming");
  assert.equal(report.migrations[0].status, "migrated");
  assert.equal(report.applied, true);
  assert.equal(report.synced, false);
  assert.equal(report.syncPlan, null);
  assert.equal(await exists(path.join(f.sourceRoot, "incoming", "a-one")), true);
  assert.equal(await exists(path.join(f.home, ".codex", "skills", "a-one")), false);
  await assertUnrelatedUnlinked(f);
});

test("migration and host conflict evidence coexist while independent host sync succeeds", async t => {
  const f = await fixture(t);
  const conflict = path.join(f.home, ".codex", "skills", "a-one");
  await fs.mkdir(conflict);
  await fs.writeFile(path.join(conflict, "keep.txt"), "keep\n");
  await fs.mkdir(path.join(f.home, ".claude", "skills"), { recursive: true });
  const report = incomplete(run(f, { phase: "rename", tools: "codex,claude" }));
  assert.equal(report.applied, true);
  assert.equal(report.synced, false);
  assert.equal(report.migrationError.phase, "rename");
  assert.equal(report.syncVerification.records.find(item => item.tool === "codex").status, "real_path_conflict");
  assert.equal(report.syncVerification.records.find(item => item.tool === "claude").status, "already_linked");
  assert.equal(await fs.realpath(path.join(f.home, ".claude", "skills", "a-one")),
    await fs.realpath(path.join(f.sourceRoot, "core", "a-one")));
  assert.equal(await fs.readFile(path.join(conflict, "keep.txt"), "utf8"), "keep\n");
});

test("dry-run never reaches the injected move fault or changes source and links", async t => {
  const f = await fixture(t);
  const result = run(f, { phase: "rename", index: 1, apply: false });
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.ok, true);
  assert.equal(report.applied, false);
  assert.deepEqual(report.migrations.map(item => item.status), ["planned", "planned", "planned"]);
  assert.equal(report.migrationError, undefined);
  for (const name of ["a-one", "b-two", "c-three"]) {
    assert.equal(await exists(path.join(f.sourceRoot, name)), true);
    assert.equal(await exists(path.join(f.sourceRoot, "core", name)), false);
    assert.equal(await exists(path.join(f.home, ".codex", "skills", name)), false);
  }
});

test("pre-existing migration target blocks all moves even with a move failure configured", async t => {
  const f = await fixture(t);
  await fs.mkdir(path.join(f.sourceRoot, "core", "b-two"));
  const result = run(f, { phase: "rename", index: 1 });
  assert.equal(result.status, 2, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.applied, false);
  assert.equal(report.migrationError, undefined);
  assert.deepEqual(report.migrations.map(item => item.status), ["planned", "target_exists", "planned"]);
  for (const name of ["a-one", "b-two", "c-three"]) assert.equal(await exists(path.join(f.sourceRoot, name)), true);
  await assertUnrelatedUnlinked(f);
});

for (const { phase, json, code } of [
  { phase: "rename", json: true, code: "PRIVATE_SYNC_CODE" },
  { phase: "rename", json: false, code: "EACCES" },
  { phase: "", json: true, code: "EACCES" },
  { phase: "", json: false, code: "PRIVATE_SYNC_CODE" },
]) {
  test(`sync exception stays sanitized after ${phase ? "partial" : "complete"} migration in ${json ? "JSON" : "text"}`, async t => {
    const f = await fixture(t);
    await fs.mkdir(path.join(f.home, ".claude", "skills"), { recursive: true });
    const result = run(f, { phase, json, code: "EACCES", tools: "codex,claude", syncCode: code });
    assert.equal(result.status, 2, result.stderr);
    assert.equal(result.stderr, "");
    const status = phase ? "migration_incomplete" : "migrated_sync_incomplete";
    if (json) {
      const report = JSON.parse(result.stdout);
      assert.equal(report.status, status);
      assert.equal(report.ok, false);
      assert.equal(report.applied, true);
      assert.equal(report.synced, false);
      assert.equal(report.syncError.code, code === "EACCES" ? code : null);
      assert.equal(report.syncError.message, "宿主链接同步未确认完成");
      assert.deepEqual(report.migrations.map(item => item.status),
        phase ? ["migrated", "failed", "planned"] : ["migrated", "migrated", "migrated"]);
    } else {
      assert.match(result.stdout, /Host sync error:/);
      assert.ok(result.stdout.includes(code === "EACCES" ? "EACCES" : "unknown"));
      if (phase) assert.ok(result.stdout.includes(status));
    }
    assert.equal(await fs.realpath(path.join(f.home, ".codex", "skills", "a-one")),
      await fs.realpath(path.join(f.sourceRoot, "core", "a-one")));
    assert.equal(await exists(path.join(f.home, ".claude", "skills", "a-one")), false);
    assert.equal(await exists(path.join(f.sourceRoot, "b-two")), Boolean(phase));
    await assertUnrelatedUnlinked(f);
  });
}
