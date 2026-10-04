import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { parseArgs } from "../src/cli.mjs";
import { linkTypeForPlatform } from "../src/sync-links.mjs";

const cli = fileURLToPath(new URL("../bin/skill-installer.mjs", import.meta.url));
const skillText = "---\nname: demo\ndescription: Demo\ntags: [core]\n---\n";

async function fixture(t) {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), "skill-cli-result-"));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const sourceRoot = path.join(base, "source");
  const source = path.join(sourceRoot, "core", "demo");
  const home = path.join(base, "home");
  const targetRoot = path.join(home, ".codex", "skills");
  const target = path.join(targetRoot, "demo");
  await fs.mkdir(source, { recursive: true });
  await fs.mkdir(targetRoot, { recursive: true });
  await fs.writeFile(path.join(source, "SKILL.md"), skillText);
  return { base, sourceRoot, source, home, targetRoot, target };
}

function run(f, args, nodeArgs = []) {
  return spawnSync(process.execPath, [...nodeArgs, cli, ...args, "--source-root", f.sourceRoot,
    "--home", f.home, "--json"], {
    encoding: "utf8",
    env: { ...process.env, HOME: f.home, USERPROFILE: f.home, AI_SKILLS_HOME: f.sourceRoot, AI_HOST_HOME: f.home,
      XDG_CONFIG_HOME: path.join(f.base, "config"), APPDATA: path.join(f.base, "config") },
  });
}

for (const kind of ["directory", "external_symlink"]) {
  test(`remove dry-run preserves ${kind} conflict and returns exit 2`, async (t) => {
    const f = await fixture(t);
    if (kind === "directory") {
      await fs.mkdir(f.target);
      await fs.writeFile(path.join(f.target, "keep.txt"), "keep");
    } else {
      const external = path.join(f.base, "external");
      await fs.mkdir(external);
      await fs.symlink(external, f.target, linkTypeForPlatform());
    }
    const result = run(f, ["remove", "demo", "--tool", "codex", "--dry-run"]);
    const report = JSON.parse(result.stdout);
    assert.equal(report.ok, false);
    assert.equal(report.applied, false);
    assert.equal(report.records[0].status,
      kind === "directory" ? "real_path_conflict" : "external_symlink_conflict");
    assert.ok(await fs.lstat(f.target));
    assert.equal(result.status, 2, result.stderr);
  });
}

for (const mode of ["--dry-run", "--apply"]) {
  test(`migrate ${mode} preserves conflicting source directories and returns exit 2`, async (t) => {
    const f = await fixture(t);
    const oldSource = path.join(f.sourceRoot, "demo");
    await fs.mkdir(oldSource);
    await fs.writeFile(path.join(oldSource, "SKILL.md"), skillText);
    const result = run(f, ["migrate", "--tool", "codex", mode]);
    const report = JSON.parse(result.stdout);
    assert.equal(report.ok, false);
    assert.equal(report.applied, false);
    assert.equal(report.migrations[0].status, "target_exists");
    assert.equal(await fs.readFile(path.join(oldSource, "SKILL.md"), "utf8"), skillText);
    assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), skillText);
    assert.equal(result.status, 2, result.stderr);
  });
}

for (const args of [["--dry-run"], ["--apply", "--purge"]]) {
  test(`remove rejects unknown tool for ${args.join(" ")}`, async (t) => {
    const f = await fixture(t);
    const result = run(f, ["remove", "core/demo", "--tool", "unknown-host", ...args]);
    const report = JSON.parse(result.stdout);
    assert.equal(report.records[0].status, "invalid_tool");
    assert.equal(report.ok, false);
    assert.equal(report.applied, false);
    assert.equal(result.status, 2, result.stderr);
    assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), skillText);
  });
}

for (const flags of [["--dry-run", "--apply"], ["--apply", "--dry-run"]]) {
  test(`mutually exclusive write flags are rejected: ${flags.join(" ")}`, () => {
    assert.throws(() => parseArgs(flags, { sourceRoot: os.tmpdir(), home: os.tmpdir() }),
      /--dry-run.*--apply|--apply.*--dry-run/);
  });
}

test("CLI rejects conflicting write flags before changing links", async (t) => {
  const f = await fixture(t);
  const result = run(f, ["--skill", "demo", "--tool", "codex", "--dry-run", "--apply"]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /--dry-run.*--apply|--apply.*--dry-run/);
  await assert.rejects(fs.lstat(f.target), { code: "ENOENT" });
});

