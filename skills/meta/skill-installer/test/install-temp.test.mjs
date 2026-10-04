import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = process.env.SKILL_INSTALLER_TEST_ROOT || fileURLToPath(new URL("../", import.meta.url));
const skillText = "---\nname: demo\ndescription: Fixture\n---\n";

async function fixture(t) {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), "skill-install-temp-test-"));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const sourceRoot = path.join(base, "skills"), home = path.join(base, "home");
  const input = path.join(base, "input"), temp = path.join(base, "temp");
  const target = path.join(sourceRoot, "core", "demo");
  for (const directory of [input, temp, path.dirname(target), path.join(home, ".codex", "skills")]) {
    await fs.mkdir(directory, { recursive: true });
  }
  await fs.writeFile(path.join(input, "SKILL.md"), skillText);
  await fs.writeFile(path.join(input, "resource.txt"), "resource content\n");
  // A sibling temporary directory is not owned by this invocation.
  await fs.mkdir(path.join(temp, "unrelated"));
  await fs.writeFile(path.join(temp, "unrelated", "keep.txt"), "keep\n");
  const preload = path.join(base, "offline.mjs");
  await fs.writeFile(preload, `import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import cp from "node:child_process";
import { syncBuiltinESMExports } from "node:module";
os.tmpdir = () => ${JSON.stringify(temp)};
globalThis.fetch = () => { throw new Error("Unexpected network execution"); };
cp.execFile = (file, args, callback) => {
  if (file !== "git" || args[0] !== "clone" || args[1] !== "--depth" || args[2] !== "1" || args.length !== 5) {
    throw new Error("Unexpected process execution");
  }
  (async () => {
    await fs.cp(${JSON.stringify(input)}, args[4], { recursive: true });
    if (process.env.OFFLINE_CLONE_FAULT === "clone") throw Object.assign(new Error("offline clone failed"), { code: 17 });
    return "";
  })().then(stdout => callback(null, stdout, ""), callback);
};
const copyFile = fs.copyFile.bind(fs);
fs.copyFile = async (source, destination, ...args) => {
  if (destination === ${JSON.stringify(path.join(target, "resource.txt"))} && process.env.OFFLINE_CLONE_FAULT === "copy") {
    throw Object.assign(new Error("offline copy failed"), { code: "EACCES" });
  }
  return copyFile(source, destination, ...args);
};
syncBuiltinESMExports();
`);
  return { base, sourceRoot, home, input, temp, target, preload };
}

function run(f, { fault = "", apply = true, category = "core", local = false, code } = {}) {
  const args = code ? ["--input-type=module", "--eval", code] : [
    path.join(root, "bin", "skill-installer.mjs"), "install", local ? f.input : "https://example.invalid/fixture.git",
    "--source-root", f.sourceRoot, "--home", f.home, "--category", category,
    "--tool", "codex", ...(apply ? ["--apply"] : []), "--json",
  ];
  return spawnSync(process.execPath, ["--import", f.preload, ...args], {
    encoding: "utf8", timeout: 15000,
    env: { ...process.env, HOME: f.home, USERPROFILE: f.home, AI_HOST_HOME: f.home,
      AI_SKILLS_HOME: f.sourceRoot, XDG_CONFIG_HOME: path.join(f.base, "config"),
      APPDATA: path.join(f.base, "config"), OFFLINE_CLONE_FAULT: fault },
  });
}

async function assertReleased(f) {
  assert.deepEqual(await fs.readdir(f.temp), ["unrelated"], "installer-owned clone directory must be released");
  assert.equal(await fs.readFile(path.join(f.temp, "unrelated", "keep.txt"), "utf8"), "keep\n");
  assert.equal(await fs.readFile(path.join(f.input, "resource.txt"), "utf8"), "resource content\n");
}

async function assertNotInstalled(f) {
  await assert.rejects(fs.lstat(f.target), { code: "ENOENT" });
  await assert.rejects(fs.lstat(path.join(f.home, ".codex", "skills", "demo")), { code: "ENOENT" });
}

