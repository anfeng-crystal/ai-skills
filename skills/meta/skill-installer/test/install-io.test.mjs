import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = process.env.SKILL_INSTALLER_TEST_ROOT || fileURLToPath(new URL("../", import.meta.url));
const privateText = "PRIVATE INSTALL FAILURE CONTENT";

async function fixture(t) {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), "skill-install-io-"));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const sourceRoot = path.join(base, "skills"), home = path.join(base, "home"), input = path.join(base, "input");
  const target = path.join(sourceRoot, "core", "demo");
  await fs.mkdir(path.join(sourceRoot, "core"), { recursive: true });
  await fs.mkdir(input);
  await fs.mkdir(path.join(home, ".codex", "skills"), { recursive: true });
  await fs.writeFile(path.join(input, "SKILL.md"), "---\nname: demo\ndescription: Fixture\n---\n");
  await fs.writeFile(path.join(input, "z-extra.txt"), "supplement\n");
  const preload = path.join(base, "fault.mjs");
  await fs.writeFile(preload, `import fs from "node:fs/promises";
import cp from "node:child_process";
import { syncBuiltinESMExports } from "node:module";
cp.execFile = () => { throw new Error("Unexpected process execution"); };
syncBuiltinESMExports();
globalThis.fetch = () => { throw new Error("Unexpected network execution"); };
const target = ${JSON.stringify(target)}, phase = process.env.OFFLINE_INSTALL_FAULT;
const original = Object.fromEntries(["mkdir", "copyFile", "lstat", "unlink", "rmdir", "writeFile", "rename"].map(name => [name, fs[name].bind(fs)]));
const fail = () => { throw Object.assign(new Error(${JSON.stringify(privateText)}), { code: "EACCES" }); };
let copied = false, triggered = false;
fs.mkdir = async (file, ...args) => {
  if (file === target && !triggered) {
    triggered = true;
    if (phase === "race_directory") { await original.mkdir(target); await original.writeFile(target + "/keep.txt", "foreign"); }
    if (phase === "race_file") await original.writeFile(target, "foreign");
    if (phase === "race_symlink") await fs.symlink(target + "-missing", target);
    if (phase === "target_create") fail();
    if (phase === "target_create_after") { await original.mkdir(file, ...args); fail(); }
  }
  if (file === ${JSON.stringify(path.dirname(target))} && phase === "parent_create") fail();
  if (file === target + "/nested" && phase === "nested_create") fail();
  return original.mkdir(file, ...args);
};
fs.lstat = async (file, ...args) => {
  if (file === target && phase === "target_inspect" && triggered) fail();
  return original.lstat(file, ...args);
};
fs.copyFile = async (source, destination, ...args) => {
  if (destination === target + "/SKILL.md") copied = true;
  if (destination === target + "/z-extra.txt") {
    if (phase === "copy_after") { await original.copyFile(source, destination, ...args); fail(); }
    if (phase === "foreign_file") await original.writeFile(target + "/foreign.txt", "foreign");
    if (phase === "collision_file") await original.writeFile(destination, "foreign");
    if (phase === "replace_target") {
      await original.rename(target, target + "-moved");
      await original.mkdir(target);
      await original.writeFile(target + "/keep.txt", "foreign");
    }
    if (["copy", "foreign_file", "replace_target", "cleanup", "cleanup_after", "directory_cleanup"].includes(phase)) fail();
  }
  return original.copyFile(source, destination, ...args);
};
fs.unlink = async (file, ...args) => {
  if (copied && file === target + "/SKILL.md" && phase === "cleanup") fail();
  if (copied && file === target + "/SKILL.md" && phase === "cleanup_after") { await original.unlink(file, ...args); fail(); }
  return original.unlink(file, ...args);
};
fs.rmdir = async (file, ...args) => {
  if (file === target && phase === "directory_cleanup") fail();
  return original.rmdir(file, ...args);
};
`);
  return { base, sourceRoot, home, input, target, preload };
}

