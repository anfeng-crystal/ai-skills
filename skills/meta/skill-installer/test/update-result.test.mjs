import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const installerRoot = process.env.SKILL_INSTALLER_TEST_ROOT || fileURLToPath(new URL("../", import.meta.url));
const cli = path.join(installerRoot, "bin", "skill-installer.mjs");
const oldText = "---\nname: demo\ndescription: Before update\n---\n";
const upstreamHash = "a".repeat(40);
const nextHash = "b".repeat(40);
const newText = "---\nname: demo\ndescription: Offline upstream fixture\n---\n";

async function fixture(t) {
  const base = await fs.mkdtemp(path.join(os.tmpdir(), "skill-update-result-"));
  t.after(() => fs.rm(base, { recursive: true, force: true }));
  const sourceRoot = path.join(base, "source");
  const source = path.join(sourceRoot, "core", "demo");
  const home = path.join(base, "home");
  const target = path.join(home, ".codex", "skills", "demo");
  const claudeTarget = path.join(home, ".claude", "skills", "demo");
  await fs.mkdir(source, { recursive: true });
  await fs.mkdir(path.dirname(target), { recursive: true });
  await fs.mkdir(path.dirname(claudeTarget), { recursive: true });
  await fs.writeFile(path.join(source, "SKILL.md"), oldText);
  await fs.writeFile(path.join(source, ".skill-meta.json"), JSON.stringify({
    source: { type: "git", url: "https://github.com/offline/fixture", path: "demo", branch: "main" },
    lastUpstreamHash: "old-hash",
  }));
  const preload = path.join(base, "offline-upstream.mjs");
  const events = path.join(base, "upstream-events.jsonl");
  await fs.writeFile(preload, `import fs from "node:fs/promises";
import childProcess from "node:child_process";
import { syncBuiltinESMExports } from "node:module";
import { promisify } from "node:util";
let commitChecks = 0;
const log = event => fs.appendFile(${JSON.stringify(events)}, JSON.stringify(event) + "\\n");
globalThis.fetch = async (url) => {
  await log({ fetch: url });
  if (url !== "https://raw.githubusercontent.com/offline/fixture/${upstreamHash}/demo/SKILL.md") {
    throw new Error("Unexpected network request in offline test: " + url);
  }
  return { ok: process.env.OFFLINE_FAIL_FETCH !== "1", text: async () => ${JSON.stringify(newText)} };
};
const offlineExec = () => { throw new Error("Unexpected process call in offline test"); };
offlineExec[promisify.custom] = async (command, args) => {
  await log({ git: args });
  if (command !== "git" || args.join(" ") !== "ls-remote https://github.com/offline/fixture refs/heads/main") {
    throw new Error("Unexpected process call in offline test");
  }
  if (process.env.OFFLINE_FAIL_GIT === "1") throw new Error("offline git failed");
  const hash = process.env.OFFLINE_MOVING_BRANCH === "1" && commitChecks++ > 0
    ? ${JSON.stringify(nextHash)} : ${JSON.stringify(upstreamHash)};
  return { stdout: hash + "\\trefs/heads/main\\n" };
};
childProcess.execFile = offlineExec;
syncBuiltinESMExports();
if (process.env.OFFLINE_FAIL_SYMLINK === "1") {
  fs.symlink = async () => { throw Object.assign(new Error("offline symlink denied"), { code: "EACCES" }); };
}
`);
  return { base, sourceRoot, source, home, target, claudeTarget, preload, events };
}

function run(f, args, extraEnv = {}, json = true) {
  return spawnSync(process.execPath, ["--import", f.preload, cli, ...args,
    "--source-root", f.sourceRoot, "--home", f.home, ...(json ? ["--json"] : [])], {
    encoding: "utf8",
    env: { ...process.env, HOME: f.home, USERPROFILE: f.home, AI_HOST_HOME: f.home,
      AI_SKILLS_HOME: f.sourceRoot, XDG_CONFIG_HOME: path.join(f.base, "config"),
      APPDATA: path.join(f.base, "config"), ...extraEnv },
  });
}

async function readEvents(f) {
  return (await fs.readFile(f.events, "utf8")).trim().split("\n").map(JSON.parse);
}

async function readHistory(f) {
  return (await fs.readFile(path.join(f.home, ".skill-installer", "history.jsonl"), "utf8"))
    .trim().split("\n").map((line) => JSON.parse(line));
}