for (const apply of [false, true]) {
  test(`clone failure releases partial checkout (apply=${apply})`, async t => {
    const f = await fixture(t);
    const result = run(f, { fault: "clone", apply });
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stderr, /offline clone failed/);
    await assertNotInstalled(f);
    await assertReleased(f);
  });

  test(`planning exception releases clone (apply=${apply})`, async t => {
    const f = await fixture(t);
    const result = run(f, { category: "missing-category", apply });
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stderr, /missing-category/);
    await assertNotInstalled(f);
    await assertReleased(f);
  });

  for (const conflict of ["invalid_source", "target_exists", "source_name_collision"]) {
    test(`${conflict} releases clone and preserves existing paths (apply=${apply})`, async t => {
      const f = await fixture(t);
      let preserved;
      if (conflict === "invalid_source") await fs.unlink(path.join(f.input, "SKILL.md"));
      if (conflict === "target_exists") {
        await fs.mkdir(f.target);
        preserved = path.join(f.target, "keep.txt");
        await fs.writeFile(preserved, "foreign\n");
      }
      if (conflict === "source_name_collision") {
        const collision = path.join(f.sourceRoot, "meta", "demo");
        await fs.mkdir(collision, { recursive: true });
        preserved = path.join(collision, "SKILL.md");
        await fs.writeFile(preserved, skillText);
      }
      const result = run(f, { apply });
      assert.equal(result.status, 2, result.stderr);
      assert.equal(JSON.parse(result.stdout).status, conflict);
      if (preserved) assert.equal(await fs.readFile(preserved, "utf8"), conflict === "target_exists" ? "foreign\n" : skillText);
      await assert.rejects(fs.lstat(path.join(f.home, ".codex", "skills", "demo")), { code: "ENOENT" });
      await assertReleased(f);
    });
  }
}

test("successful dry-run releases clone without installing", async t => {
  const f = await fixture(t);
  const result = run(f, { apply: false });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).status, "planned");
  await assertNotInstalled(f);
  await assertReleased(f);
});

for (const category of ["core", "incoming"]) {
  test(`successful ${category} apply keeps clone until every source file is copied`, async t => {
    const f = await fixture(t);
    const result = run(f, { category });
    assert.equal(result.status, 0, result.stderr);
    const report = JSON.parse(result.stdout);
    assert.equal(report.status, "installed");
    assert.equal(report.synced, category === "core");
    assert.equal(await fs.readFile(path.join(f.sourceRoot, category, "demo", "resource.txt"), "utf8"), "resource content\n");
    await assertReleased(f);
  });
}

test("copy failure releases clone after owned target cleanup", async t => {
  const f = await fixture(t);
  const result = run(f, { fault: "copy" });
  assert.equal(result.status, 2, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.status, "install_incomplete");
  assert.equal(report.installError.code, "EACCES");
  assert.equal(report.cleanup.status, "removed");
  await assertNotInstalled(f);
  await assertReleased(f);
});

test("incomplete host sync releases clone but preserves installed source and host conflict", async t => {
  const f = await fixture(t);
  const conflict = path.join(f.home, ".codex", "skills", "demo");
  await fs.mkdir(conflict);
  await fs.writeFile(path.join(conflict, "keep.txt"), "foreign\n");
  const result = run(f);
  assert.equal(result.status, 2, result.stderr);
  assert.equal(JSON.parse(result.stdout).status, "installed_sync_incomplete");
  assert.equal(await fs.readFile(path.join(f.target, "resource.txt"), "utf8"), "resource content\n");
  assert.equal(await fs.readFile(path.join(conflict, "keep.txt"), "utf8"), "foreign\n");
  await assertReleased(f);
});

test("apply rejection releases a previously retained prepared clone", async t => {
  const f = await fixture(t);
  const moduleUrl = pathToFileURL(path.join(root, "src", "install.mjs")).href;
  const result = run(f, { code: `import { buildInstallPlan, applyInstallPlan } from ${JSON.stringify(moduleUrl)};
import fs from "node:fs/promises";
const plan = await buildInstallPlan(${JSON.stringify({ installSource: "https://example.invalid/fixture.git",
      sourceRoot: f.sourceRoot, home: f.home, tools: ["codex"], category: "core", apply: true })});
await fs.access(plan.sourceSkillDir);
const result = await applyInstallPlan({ ...plan, ok: false });
process.stdout.write(JSON.stringify(result));` });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).applied, false);
  await assertNotInstalled(f);
  await assertReleased(f);
});

for (const apply of [false, true]) {
  test(`local source survives without clone cleanup (apply=${apply})`, async t => {
    const f = await fixture(t);
    const result = run(f, { local: true, apply });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(JSON.parse(result.stdout).inputType, "local");
    assert.equal(await fs.readFile(path.join(f.input, "SKILL.md"), "utf8"), skillText);
    await assertReleased(f);
  });
}