test("successful sync preview stays read-only and explicit apply creates its selected link", async (t) => {
  const f = await fixture(t);
  const preview = run(f, ["--skill", "demo", "--tool", "codex", "--dry-run"]);
  assert.equal(preview.status, 0, preview.stderr);
  assert.equal(JSON.parse(preview.stdout).records[0].status, "planned");
  await assert.rejects(fs.lstat(f.target), { code: "ENOENT" });
  const applied = run(f, ["--skill", "demo", "--tool", "codex", "--apply"]);
  assert.equal(applied.status, 0, applied.stderr);
  assert.equal(JSON.parse(applied.stdout).records[0].status, "applied");
  assert.equal(await fs.realpath(f.target), await fs.realpath(f.source));
  const verified = run(f, ["--skill", "demo", "--tool", "codex", "--dry-run"]);
  assert.equal(verified.status, 0, verified.stderr);
  assert.equal(JSON.parse(verified.stdout).records[0].status, "already_linked");
});

test("successful remove preview keeps its managed link and returns exit 0", async (t) => {
  const f = await fixture(t);
  await fs.symlink(f.source, f.target, linkTypeForPlatform());
  const result = run(f, ["remove", "demo", "--tool", "codex", "--dry-run"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(report.ok, true);
  assert.equal(report.applied, false);
  assert.equal(report.records[0].action, "remove_link");
  assert.equal(await fs.realpath(f.target), await fs.realpath(f.source));
});


async function writeSourceMeta(f, source) {
  await fs.writeFile(path.join(f.source, ".skill-meta.json"), JSON.stringify({ source }));
}

for (const command of ["diff", "update"]) {
  test(`${command} upstream failure returns exit 2 without modifying local content`, async (t) => {
    const f = await fixture(t);
    await writeSourceMeta(f, { type: "git", url: "unsupported://offline-fixture", path: "demo" });
    const result = run(f, [command, "core/demo", "--dry-run"]);
    assert.equal(JSON.parse(result.stdout).status, command === "diff" ? "fetch_failed" : "failed");
    assert.equal(result.status, 2, result.stderr);
    assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), skillText);
  });
}

test("update checks report missing local source and return exit 2", async (t) => {
  const f = await fixture(t);
  await writeSourceMeta(f, { type: "local", url: path.join(f.base, "missing") });
  const result = run(f, ["--check-updates", "--skill", "core/demo"]);
  const report = JSON.parse(result.stdout);
  assert.equal(report.skills["core/demo"].status, "source_missing");
  assert.equal(result.status, 2, result.stderr);
  assert.equal(report.ok, false);
});

