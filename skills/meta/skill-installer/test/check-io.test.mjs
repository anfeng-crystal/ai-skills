import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = process.env.SKILL_INSTALLER_TEST_ROOT || fileURLToPath(new URL("../", import.meta.url));
const oldHash = "a".repeat(40), newHash = "b".repeat(40);
const oldText = "---\nname: test\ndescription: Before\n---\n";
const newText = "---\nname: test\ndescription: After\n---\n";

async function fixture(t) {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), "skill-check-io-"));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const sourceRoot = path.join(base, "source"), home = path.join(base, "home");
  for (const name of ["a", "b"]) {
    const dir = path.join(sourceRoot, "core", name);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(path.join(dir, "SKILL.md"), oldText);
    await fs.writeFile(path.join(dir, ".skill-meta.json"), JSON.stringify({
      source: { type: "git", url: "https://github.com/offline/io", path: name }, lastUpstreamHash: oldHash,
    }));
  }
  const preload = path.join(base, "fault.mjs");
  await fs.writeFile(preload, `import fs from "node:fs/promises";
import cp from "node:child_process";
import { promisify } from "node:util";
import { syncBuiltinESMExports } from "node:module";
const stub = () => { throw new Error("Unexpected process execution"); };
stub[promisify.custom] = async (command, args) => {
  if (command !== "git" || args[0] !== "ls-remote" || args[1] !== "https://github.com/offline/io") throw new Error("Unexpected execution");
  return { stdout: ${JSON.stringify(newHash + "\trefs/heads/main\n")} };
};
cp.execFile = stub;
syncBuiltinESMExports();
globalThis.fetch = async url => {
  if (!url.startsWith("https://raw.githubusercontent.com/offline/io/${newHash}/")) throw new Error("Unexpected fetch");
  return { ok: true, text: async () => ${JSON.stringify(newText)} };
};
const write = fs.writeFile;
fs.writeFile = async (file, ...args) => {
  if (String(file) === ${JSON.stringify(path.join(sourceRoot, "core/a/.skill-meta.json"))}) {
    throw Object.assign(new Error("PRIVATE SOURCE CONTENT MUST NOT ESCAPE"), { code: "EACCES" });
  }
  return write(file, ...args);
};
`);
  return { base, sourceRoot, home, preload };
}

function run(f, args, json = true) {
  return spawnSync(process.execPath, ["--import", f.preload, path.join(root, "bin/skill-installer.mjs"),
    ...args, "--source-root", f.sourceRoot, "--home", f.home, ...(json ? ["--json"] : [])], {
    encoding: "utf8", env: { ...process.env, HOME: f.home, USERPROFILE: f.home,
      AI_HOST_HOME: f.home, AI_SKILLS_HOME: f.sourceRoot,
      XDG_CONFIG_HOME: path.join(f.base, "config"), APPDATA: path.join(f.base, "config") },
  });
}

test("check metadata write failure remains per-skill and later checks complete", async t => {
  const f = await fixture(t), result = run(f, ["--check-updates"]);
  assert.equal(result.status, 2, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.ok, false);
  assert.equal(report.skills["core/a"].status, "check_failed");
  assert.equal(report.skills["core/a"].code, "EACCES");
  assert.equal(report.skills["core/b"].status, "updatable");
  assert.equal(report.summary.total, 2);
  assert.equal(report.summary.failed, 1);
  assert.equal(report.summary.updatable, 1);
  assert.doesNotMatch(result.stdout + result.stderr, /PRIVATE SOURCE/);
  const meta = JSON.parse(await fs.readFile(path.join(f.sourceRoot, "core/b/.skill-meta.json")));
  assert.ok(meta.lastCheckedAt);
});

test("only-updatable exposes write failure while filtering successful checks", async t => {
  const f = await fixture(t), result = run(f, ["--check-updates", "--only-updatable"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 2);
  assert.deepEqual(Object.keys(report.skills), ["core/b"]);
  assert.equal(report.checkErrors["core/a"].status, "check_failed");
});

test("update all retains check error and continues the independent updatable skill", async t => {
  const f = await fixture(t), result = run(f, ["update", "--all"]);
  assert.equal(result.status, 2, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.ok, false);
  assert.equal(report.checkErrors["core/a"].status, "check_failed");
  assert.equal(report.results.length, 1);
  assert.equal(report.results[0].skill, "core/b");
  assert.equal(report.results[0].status, "updated");
  assert.equal(await fs.readFile(path.join(f.sourceRoot, "core/a/SKILL.md"), "utf8"), oldText);
  assert.equal(await fs.readFile(path.join(f.sourceRoot, "core/b/SKILL.md"), "utf8"), newText);
});

test("dry-run does not encounter write fault or change metadata", async t => {
  const f = await fixture(t), file = path.join(f.sourceRoot, "core/a/.skill-meta.json");
  const before = await fs.readFile(file, "utf8");
  const result = run(f, ["--check-updates", "--dry-run"]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).summary.updatable, 2);
  assert.equal(await fs.readFile(file, "utf8"), before);
});

test("text check output identifies failed and subsequent successful objects", async t => {
  const f = await fixture(t), result = run(f, ["--check-updates"], false);
  assert.equal(result.status, 2, result.stderr);
  assert.match(result.stdout, /core\/a: check_failed/);
  assert.match(result.stdout, /core\/b: updatable/);
  assert.doesNotMatch(result.stdout + result.stderr, /PRIVATE SOURCE/);
});