test("all update checks discover classified and root skills using distribution discovery rules", async (t) => {
  const f = await fixture(t);
  for (const skill of ["flat", "meta/helper", "incoming/unreviewed", ".hidden/private"]) {
    await fs.mkdir(path.join(f.sourceRoot, skill), { recursive: true });
    await fs.writeFile(path.join(f.sourceRoot, skill, "SKILL.md"), oldText);
  }
  const result = run(f, ["--check-updates"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(Object.keys(report.skills).sort(), ["core/demo", "flat", "meta/helper"]);
  assert.equal(report.skills["core/demo"].status, "updatable");
  assert.equal(report.summary.total, 3);
});

test("update --all dry-run finds classified upstream without writing source or links", async (t) => {
  const f = await fixture(t);
  const beforeMeta = await fs.readFile(path.join(f.source, ".skill-meta.json"), "utf8");
  const result = run(f, ["update", "--all", "--dry-run", "--sync", "--tool", "codex"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(report.status, "would_update");
  assert.deepEqual(report.skills.map((skill) => skill.name), ["core/demo"]);
  assert.equal(await fs.readFile(path.join(f.source, ".skill-meta.json"), "utf8"), beforeMeta);
  assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), oldText);
  await assert.rejects(fs.lstat(f.target), { code: "ENOENT" });
  await assert.rejects(readHistory(f), { code: "ENOENT" });
});

test("all update checks retain failures inside categories", async (t) => {
  const f = await fixture(t);
  await fs.writeFile(path.join(f.source, ".skill-meta.json"), JSON.stringify({
    source: { type: "local", url: path.join(f.base, "missing") },
  }));
  const result = run(f, ["--check-updates"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 2, result.stderr);
  assert.equal(report.skills["core/demo"].status, "source_missing");
  assert.equal(report.summary.failed, 1);
});

test("update --sync retains source and independent links while exposing conflict and safe retry", async (t) => {
  const f = await fixture(t);
  await fs.mkdir(f.target);
  await fs.writeFile(path.join(f.target, "keep.txt"), "keep");
  const result = run(f, ["update", "core/demo", "--sync", "--tool", "codex,claude"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 2, result.stderr);
  assert.equal(report.ok, false);
  assert.equal(report.status, "updated_sync_incomplete");
  assert.equal(report.sourceUpdated, true);
  assert.equal(report.synced, false);
  assert.deepEqual(report.syncedTools, ["claude"]);
  assert.equal(report.syncVerification.records.find(r => r.tool === "codex").status, "real_path_conflict");
  assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), newText);
  assert.equal(await fs.readFile(path.join(f.target, "keep.txt"), "utf8"), "keep");
  assert.equal(await fs.realpath(f.claudeTarget), await fs.realpath(f.source));
  assert.equal((await readHistory(f)).at(-1).synced, false);
  await fs.rm(f.target, { recursive: true });
  const retry = run(f, ["--skill", "core/demo", "--tool", "codex", "--apply"]);
  assert.equal(retry.status, 0, retry.stderr);
  assert.equal(await fs.realpath(f.target), await fs.realpath(f.source));
  assert.equal((await readHistory(f)).filter(r => r.action === "update").length, 1);
});

test("update --sync honors explicit --home and --tool without touching other host roots", async (t) => {
  const f = await fixture(t);
  const envHome = path.join(f.base, "other-home");
  await fs.mkdir(path.join(envHome, ".codex", "skills"), { recursive: true });
  const result = run(f, ["update", "core/demo", "--sync", "--tool", "codex"], { AI_HOST_HOME: envHome });
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(report.synced, true);
  assert.deepEqual(report.syncedTools, ["codex"]);
  assert.equal(report.syncVerification.home, f.home);
  assert.equal(report.syncVerification.records.length, 1);
  assert.equal(await fs.realpath(f.target), await fs.realpath(f.source));
  await assert.rejects(fs.lstat(f.claudeTarget), { code: "ENOENT" });
  await assert.rejects(fs.lstat(path.join(envHome, ".codex", "skills", "demo")), { code: "ENOENT" });
});

test("update sync errors retain a structured recoverable result and actual link verification", async (t) => {
  const f = await fixture(t);
  const result = run(f, ["update", "core/demo", "--sync", "--tool", "codex"], { OFFLINE_FAIL_SYMLINK: "1" });
  assert.equal(result.status, 2, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.status, "updated_sync_incomplete");
  assert.equal(report.sourceUpdated, true);
  assert.equal(report.syncError.code, "EACCES");
  assert.equal(report.syncVerification.records[0].status, "planned");
  assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), newText);
  assert.equal((await readHistory(f)).at(-1).synced, false);
});

