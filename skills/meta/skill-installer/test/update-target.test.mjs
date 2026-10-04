import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = process.env.SKILL_INSTALLER_TEST_ROOT || fileURLToPath(new URL("../", import.meta.url));
const beforeText = "---\nname: fixture\ndescription: Before\n---\n";
const afterText = "---\nname: fixture\ndescription: After\n---\n";
const hash = "b".repeat(40);
const metadata = JSON.stringify({ source: { type: "git", url: "https://github.com/offline/target", path: "valid", branch: "main" }, lastUpstreamHash: "a".repeat(40) });

async function fixture(t, mode) {
  const base = await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), "skill-update-target-")));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const sourceRoot = path.join(base, "source"), home = path.join(base, "home");
  const target = path.join(sourceRoot, "core", "target");
  await fs.mkdir(path.dirname(target), { recursive: true });
  await fs.mkdir(home);
  if (mode === "target-file") await fs.writeFile(target, "ordinary file");
  else if (mode !== "missing") {
    await fs.mkdir(target);
    if (mode === "entry-dir") await fs.mkdir(path.join(target, "SKILL.md"));
    else if (!["no-entry", "git-no-entry"].includes(mode)) await fs.writeFile(path.join(target, "SKILL.md"), beforeText);
    if (mode === "git-no-entry") await fs.writeFile(path.join(target, ".skill-meta.json"), metadata);
    if (mode === "null-meta") await fs.writeFile(path.join(target, ".skill-meta.json"), "null");
    if (mode === "bad-meta") await fs.writeFile(path.join(target, ".skill-meta.json"), "{PRIVATE_TARGET_CONTENT");
    if (mode === "local-meta") await fs.writeFile(path.join(target, ".skill-meta.json"), JSON.stringify({ source: { type: "local", url: base } }));
  }
  const valid = path.join(sourceRoot, "core", "valid");
  await fs.mkdir(valid);
  await fs.writeFile(path.join(valid, "SKILL.md"), beforeText);
  await fs.writeFile(path.join(valid, ".skill-meta.json"), metadata);
  const events = path.join(base, "events.jsonl"), preload = path.join(base, "offline.mjs");
  await fs.writeFile(events, "");
  await fs.writeFile(preload, `import fs from "node:fs/promises";
import cp from "node:child_process";
import { promisify } from "node:util";
import { syncBuiltinESMExports } from "node:module";
const log = item => fs.appendFile(${JSON.stringify(events)}, JSON.stringify(item) + "\\n");
const deny = () => { throw new Error("UNEXPECTED_PROCESS_EXECUTION"); };
for (const key of ["exec", "execSync", "execFileSync", "spawn", "spawnSync", "fork"]) cp[key] = deny;
const stub = deny;
stub[promisify.custom] = async (command, args) => {
  await log({ git: args });
  if (command !== "git" || args.join(" ") !== "ls-remote https://github.com/offline/target refs/heads/main") throw new Error("UNEXPECTED_PROCESS_EXECUTION");
  return { stdout: ${JSON.stringify(hash + "\trefs/heads/main\n")} };
};
cp.execFile = stub;
syncBuiltinESMExports();
globalThis.fetch = async url => {
  await log({ fetch: url });
  if (url !== "https://raw.githubusercontent.com/offline/target/${hash}/valid/SKILL.md") throw new Error("UNEXPECTED_FETCH");
  return { ok: true, text: async () => ${JSON.stringify(afterText)} };
};
const stat = fs.stat.bind(fs);
fs.stat = async (file, ...args) => {
  if (String(file) === ${JSON.stringify(target)} && process.env.TARGET_STAT_CODE) {
    throw Object.assign(new Error("PRIVATE_TARGET_CONTENT"), { code: process.env.TARGET_STAT_CODE });
  }
  return stat(file, ...args);
};
`);
  return { base, sourceRoot, home, target, valid, events, preload };
}

function run(f, args, { json = true, code } = {}) {
  const result = spawnSync(process.execPath, ["--import", f.preload, path.join(root, "bin/skill-installer.mjs"),
    ...args, "--source-root", f.sourceRoot, "--home", f.home, ...(json ? ["--json"] : [])], {
    encoding: "utf8", timeout: 15000, cwd: f.base,
    env: { PATH: process.env.PATH, LANG: "C", HOME: f.home, USERPROFILE: f.home,
      AI_HOST_HOME: f.home, AI_SKILLS_HOME: f.sourceRoot,
      XDG_CONFIG_HOME: path.join(f.base, "config"), APPDATA: path.join(f.base, "config"),
      ...(code ? { TARGET_STAT_CODE: code } : {}) },
  });
  assert.equal(result.error, undefined);
  assert.equal(result.stderr, "");
  assert.doesNotMatch(result.stdout, /PRIVATE_TARGET|UNEXPECTED_PROCESS|UNEXPECTED_FETCH/);
  return result;
}

