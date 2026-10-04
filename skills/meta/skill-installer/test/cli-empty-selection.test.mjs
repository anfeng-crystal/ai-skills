import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = process.env.SKILL_INSTALLER_TEST_ROOT || fileURLToPath(new URL("../", import.meta.url));
const { parseArgs } = await import(pathToFileURL(path.join(root, "src/cli.mjs")));
const cli = path.join(root, "bin/skill-installer.mjs");
const defaults = { sourceRoot: os.tmpdir(), home: os.tmpdir() };
const sourceText = "---\nname: fixture\ndescription: Offline selection fixture\n---\n";

for (const value of [" ", ",", " , ", "\t,\n"]) {
  for (const flag of ["--skill", "--tool", "--target", null]) {
    test(`rejects empty ${flag || "positional Skill"} selection ${JSON.stringify(value)}`, () => {
      assert.throws(() => parseArgs(flag ? [flag, value] : [value], defaults), /需要指定至少一个非空值/);
    });
  }
}

for (const flag of ["--skill", "--tool", "--target", null]) {
  test(`an earlier valid selection does not hide empty ${flag || "positional Skill"}`, () => {
    const prefix = flag === "--tool" || flag === "--target" ? [flag, "codex"] : ["core/a"];
    assert.throws(() => parseArgs([...prefix, ...(flag ? [flag, " , "] : [" , "])], defaults),
      /需要指定至少一个非空值/);
  });
}

async function fixture(t, linked = false) {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), "skill-empty-selection-"));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const sourceRoot = path.join(base, "source"), home = path.join(base, "home");
  const incoming = path.join(base, "local skill");
  const metaText = JSON.stringify({ source: { type: "git", url: "https://example.invalid/offline/fixture" } });
  for (const name of ["a", "b"]) {
    const dir = path.join(sourceRoot, "core", name);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(path.join(dir, "SKILL.md"), sourceText);
    await fs.writeFile(path.join(dir, ".skill-meta.json"), metaText);
  }
  await fs.mkdir(incoming);
  await fs.writeFile(path.join(incoming, "SKILL.md"), sourceText.replace("fixture", "new-skill"));
  for (const tool of ["codex", "claude"]) {
    const dir = path.join(home, `.${tool}`, "skills");
    await fs.mkdir(dir, { recursive: true });
    if (linked) await fs.symlink(path.join(sourceRoot, "core/a"), path.join(dir, "a"), "dir");
  }
  const events = path.join(base, "unexpected-events.txt"), preload = path.join(base, "offline.mjs");
  await fs.writeFile(preload, `import fs from "node:fs";
import cp from "node:child_process";
import { promisify } from "node:util";
import { syncBuiltinESMExports } from "node:module";
const block = () => { fs.appendFileSync(${JSON.stringify(events)}, "blocked\\n"); throw new Error("Offline guard"); };
const exec = block;
exec[promisify.custom] = async () => block();
cp.execFile = exec;
syncBuiltinESMExports();
globalThis.fetch = async () => block();
`);
  return { base, sourceRoot, home, incoming, linked, events, preload, metaText };
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
  assert.deepEqual(await fs.readdir(path.join(f.sourceRoot, "core")), ["a", "b"]);
  for (const name of ["a", "b"]) {
    const dir = path.join(f.sourceRoot, "core", name);
    assert.equal(await fs.readFile(path.join(dir, "SKILL.md"), "utf8"), sourceText);
    assert.equal(await fs.readFile(path.join(dir, ".skill-meta.json"), "utf8"), f.metaText);
  }
  for (const tool of ["codex", "claude"]) {
    const dir = path.join(f.home, `.${tool}`, "skills");
    assert.deepEqual(await fs.readdir(dir), f.linked ? ["a"] : []);
    if (f.linked) assert.equal(await fs.realpath(path.join(dir, "a")), await fs.realpath(path.join(f.sourceRoot, "core/a")));
  }
  for (const file of [f.events, path.join(f.home, ".skill-installer/history.jsonl")]) {
    await assert.rejects(fs.stat(file), { code: "ENOENT" });
  }
}

for (const [name, args, linked] of [
  ["sync skill", () => ["--skill", " , ", "--tool", "codex", "--apply"]],
  ["sync tool", () => ["--skill", "core/a", "--tool", " , ", "--apply"]],
  ["sync positional Skill", () => [" , ", "--tool", "codex", "--apply"]],
  ["remove target", () => ["remove", "core/a", "--target", " , ", "--apply"], true],
  ["install tool", f => ["install", f.incoming, "--category", "core", "--tool", " , ", "--apply"]],
  ["update sync tool", () => ["update", "core/a", "--sync", "--tool", " , "]],
  ["check skill", () => ["--check-updates", "--skill", " , "]],
]) {
  test(`invalid ${name} fails before writes or upstream requests`, async t => {
    const f = await fixture(t, linked);
    const result = run(f, args(f));
    assert.equal(result.status, 1, result.stderr);
    assert.equal(result.stdout, "");
    assert.match(result.stderr, /需要指定至少一个非空值/);
    await assertUntouched(f);
  });
}

test("omitted selection keeps default discovery in preview", async t => {
  const f = await fixture(t);
  const result = run(f, ["--dry-run"]);
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.applied, false);
  assert.deepEqual(report.records.map(r => `${r.skill}:${r.tool}`).sort(),
    ["core/a:claude", "core/a:codex", "core/b:claude", "core/b:codex"]);
  await assertUntouched(f);
});

test("mixed and repeated nonempty selections retain order", () => {
  const result = parseArgs(["--skill", " , core/a, ", " , core/b, ", "--skill", "core/a",
    "--tool", " , codex, ", "--target", "claude", "--tool", "codex"], defaults);
  assert.deepEqual(result.skills, ["core/a", "core/b", "core/a"]);
  assert.deepEqual(result.tools, ["codex", "claude", "codex"]);
});

test("valid mixed selection applies only the selected Skill and host", async t => {
  const f = await fixture(t);
  const result = run(f, ["--skill", " , core/a, ", "--tool", " , codex, ", "--apply"]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).applied, true);
  assert.equal(await fs.realpath(path.join(f.home, ".codex/skills/a")), await fs.realpath(path.join(f.sourceRoot, "core/a")));
  assert.deepEqual(await fs.readdir(path.join(f.home, ".codex/skills")), ["a"]);
  assert.deepEqual(await fs.readdir(path.join(f.home, ".claude/skills")), []);
});

test("install source positional argument remains a path rather than a Skill list", () => {
  const result = parseArgs(["install", "local skill, copy", "--tool", "codex"], defaults);
  assert.equal(result.installSource, "local skill, copy");
  assert.deepEqual(result.skills, []);
});