test("update checks retain explicitly requested missing skills as failures", async (t) => {
  const f = await fixture(t);
  const result = run(f, ["--check-updates", "--skill", "missing"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 2, result.stderr);
  assert.equal(report.skills.missing.status, "missing_skill");
  assert.equal(report.summary.failed, 1);
});

test("existing local update source remains a successful check", async (t) => {
  const f = await fixture(t);
  await writeSourceMeta(f, { type: "local", url: f.source });
  const result = run(f, ["--check-updates", "--skill", "core/demo"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(report.summary.failed, 0);
  assert.equal(report.skills["core/demo"].status, "local");
});

test("update --all does not report failed checks as nothing to update", async (t) => {
  const f = await fixture(t);
  await writeSourceMeta(f, { type: "local", url: path.join(f.base, "missing") });
  await fs.rename(f.source, path.join(f.sourceRoot, "demo"));
  const result = run(f, ["update", "--all", "--dry-run"]);
  assert.equal(result.status, 2, result.stderr);
  assert.equal(JSON.parse(result.stdout).status, "check_failed");
});

test("unreadable history fails while an absent history is a successful empty result", async (t) => {
  const f = await fixture(t);
  const absent = run(f, ["history"]);
  assert.equal(absent.status, 0, absent.stderr);
  assert.equal(JSON.parse(absent.stdout).total, 0);
  await fs.mkdir(path.join(f.home, ".skill-installer", "history.jsonl"), { recursive: true });
  const unreadable = run(f, ["history"]);
  assert.equal(unreadable.status, 1);
  assert.match(unreadable.stderr, /EISDIR|illegal operation|directory/i);
});

test("migrate reports partial host sync and preserves independent success", async (t) => {
  const f = await fixture(t);
  await fs.rename(f.source, path.join(f.sourceRoot, "demo"));
  await fs.mkdir(f.target);
  await fs.writeFile(path.join(f.target, "keep.txt"), "keep");
  const claudeRoot = path.join(f.home, ".claude", "skills");
  await fs.mkdir(claudeRoot, { recursive: true });
  const result = run(f, ["migrate", "--tool", "codex,claude", "--apply"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 2, result.stderr);
  assert.equal(report.ok, false);
  assert.equal(report.applied, true);
  assert.equal(report.status, "migrated_sync_incomplete");
  assert.equal(report.migrations[0].status, "migrated");
  assert.equal(report.syncVerification.records.find(r => r.tool === "codex").status, "real_path_conflict");
  assert.equal(report.syncVerification.records.find(r => r.tool === "claude").status, "already_linked");
  assert.equal(await fs.readFile(path.join(f.target, "keep.txt"), "utf8"), "keep");
  assert.equal(await fs.realpath(path.join(claudeRoot, "demo")), await fs.realpath(f.source));
  await fs.rm(f.target, { recursive: true });
  const retry = run(f, ["--skill", "core/demo", "--tool", "codex", "--apply"]);
  assert.equal(retry.status, 0, retry.stderr);
  assert.equal(await fs.realpath(f.target), await fs.realpath(f.source));
});

test("migrate without root-level skills leaves unrelated links unchanged", async (t) => {
  const f = await fixture(t);
  const result = run(f, ["migrate", "--tool", "codex", "--apply"]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).count, 0);
  await assert.rejects(fs.lstat(f.target), { code: "ENOENT" });
});

test("migrate keeps incoming skills unlinked until review", async (t) => {
  const f = await fixture(t);
  await fs.rename(f.source, path.join(f.sourceRoot, "demo"));
  await fs.writeFile(path.join(f.sourceRoot, "demo", "SKILL.md"), "---\nname: demo\ndescription: demo\n---\n");
  const result = run(f, ["migrate", "--tool", "codex", "--apply"]);
  assert.equal(result.status, 0, result.stderr);
  assert.ok(await fs.stat(path.join(f.sourceRoot, "incoming", "demo", "SKILL.md")));
  await assert.rejects(fs.lstat(f.target), { code: "ENOENT" });
});


for (const command of ["diff", "update"]) {
  test(`${command} without recorded upstream remains a successful no-op`, async (t) => {
    const f = await fixture(t);
    const result = run(f, [command, "core/demo", "--dry-run"]);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(JSON.parse(result.stdout).status, command === "diff" ? "no_source" : "skipped");
  });
}

test("successful migration verifies its selected host link after a read-only preview", async (t) => {
  const f = await fixture(t);
  const original = path.join(f.sourceRoot, "demo");
  await fs.rename(f.source, original);
  const preview = run(f, ["migrate", "--tool", "codex", "--dry-run"]);
  assert.equal(preview.status, 0, preview.stderr);
  assert.equal(JSON.parse(preview.stdout).applied, false);
  assert.ok(await fs.stat(path.join(original, "SKILL.md")));
  await assert.rejects(fs.lstat(f.target), { code: "ENOENT" });
  const result = run(f, ["migrate", "--tool", "codex", "--apply"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(report.status, "migrated");
  assert.equal(report.syncVerification.records[0].status, "already_linked");
  assert.equal(await fs.realpath(f.target), await fs.realpath(f.source));
  await assert.rejects(fs.lstat(original), { code: "ENOENT" });
});

test("migration retains moved source and a recoverable result when symlink creation throws", async (t) => {
  const f = await fixture(t);
  await fs.rename(f.source, path.join(f.sourceRoot, "demo"));
  const preload = path.join(f.base, "fail-symlink.mjs");
  await fs.writeFile(preload, `import fs from "node:fs/promises";
fs.symlink = async () => { throw Object.assign(new Error("offline fixture symlink denied"), { code: "EACCES" }); };
`);
  const result = run(f, ["migrate", "--tool", "codex", "--apply"], ["--import", preload]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 2, result.stderr);
  assert.equal(report.applied, true);
  assert.equal(report.status, "migrated_sync_incomplete");
  assert.equal(report.syncError.code, "EACCES");
  assert.equal(report.syncPlan.records[0].status, "planned");
  assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), skillText);
  await assert.rejects(fs.lstat(f.target), { code: "ENOENT" });
  const retry = run(f, ["--skill", "core/demo", "--tool", "codex", "--apply"]);
  assert.equal(retry.status, 0, retry.stderr);
  assert.equal(await fs.realpath(f.target), await fs.realpath(f.source));
});
