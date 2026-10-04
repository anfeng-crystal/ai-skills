import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = process.env.SKILL_INSTALLER_TEST_ROOT || fileURLToPath(new URL("../", import.meta.url));
const cli = path.join(root, "bin/skill-installer.mjs");
const hash = "a".repeat(40);

async function fixture(t) {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), "skill-check-filter-"));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const sourceRoot = path.join(base, "source");
  const home = path.join(base, "home");
  const metas = {
    changed: { source: { type: "git", url: "https://github.com/offline/fixture" }, lastUpstreamHash: "old" },
    current: { source: { type: "git", url: "https://github.com/offline/fixture" }, lastUpstreamHash: hash },
    unknown: { source: { type: "git", url: "https://github.com/offline/fixture" } },
    plain: null,
    local: { source: { type: "local", url: path.join(sourceRoot, "plain") } },
    missing: { source: { type: "local", url: path.join(base, "missing") } },
  };
  for (const [name, meta] of Object.entries(metas)) {
    const dir = path.join(sourceRoot, name);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(path.join(dir, "SKILL.md"), `---\nname: ${name}\ndescription: Fixture\n---\n`);
    if (meta) await fs.writeFile(path.join(dir, ".skill-meta.json"), JSON.stringify(meta));
  }
  const preload = path.join(base, "offline.mjs");
  await fs.writeFile(preload, `import cp from "node:child_process";
import { promisify } from "node:util";
import { syncBuiltinESMExports } from "node:module";
const stub = () => { throw new Error("Unexpected process execution"); };
stub[promisify.custom] = async (command, args) => {
  if (command !== "git" || args[0] !== "ls-remote" || args[1] !== "https://github.com/offline/fixture") throw new Error("Unexpected execution");
  return { stdout: ${JSON.stringify(hash + "\trefs/heads/main\n")} };
};
cp.execFile = stub;
syncBuiltinESMExports();
globalThis.fetch = async () => { throw new Error("Unexpected network request"); };
`);
  return { base, home, sourceRoot, preload };
}

function run(f, flags = [], json = true) {
  return spawnSync(process.execPath, ["--import", f.preload, cli, "--check-updates", "--dry-run",
    "--source-root", f.sourceRoot, "--home", f.home, ...flags, ...(json ? ["--json"] : [])], {
    encoding: "utf8", env: { ...process.env, HOME: f.home, USERPROFILE: f.home,
      AI_HOST_HOME: f.home, AI_SKILLS_HOME: f.sourceRoot,
      XDG_CONFIG_HOME: path.join(f.base, "config"), APPDATA: path.join(f.base, "config") },
  });
}

test("only-updatable filters successful nonupdates while preserving failures and full summary", async t => {
  const f = await fixture(t);
  const result = run(f, ["--only-updatable"]);
  assert.equal(result.status, 2, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.ok, false);
  assert.deepEqual(Object.keys(report.skills), ["changed"]);
  assert.equal(report.skills.changed.status, "updatable");
  assert.deepEqual(Object.keys(report.checkErrors).sort(), ["missing", "unknown"]);
  assert.equal(report.checkErrors.unknown.status, "baseline_unknown");
  assert.equal(report.checkErrors.missing.status, "source_missing");
  assert.deepEqual(report.summary, { total: 6, updatable: 1, upToDate: 1, noSource: 1, local: 1, failed: 2 });
});

test("unfiltered output retains every checked skill and its existing shape", async t => {
  const f = await fixture(t);
  const result = run(f);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 2);
  assert.equal(Object.keys(report.skills).length, 6);
  assert.equal(report.checkErrors, undefined);
});

test("filtered text prints failures and updatable skills without nonupdate detail rows", async t => {
  const f = await fixture(t);
  const result = run(f, ["--only-updatable"], false);
  assert.equal(result.status, 2);
  assert.match(result.stdout, /changed: updatable/);
  assert.match(result.stdout, /unknown: baseline_unknown/);
  assert.match(result.stdout, /missing: source_missing/);
  assert.doesNotMatch(result.stdout, /(?:current|plain|local): /);
});

test("no updatable skills still reports successful checks and does not write in dry-run", async t => {
  const f = await fixture(t);
  const metaFile = path.join(f.sourceRoot, "current/.skill-meta.json");
  const before = await fs.readFile(metaFile, "utf8");
  const result = run(f, ["--only-updatable", "--skill", "current,local,plain"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(report.ok, true);
  assert.deepEqual(report.skills, {});
  assert.deepEqual(report.checkErrors, {});
  assert.equal(report.summary.total, 3);
  assert.equal(report.summary.failed, 0);
  assert.equal(await fs.readFile(metaFile, "utf8"), before);
});

test("missing explicit skill remains visible when all entries are filtered out", async t => {
  const f = await fixture(t);
  const result = run(f, ["--only-updatable", "--skill", "absent,current"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 2);
  assert.deepEqual(report.skills, {});
  assert.equal(report.checkErrors.absent.status, "missing_skill");
  assert.equal(report.summary.total, 2);
  assert.equal(report.summary.failed, 1);
});