function reports(result, exitCode = 2) {
  assert.equal(result.status, exitCode, result.stdout);
  return result.stdout.trim().split(/\n(?=\{\n)/).map(JSON.parse);
}

async function state(f) {
  async function walk(dir) {
    const result = {};
    for (const name of (await fs.readdir(dir)).sort()) {
      const file = path.join(dir, name), stat = await fs.lstat(file);
      result[name] = stat.isSymbolicLink() ? { symlink: await fs.readlink(file) }
        : stat.isDirectory() ? await walk(file) : await fs.readFile(file, "utf8");
    }
    return result;
  }
  return { source: await walk(f.sourceRoot), home: await walk(f.home) };
}

for (const command of ["diff", "update"]) {
  for (const mode of ["missing", "target-file", "no-entry", "entry-dir", "git-no-entry"]) {
    test(`${command} rejects ${mode} before upstream or persistence`, async t => {
      const f = await fixture(t, mode), before = await state(f);
      const [result] = reports(run(f, [command, "core/target"]));
      assert.equal(result.skill, "core/target");
      assert.equal(result.ok, false);
      assert.equal(result.found, false);
      assert.equal(result.status, mode === "missing" ? "missing_skill" : "invalid_source");
      assert.equal(await fs.readFile(f.events, "utf8"), "");
      assert.deepEqual(await state(f), before);
    });
  }

  for (const mode of ["no-meta", "null-meta", "local-meta"]) {
    test(`${command} preserves valid ${mode} success without upstream or writes`, async t => {
      const f = await fixture(t, mode), before = await state(f);
      const [result] = reports(run(f, [command, "core/target"]), 0);
      assert.equal(result.status, command === "update" ? "skipped" : mode === "local-meta" ? "local_source" : "no_source");
      assert.notEqual(result.ok, false);
      assert.equal(await fs.readFile(f.events, "utf8"), "");
      assert.deepEqual(await state(f), before);
    });
  }

  test(`${command} preserves malformed metadata classification for valid skill`, async t => {
    const f = await fixture(t, "bad-meta"), before = await state(f);
    const [result] = reports(run(f, [command, "core/target"]));
    assert.equal(result.status, "metadata_read_failed");
    assert.equal(result.code, "INVALID_METADATA_JSON");
    assert.equal(await fs.readFile(f.events, "utf8"), "");
    assert.deepEqual(await state(f), before);
  });

  for (const code of ["EACCES", "PRIVATE_TARGET_CODE"]) {
    test(`${command} target stat ${code} remains a sanitized item failure`, async t => {
      const f = await fixture(t, "no-meta"), before = await state(f);
      const [result] = reports(run(f, [command, "core/target"], { code }));
      assert.equal(result.ok, false);
      assert.equal(result.status, "invalid_source");
      assert.equal(result.code, code === "EACCES" ? "EACCES" : null);
      assert.equal(await fs.readFile(f.events, "utf8"), "");
      assert.deepEqual(await state(f), before);
    });
  }

  test(`${command} dry-run retains an invalid first result and checks a later valid upstream`, async t => {
    const f = await fixture(t, "no-entry"), before = await state(f);
    const [invalid, valid] = reports(run(f, [command, "core/target", "core/valid", "--dry-run"]));
    assert.equal(invalid.status, "invalid_source");
    assert.equal(valid.skill, "core/valid");
    assert.equal(valid.status, command === "diff" ? "updatable" : "would_update");
    assert.equal(valid.upstreamHash, hash);
    assert.equal((await fs.readFile(f.events, "utf8")).trim().split("\n").length, 2);
    assert.deepEqual(await state(f), before);
  });

  test(`${command} text output identifies invalid target and continues the batch`, async t => {
    const f = await fixture(t, "no-meta"), before = await state(f);
    const result = run(f, [command, "core/missing", "core/target"], { json: false });
    assert.equal(result.status, 2);
    assert.match(result.stdout, /core\/missing/);
    assert.match(result.stdout, command === "update" ? /Status: skipped/ : /core\/target/);
    assert.equal(await fs.readFile(f.events, "utf8"), "");
    assert.deepEqual(await state(f), before);
  });

  test(`${command} accepts an existing symlinked skill directory`, async t => {
    const f = await fixture(t, "no-meta");
    await fs.symlink(f.target, path.join(f.sourceRoot, "linked"), process.platform === "win32" ? "junction" : "dir");
    const before = await state(f);
    const [result] = reports(run(f, [command, "linked"]), 0);
    assert.equal(result.status, command === "diff" ? "no_source" : "skipped");
    assert.deepEqual(await state(f), before);
  });
}

test("update applies a later valid target while retaining an invalid first result", async t => {
  const f = await fixture(t, "git-no-entry");
  const [invalid, valid] = reports(run(f, ["update", "core/target", "core/valid"]));
  assert.equal(invalid.status, "invalid_source");
  assert.equal(valid.status, "updated");
  assert.equal(valid.ok, true);
  await assert.rejects(fs.stat(path.join(f.target, "SKILL.md")), { code: "ENOENT" });
  assert.equal(await fs.readFile(path.join(f.target, ".skill-meta.json"), "utf8"), metadata);
  assert.equal(await fs.readFile(path.join(f.valid, "SKILL.md"), "utf8"), afterText);
  assert.equal(JSON.parse(await fs.readFile(path.join(f.valid, ".skill-meta.json"), "utf8")).lastUpstreamHash, hash);
  const history = (await fs.readFile(path.join(f.home, ".skill-installer/history.jsonl"), "utf8")).trim().split("\n").map(JSON.parse);
  assert.deepEqual(history.map(item => [item.action, item.skill]), [["update", "core/valid"]]);
  assert.equal((await fs.readFile(f.events, "utf8")).trim().split("\n").length, 2);
});