function run(f, phase = "", { apply = true, category = "core" } = {}) {
  const result = spawnSync(process.execPath, ["--import", f.preload, path.join(root, "bin/skill-installer.mjs"),
    "install", f.input, "--source-root", f.sourceRoot, "--home", f.home, "--category", category,
    "--tool", "codex", ...(apply ? ["--apply"] : []), "--json"], {
    encoding: "utf8", timeout: 15000, env: { ...process.env,
      HOME: f.home, USERPROFILE: f.home, AI_HOST_HOME: f.home, AI_SKILLS_HOME: f.sourceRoot,
      XDG_CONFIG_HOME: path.join(f.base, "config"), APPDATA: path.join(f.base, "config"),
      OFFLINE_INSTALL_FAULT: phase },
  });
  assert.doesNotMatch(result.stdout + result.stderr, /PRIVATE INSTALL/);
  assert.equal(result.stderr, "");
  return { exit: result.status, report: JSON.parse(result.stdout) };
}

async function exists(file) {
  try { await fs.lstat(file); return true; } catch (error) { if (error.code === "ENOENT") return false; throw error; }
}

async function assertNotSynced(f) {
  assert.equal(await exists(path.join(f.home, ".codex", "skills", "demo")), false);
}

test("failed second copy returns structured failure, removes owned paths and permits retry", async t => {
  const f = await fixture(t);
  const { exit, report } = run(f, "copy");
  assert.equal(exit, 2);
  assert.equal(report.status, "install_incomplete");
  assert.equal(report.ok, false);
  assert.equal(report.sourceInstalled, false);
  assert.equal(report.targetCreated, true);
  assert.equal(report.targetExists, false);
  assert.equal(report.installError.phase, "source_copy");
  assert.equal(report.installError.code, "EACCES");
  assert.equal(report.cleanup.status, "removed");
  assert.equal(await exists(f.target), false);
  await assertNotSynced(f);
  const retried = run(f);
  assert.equal(retried.exit, 0);
  assert.equal(retried.report.status, "installed");
  assert.equal(await fs.readFile(path.join(f.target, "z-extra.txt"), "utf8"), "supplement\n");
});

for (const phase of ["race_directory", "race_file", "race_symlink"]) {
  test(`${phase} after planning is neither overwritten nor cleaned`, async t => {
    const f = await fixture(t);
    const { exit, report } = run(f, phase);
    assert.equal(exit, 2);
    assert.equal(report.status, "target_exists");
    assert.equal(report.targetCreated, false);
    assert.equal(report.sourceInstalled, false);
    assert.equal(report.cleanup.status, "not_needed");
    if (phase === "race_directory") assert.deepEqual(await fs.readdir(f.target), ["keep.txt"]);
    if (phase === "race_file") assert.equal(await fs.readFile(f.target, "utf8"), "foreign");
    if (phase === "race_symlink") assert.equal(await fs.readlink(f.target), f.target + "-missing");
    await assertNotSynced(f);
  });
}

for (const kind of ["directory", "file", "symlink"]) {
  test(`existing ${kind} remains a planning conflict`, async t => {
    const f = await fixture(t);
    await fs.mkdir(path.dirname(f.target), { recursive: true });
    if (kind === "directory") await fs.mkdir(f.target);
    if (kind === "file") await fs.writeFile(f.target, "foreign");
    if (kind === "symlink") await fs.symlink(f.target + "-missing", f.target);
    const { exit, report } = run(f);
    assert.equal(exit, 2);
    assert.equal(report.status, "target_exists");
    assert.equal(report.applied, false);
    assert.equal(await exists(f.target), true);
    await assertNotSynced(f);
  });
}

for (const phase of ["parent_create", "target_create", "target_create_after", "target_inspect"]) {
  test(`${phase} reports uncertain creation honestly and never removes unowned paths`, async t => {
    const f = await fixture(t);
    const { exit, report } = run(f, phase);
    assert.equal(exit, 2);
    assert.equal(report.status, "install_incomplete");
    assert.equal(report.sourceInstalled, false);
    assert.equal(report.targetCreated, phase === "parent_create" ? false : phase === "target_inspect" ? true : null);
    assert.equal(report.cleanup.status, phase === "target_inspect" ? "incomplete" : "not_needed");
    if (phase === "target_inspect") assert.equal(report.targetExists, null);
    assert.equal(await exists(f.target), ["target_create_after", "target_inspect"].includes(phase));
    await assertNotSynced(f);
  });
}

