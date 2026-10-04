import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const installerRoot = process.env.SKILL_INSTALLER_TEST_ROOT || fileURLToPath(new URL("../", import.meta.url));
const { parseArgs } = await import(pathToFileURL(path.join(installerRoot, "src", "cli.mjs")));
const cli = path.join(installerRoot, "bin", "skill-installer.mjs");
const skillText = "---\nname: demo\ndescription: Offline CLI fixture\n---\n";
const defaults = { sourceRoot: os.tmpdir(), home: os.tmpdir() };

async function fixture(t) {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), "skill-cli-options-"));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const sourceRoot = path.join(base, "source");
  const source = path.join(sourceRoot, "core", "demo");
  const home = path.join(base, "home");
  const incoming = path.join(base, "local skill");
  for (const dir of [source, incoming, path.join(home, ".codex", "skills"), path.join(home, ".claude", "skills")]) {
    await fs.mkdir(dir, { recursive: true });
  }
  await fs.writeFile(path.join(source, "SKILL.md"), skillText);
  await fs.writeFile(path.join(incoming, "SKILL.md"), skillText.replace("demo", "new-demo"));
  const metaText = JSON.stringify({ source: { type: "git", url: "https://example.invalid/offline/repo", path: "demo" } });
  await fs.writeFile(path.join(source, ".skill-meta.json"), metaText);
  const events = path.join(base, "unexpected-events.txt");
  const preload = path.join(base, "offline-guard.mjs");
  await fs.writeFile(preload, `import fs from "node:fs";
import childProcess from "node:child_process";
import { promisify } from "node:util";
import { syncBuiltinESMExports } from "node:module";
const blocked = kind => { fs.appendFileSync(${JSON.stringify(events)}, kind + "\\n"); throw new Error("offline guard"); };
globalThis.fetch = async () => blocked("fetch");
const exec = () => blocked("execFile");
exec[promisify.custom] = async () => blocked("execFile");
childProcess.execFile = exec;
syncBuiltinESMExports();
`);
  return { base, sourceRoot, source, home, incoming, metaText, preload, events };
}

function run(f, args) {
  return spawnSync(process.execPath, ["--import", f.preload, cli, ...args,
    "--source-root", f.sourceRoot, "--home", f.home, "--json"], {
    encoding: "utf8", timeout: 5000,
    env: { ...process.env, HOME: f.home, USERPROFILE: f.home, AI_HOST_HOME: f.home,
      AI_SKILLS_HOME: f.sourceRoot, XDG_CONFIG_HOME: path.join(f.base, "config"), APPDATA: path.join(f.base, "config") },
  });
}

async function assertUntouched(f) {
  assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), skillText);
  assert.equal(await fs.readFile(path.join(f.source, ".skill-meta.json"), "utf8"), f.metaText);
  assert.deepEqual(await fs.readdir(path.join(f.sourceRoot, "core")), ["demo"]);
  for (const host of [".codex", ".claude"]) {
    assert.deepEqual(await fs.readdir(path.join(f.home, host, "skills")), []);
  }
  for (const file of [f.events, path.join(f.home, ".skill-installer", "history.jsonl")]) {
    await assert.rejects(fs.stat(file), { code: "ENOENT" });
  }
}

for (const flag of ["--dryrun", "--unknown-option", "--tool=codex", "--skill=core/demo", "--source-root=/unused"]) {
  test(`parser rejects unsupported long option ${flag}`, () => {
    assert.throws(() => parseArgs([flag], defaults), /未知参数/);
  });
}

for (const [name, makeArgs] of [
  ["misspelled preview with apply", () => ["--skill", "core/demo", "--tool", "codex", "--dryrun", "--apply"]],
  ["equals target with apply", () => ["--skill", "core/demo", "--tool=codex", "--apply"]],
  ["equals target during preview", () => ["--skill", "core/demo", "--tool=codex", "--dry-run"]],
  ["unknown option after install source", f => ["install", f.incoming, "--category", "core", "--tool", "codex", "--apply", "--unknown-option"]],
  ["misspelled update preview", () => ["update", "core/demo", "--dryrun"]],
]) {
  test(`${name} fails before any requested work`, async t => {
    const f = await fixture(t);
    const result = run(f, makeArgs(f));
    assert.equal(result.status, 1, result.stderr);
    assert.equal(result.stdout, "");
    assert.match(result.stderr, /未知参数/);
    await assertUntouched(f);
  });
}

test("unsupported equals option does not echo its value", async t => {
  const f = await fixture(t);
  const result = run(f, ["--token=FAKE_UNKNOWN_OPTION_SENTINEL"]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /--token/);
  assert.doesNotMatch(result.stderr + result.stdout, /FAKE_UNKNOWN_OPTION_SENTINEL/);
  await assertUntouched(f);
});

test("space-separated target preview preserves the selected host", async t => {
  const f = await fixture(t);
  const result = run(f, ["--skill", "core/demo", "--tool", "codex", "--dry-run"]);
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.ok, true);
  assert.equal(report.applied, false);
  assert.deepEqual(report.records.map(record => record.tool), ["codex"]);
  await assertUntouched(f);
});

test("valid explicit apply still creates only the selected host link", async t => {
  const f = await fixture(t);
  const result = run(f, ["--skill", "core/demo", "--tool", "codex", "--apply"]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).applied, true);
  assert.equal(await fs.realpath(path.join(f.home, ".codex", "skills", "demo")), await fs.realpath(f.source));
  assert.deepEqual(await fs.readdir(path.join(f.home, ".claude", "skills")), []);
});

test("all existing subcommands and positional selections remain available", () => {
  for (const command of ["history", "diff", "update", "remove", "migrate"]) {
    const result = parseArgs([command, "core/demo", "--dry-run"], defaults);
    assert.equal(result.command, command);
    assert.deepEqual(result.skills, ["core/demo"]);
    assert.equal(result.dryRun, true);
  }
  const result = parseArgs(["install", "local skill", "--category", "core", "--name", "new-demo", "--path", "sub/path"], defaults);
  assert.equal(result.command, "install");
  assert.equal(result.installSource, "local skill");
  assert.equal(result.category, "core");
  assert.equal(result.name, "new-demo");
  assert.equal(result.path, "sub/path");
});

test("repeated and comma-separated selections preserve order", () => {
  const result = parseArgs(["--skill", "core/a, core/b", "core/c", "--skill", "core/d",
    "--tool", "codex, claude", "--target", "agents", "--tool", "junie"], defaults);
  assert.deepEqual(result.skills, ["core/a", "core/b", "core/c", "core/d"]);
  assert.deepEqual(result.tools, ["codex", "claude", "agents", "junie"]);
});

test("existing boolean flags and numeric history option retain their meanings", () => {
  const result = parseArgs(["--check-updates", "--only-updatable", "--all", "--sync", "--last", "7", "--purge", "--json"], defaults);
  for (const flag of ["checkUpdates", "onlyUpdatable", "all", "sync", "purge", "json"]) assert.equal(result[flag], true);
  assert.equal(result.last, 7);
});

test("both help spellings retain source-root-free parser and successful CLI behavior", async t => {
  const f = await fixture(t);
  for (const help of ["-h", "--help"]) {
    assert.equal(parseArgs([help], { sourceRoot: null, home: f.home }).help, true);
    assert.equal(run(f, [help]).status, 0);
  }
  await assertUntouched(f);
});