test("default update sync treats unavailable optional hosts as skipped", async (t) => {
  const f = await fixture(t);
  const result = run(f, ["update", "core/demo", "--sync"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(report.ok, true);
  assert.equal(report.synced, true);
  assert.deepEqual(report.syncedTools, ["codex", "claude"]);
  assert.ok(report.syncVerification.records.some(r => r.status === "optional_host_unavailable"));
});

test("Hermes external_dirs is verified as a successful update sync", async (t) => {
  const f = await fixture(t);
  await fs.mkdir(path.join(f.home, ".hermes"));
  await fs.writeFile(path.join(f.home, ".hermes", "config.yaml"),
    `skills:\n  external_dirs:\n    - ${JSON.stringify(f.sourceRoot)}\n`);
  const result = run(f, ["update", "core/demo", "--sync", "--tool", "hermes"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(report.synced, true);
  assert.deepEqual(report.syncedTools, ["hermes"]);
  assert.equal(report.syncVerification.records[0].status, "managed_via_external_dir");
  await assert.rejects(fs.lstat(f.target), { code: "ENOENT" });
});

test("update --all propagates selected targets and incomplete sync to aggregate failure", async (t) => {
  const f = await fixture(t);
  await fs.mkdir(f.target);
  const result = run(f, ["update", "--all", "--sync", "--tool", "codex"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 2, result.stderr);
  assert.equal(report.ok, false);
  assert.equal(report.results[0].status, "updated_sync_incomplete");
  assert.equal(report.summary.failed, 1);
  assert.equal(report.summary.syncIncomplete, 1);
  assert.equal(report.results[0].syncVerification.records.length, 1);
  await assert.rejects(fs.lstat(f.claudeTarget), { code: "ENOENT" });
});

test("update without --sync changes only its source and reports no host synchronization", async (t) => {
  const f = await fixture(t);
  const result = run(f, ["update", "core/demo"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(report.status, "updated");
  assert.equal(report.synced, false);
  assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), newText);
  await assert.rejects(fs.lstat(f.target), { code: "ENOENT" });
  assert.equal((await readHistory(f)).length, 1);
});

test("update --all text output identifies incomplete skill and exact conflicting target", async (t) => {
  const f = await fixture(t);
  await fs.mkdir(f.target);
  const result = run(f, ["update", "--all", "--sync", "--tool", "codex"], {}, false);
  assert.equal(result.status, 2, result.stderr);
  assert.match(result.stdout, /Skill: core\/demo/);
  assert.match(result.stdout, /updated_sync_incomplete/);
  assert.match(result.stdout, /real_path_conflict/);
  assert.ok(result.stdout.includes(f.target));
});

for (const [tool, status] of [["unknown-host", "invalid_tool"], ["junie", "missing_target_root"]]) {
  test(`explicit update sync target ${tool} cannot be reported as optional success`, async (t) => {
    const f = await fixture(t);
    const result = run(f, ["update", "core/demo", "--sync", "--tool", tool]);
    const report = JSON.parse(result.stdout);
    assert.equal(result.status, 2, result.stderr);
    assert.equal(report.status, "updated_sync_incomplete");
    assert.equal(report.syncVerification.records[0].status, status);
    assert.deepEqual(report.syncedTools, []);
    await assert.rejects(fs.lstat(f.target), { code: "ENOENT" });
    await assert.rejects(fs.lstat(f.claudeTarget), { code: "ENOENT" });
  });
}


test("successful update stores its downloaded commit and the next check is up to date", async (t) => {
  const f = await fixture(t);
  await fs.writeFile(path.join(f.source, "resource.txt"), "local resource");
  const updated = run(f, ["update", "core/demo"]);
  assert.equal(updated.status, 0, updated.stderr);
  assert.equal(JSON.parse(updated.stdout).toHash, upstreamHash);
  const meta = JSON.parse(await fs.readFile(path.join(f.source, ".skill-meta.json"), "utf8"));
  assert.equal(meta.lastUpstreamHash, upstreamHash);
  assert.equal((await readHistory(f))[0].toHash, upstreamHash);
  assert.equal(await fs.readFile(path.join(f.source, "resource.txt"), "utf8"), "local resource");
  const checked = run(f, ["--check-updates"]);
  assert.equal(checked.status, 0, checked.stderr);
  assert.equal(JSON.parse(checked.stdout).skills["core/demo"].status, "up_to_date");
  const repeated = run(f, ["update", "--all"]);
  assert.equal(JSON.parse(repeated.stdout).status, "nothing_to_update");
  assert.equal((await readHistory(f)).length, 1);
});

for (const command of ["update", "diff"]) {
  test(`${command} resolves one commit and downloads its immutable content once`, async (t) => {
    const f = await fixture(t);
    const beforeMeta = await fs.readFile(path.join(f.source, ".skill-meta.json"), "utf8");
    const result = run(f, [command, "core/demo"], { OFFLINE_MOVING_BRANCH: "1" });
    const report = JSON.parse(result.stdout);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(report.toHash || report.upstreamHash, upstreamHash);
    const events = await readEvents(f);
    assert.equal(events.filter(event => event.git).length, 1);
    assert.deepEqual(events.filter(event => event.fetch).map(event => event.fetch),
      [`https://raw.githubusercontent.com/offline/fixture/${upstreamHash}/demo/SKILL.md`]);
    if (command === "diff") {
      assert.equal(await fs.readFile(path.join(f.source, ".skill-meta.json"), "utf8"), beforeMeta);
      assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), oldText);
      await assert.rejects(readHistory(f), { code: "ENOENT" });
    } else {
      assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), newText);
    }
  });
}

test("single update dry-run leaves source, metadata, history and links unchanged", async (t) => {
  const f = await fixture(t);
  const beforeMeta = await fs.readFile(path.join(f.source, ".skill-meta.json"), "utf8");
  const result = run(f, ["update", "core/demo", "--dry-run", "--sync", "--tool", "codex"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(report.status, "would_update");
  assert.equal(report.upstreamHash, upstreamHash);
  assert.equal(await fs.readFile(path.join(f.source, ".skill-meta.json"), "utf8"), beforeMeta);
  assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), oldText);
  await assert.rejects(readHistory(f), { code: "ENOENT" });
  await assert.rejects(fs.lstat(f.target), { code: "ENOENT" });
});

test("all update dry-run does not initialize missing upstream metadata", async (t) => {
  const f = await fixture(t);
  const metaPath = path.join(f.source, ".skill-meta.json");
  const meta = JSON.parse(await fs.readFile(metaPath, "utf8"));
  delete meta.lastUpstreamHash;
  const beforeMeta = JSON.stringify(meta);
  await fs.writeFile(metaPath, beforeMeta);
  const result = run(f, ["update", "--all", "--dry-run"]);
  assert.equal(result.status, 2, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.checkErrors["core/demo"].status, "baseline_unknown");
  assert.equal(await fs.readFile(metaPath, "utf8"), beforeMeta);
  assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), oldText);
  await assert.rejects(readHistory(f), { code: "ENOENT" });
});

