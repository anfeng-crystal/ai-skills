import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { buildInstallPlan, applyInstallPlan } from "../src/install.mjs";

async function fixture(t, conflict = false) {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), "skill-install-result-"));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const source = path.join(base, "source");
  const sourceRoot = path.join(base, "active");
  const home = path.join(base, "home");
  await fs.mkdir(source);
  await fs.mkdir(path.join(sourceRoot, "core"), { recursive: true });
  await fs.mkdir(path.join(home, ".codex", "skills"), { recursive: true });
  await fs.mkdir(path.join(home, ".claude", "skills"), { recursive: true });
  await fs.writeFile(path.join(source, "SKILL.md"), "---\nname: demo\ndescription: Demo\n---\n");
  if (conflict) {
    await fs.mkdir(path.join(home, ".codex", "skills", "demo"));
    await fs.writeFile(path.join(home, ".codex", "skills", "demo", "keep.txt"), "existing data");
  }
  return { source, sourceRoot, home, options: {
    installSource: source, sourceRoot, home, category: "core", tools: ["codex", "claude"],
    skills: [], config: {}, apply: true,
  } };
}

test("partial host sync reports source installation and retains independent successes", async (t) => {
  const { options, sourceRoot, home } = await fixture(t, true);
  const result = await applyInstallPlan(await buildInstallPlan(options));
  assert.equal(result.ok, false);
  assert.equal(result.status, "installed_sync_incomplete");
  assert.equal(result.applied, true);
  assert.equal(result.sourceInstalled, true);
  assert.equal(result.synced, false);
  assert.equal(result.syncVerification.records.find((record) => record.tool === "codex").status, "real_path_conflict");
  assert.equal(result.syncVerification.records.find((record) => record.tool === "claude").status, "already_linked");
  assert.equal(await fs.readFile(path.join(home, ".codex", "skills", "demo", "keep.txt"), "utf8"), "existing data");
  assert.equal(await fs.realpath(path.join(home, ".claude", "skills", "demo")), await fs.realpath(path.join(sourceRoot, "core", "demo")));
  assert.ok(await fs.stat(path.join(sourceRoot, "core", "demo", "SKILL.md")));
});

test("successful installation verifies all requested links", async (t) => {
  const { options } = await fixture(t);
  const result = await applyInstallPlan(await buildInstallPlan(options));
  assert.equal(result.ok, true);
  assert.equal(result.status, "installed");
  assert.equal(result.synced, true);
  assert.equal(result.syncVerification.records.length, 2);
  assert.ok(result.syncVerification.records.every((record) => record.status === "already_linked"));
});

test("CLI returns nonzero and actionable JSON for partial installation", async (t) => {
  const { source, sourceRoot, home } = await fixture(t, true);
  const cli = fileURLToPath(new URL("../bin/skill-installer.mjs", import.meta.url));
  const result = spawnSync(process.execPath, [cli, "install", source, "--source-root", sourceRoot,
    "--home", home, "--category", "core", "--tool", "codex", "--apply", "--json"], { encoding: "utf8" });
  assert.equal(result.status, 2, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.status, "installed_sync_incomplete");
  assert.equal(report.sourceInstalled, true);
  assert.equal(report.syncVerification.records[0].status, "real_path_conflict");
});