for (const phase of ["foreign_file", "collision_file", "copy_after"]) {
  test(`${phase} keeps unknown content and reports incomplete cleanup`, async t => {
    const f = await fixture(t);
    const { exit, report } = run(f, phase);
    assert.equal(exit, 2);
    assert.equal(report.status, "install_incomplete");
    assert.equal(report.cleanup.status, "incomplete");
    assert.equal(report.targetExists, true);
    assert.equal(await exists(path.join(f.target, "SKILL.md")), false);
    const preserved = phase === "foreign_file" ? "foreign.txt" : "z-extra.txt";
    assert.equal(await fs.readFile(path.join(f.target, preserved), "utf8"), phase === "copy_after" ? "supplement\n" : "foreign");
    assert.equal(report.cleanup.errors.some(error => error.code === "ENOTEMPTY" || error.code === "EEXIST"), true);
    await assertNotSynced(f);
  });
}

test("replacement target identity prevents cleanup of either replacement or moved original", async t => {
  const f = await fixture(t);
  const { exit, report } = run(f, "replace_target");
  assert.equal(exit, 2);
  assert.equal(report.cleanup.status, "incomplete");
  assert.equal(report.cleanup.errors.some(error => error.code === "OWNERSHIP_CHANGED"), true);
  assert.deepEqual(await fs.readdir(f.target), ["keep.txt"]);
  assert.equal(await exists(path.join(f.target + "-moved", "SKILL.md")), true);
  await assertNotSynced(f);
});

for (const phase of ["cleanup", "cleanup_after", "directory_cleanup"]) {
  test(`${phase} error is reported separately from the copy failure`, async t => {
    const f = await fixture(t);
    const { exit, report } = run(f, phase);
    assert.equal(exit, 2);
    assert.equal(report.installError.code, "EACCES");
    assert.equal(report.cleanup.status, "incomplete");
    assert.equal(report.cleanup.errors.some(error => error.code === "EACCES"), true);
    assert.equal(await exists(f.target), phase !== "cleanup_after");
    assert.equal(report.targetExists, phase !== "cleanup_after");
    await assertNotSynced(f);
  });
}

test("nested directory creation failure cleans only successfully created paths", async t => {
  const f = await fixture(t);
  await fs.mkdir(path.join(f.input, "nested"));
  await fs.writeFile(path.join(f.input, "nested", "data.txt"), "nested");
  const { exit, report } = run(f, "nested_create");
  assert.equal(exit, 2);
  assert.equal(report.cleanup.status, "removed");
  assert.equal(await exists(f.target), false);
});

test("dry-run never starts target creation", async t => {
  const f = await fixture(t);
  const { exit, report } = run(f, "target_create", { apply: false });
  assert.equal(exit, 0);
  assert.equal(report.status, "planned");
  assert.equal(await exists(f.target), false);
});

test("incoming install and exclusions retain existing behavior", async t => {
  const f = await fixture(t);
  for (const name of [".git", "node_modules", "dist", ".cache", "tmp", "temp"]) {
    await fs.mkdir(path.join(f.input, name));
    await fs.writeFile(path.join(f.input, name, "ignored.txt"), "ignored");
  }
  await fs.writeFile(path.join(f.input, ".DS_Store"), "ignored");
  await fs.symlink(path.join(f.input, "SKILL.md"), path.join(f.input, "source-link"));
  const { exit, report } = run(f, "", { category: "incoming" });
  assert.equal(exit, 0);
  assert.equal(report.status, "installed");
  assert.equal(report.synced, false);
  assert.deepEqual((await fs.readdir(path.join(f.sourceRoot, "incoming", "demo"))).sort(), ["SKILL.md", "z-extra.txt"]);
  await assertNotSynced(f);
});