for (const failure of ["OFFLINE_FAIL_GIT", "OFFLINE_FAIL_FETCH"]) {
  for (const command of ["update", "diff"]) {
    test(`${command} ${failure} preserves source, metadata and history`, async (t) => {
      const f = await fixture(t);
      const beforeMeta = await fs.readFile(path.join(f.source, ".skill-meta.json"), "utf8");
      const result = run(f, [command, "core/demo"], { [failure]: "1" });
      const report = JSON.parse(result.stdout);
      assert.equal(result.status, 2, result.stderr);
      assert.equal(report.status, command === "update" ? "failed" : "fetch_failed");
      assert.equal(await fs.readFile(path.join(f.source, ".skill-meta.json"), "utf8"), beforeMeta);
      assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), oldText);
      await assert.rejects(readHistory(f), { code: "ENOENT" });
      if (failure === "OFFLINE_FAIL_GIT") {
        assert.equal((await readEvents(f)).filter(event => event.fetch).length, 0);
      }
    });
  }
}

test("identical diff returns the commit without writing metadata or history", async (t) => {
  const f = await fixture(t);
  await fs.writeFile(path.join(f.source, "SKILL.md"), newText);
  const beforeMeta = await fs.readFile(path.join(f.source, ".skill-meta.json"), "utf8");
  const result = run(f, ["diff", "core/demo"]);
  const report = JSON.parse(result.stdout);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(report.status, "up_to_date");
  assert.equal(report.hash, upstreamHash);
  assert.equal(await fs.readFile(path.join(f.source, ".skill-meta.json"), "utf8"), beforeMeta);
  await assert.rejects(readHistory(f), { code: "ENOENT" });
});

for (const command of [["--check-updates"], ["--check-updates", "--dry-run"],
  ["update", "--all"], ["update", "--all", "--dry-run"]]) {
  test(`${command.join(" ")} preserves unknown installed version instead of stamping upstream`, async (t) => {
    const f = await fixture(t);
    const metaPath = path.join(f.source, ".skill-meta.json");
    const meta = JSON.parse(await fs.readFile(metaPath, "utf8"));
    delete meta.lastUpstreamHash;
    const before = JSON.stringify(meta);
    await fs.writeFile(metaPath, before);
    const result = run(f, command);
    assert.equal(result.status, 2, result.stderr);
    const report = JSON.parse(result.stdout);
    const state = (report.skills || report.checkErrors)["core/demo"];
    assert.equal(state.status, "baseline_unknown");
    assert.equal(state.upstreamHash, upstreamHash);
    assert.equal(report.summary.failed, 1);
    assert.equal(await fs.readFile(metaPath, "utf8"), before);
    assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), oldText);
    await assert.rejects(readHistory(f), { code: "ENOENT" });
    await assert.rejects(fs.lstat(f.target), { code: "ENOENT" });
    assert.equal((await readEvents(f)).filter(event => event.fetch).length, 0);
  });
}

test("explicit update establishes an unknown baseline only after downloading the pinned content", async (t) => {
  const f = await fixture(t);
  const metaPath = path.join(f.source, ".skill-meta.json");
  const meta = JSON.parse(await fs.readFile(metaPath, "utf8"));
  delete meta.lastUpstreamHash;
  await fs.writeFile(metaPath, JSON.stringify(meta));
  const result = run(f, ["update", "core/demo"]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).status, "updated");
  assert.equal((JSON.parse(await fs.readFile(metaPath, "utf8"))).lastUpstreamHash, upstreamHash);
  assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), newText);
  assert.equal((await readEvents(f)).filter(event => event.fetch).length, 1);
  const checked = run(f, ["--check-updates"]);
  assert.equal(checked.status, 0, checked.stderr);
  assert.equal(JSON.parse(checked.stdout).skills["core/demo"].status, "up_to_date");
});

test("all update keeps unknown-baseline evidence while completing independent known-version skills", async (t) => {
  const f = await fixture(t);
  const unknown = path.join(f.sourceRoot, "core", "unknown");
  await fs.mkdir(unknown);
  await fs.writeFile(path.join(unknown, "SKILL.md"), oldText);
  const metaText = JSON.stringify({ source: {
    type: "git", url: "https://github.com/offline/fixture", path: "demo", branch: "main",
  } });
  await fs.writeFile(path.join(unknown, ".skill-meta.json"), metaText);
  const result = run(f, ["update", "--all"]);
  assert.equal(result.status, 2, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.ok, false);
  assert.equal(report.checkErrors["core/unknown"].status, "baseline_unknown");
  assert.equal(report.results.length, 1);
  assert.equal(report.results[0].skill, "core/demo");
  assert.equal(report.results[0].status, "updated");
  assert.equal(await fs.readFile(path.join(f.source, "SKILL.md"), "utf8"), newText);
  assert.equal(await fs.readFile(path.join(unknown, ".skill-meta.json"), "utf8"), metaText);
  assert.equal(await fs.readFile(path.join(unknown, "SKILL.md"), "utf8"), oldText);
});

test("check-updates dry-run preserves known-version metadata through the CLI", async (t) => {
  const f = await fixture(t);
  const metaPath = path.join(f.source, ".skill-meta.json");
  const before = await fs.readFile(metaPath, "utf8");
  const result = run(f, ["--check-updates", "--dry-run"]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).skills["core/demo"].status, "updatable");
  assert.equal(await fs.readFile(metaPath, "utf8"), before);
});

test("unknown baseline text output names the skill, status and recovery action", async (t) => {
  const f = await fixture(t);
  const metaPath = path.join(f.source, ".skill-meta.json");
  const meta = JSON.parse(await fs.readFile(metaPath, "utf8"));
  delete meta.lastUpstreamHash;
  await fs.writeFile(metaPath, JSON.stringify(meta));
  const result = run(f, ["--check-updates"], {}, false);
  assert.equal(result.status, 2, result.stderr);
  assert.match(result.stdout, /core\/demo: baseline_unknown/);
  assert.match(result.stdout, /diff.*update/);
});
