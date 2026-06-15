import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { parseArgs as parseCliArgs } from "../src/cli.mjs";
import { buildInstallPlan, applyInstallPlan } from "../src/install.mjs";
import { applyPlan, buildPlan, linkTypeForPlatform, resolveTools } from "../src/sync-links.mjs";

test("cli requires source root when config and inference have no answer", () => {
  assert.throws(
    () => parseCliArgs([], {
      sourceRoot: null,
      home: path.join(os.tmpdir(), "skill-installer-home"),
      targetDirs: {},
      hermesConfigPath: null,
    }),
    /无法确定 skills source root/,
  );
});

test("cli source-root flag overrides configured source root", async () => {
  const configured = await makeSourceRoot();
  const explicit = await makeSourceRoot("skill installer explicit root ");
  const parsed = parseCliArgs(["--source-root", explicit], {
    sourceRoot: configured,
    home: path.join(os.tmpdir(), "skill-installer-home"),
    targetDirs: {},
    hermesConfigPath: null,
  });

  assert.equal(parsed.sourceRoot, path.resolve(explicit));
});

test("install dry-run plans classified target without writing files", async () => {
  const fixture = await makeSkill("Demo Skill", "tags: [meta]");
  const active = await makeSourceRoot();

  const plan = await buildInstallPlan({
    installSource: fixture,
    category: "meta",
    sourceRoot: active,
    home: await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-home-")),
    tools: [],
    skills: [],
    config: {},
  });

  assert.equal(plan.status, "planned");
  assert.equal(plan.category, "meta");
  assert.equal(plan.targetRelativePath, "meta/demo-skill");
  await assert.rejects(fs.stat(plan.targetPath));
});

test("install apply copies into category and keeps incoming out of sync", async () => {
  const fixture = await makeSkill("Unknown Skill", "");
  const active = await makeSourceRoot();

  const plan = await buildInstallPlan({
    installSource: fixture,
    category: "auto",
    sourceRoot: active,
    home: await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-home-")),
    tools: [],
    skills: [],
    config: {},
    apply: true,
  });
  const result = await applyInstallPlan(plan);

  assert.equal(result.status, "installed");
  assert.equal(result.category, "incoming");
  assert.equal(result.willSync, false);
  assert.equal(await exists(path.join(active, "incoming", "unknown-skill", "SKILL.md")), true);

  const syncPlan = await buildPlan({
    sourceRoot: active,
    home: await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-home-")),
    tools: [],
    skills: [],
    config: {},
  });
  assert.equal(syncPlan.records.some((record) => String(record.skill).includes("incoming")), false);
});

test("existing install target is rejected", async () => {
  const fixture = await makeSkill("Demo Skill", "");
  const active = await makeSourceRoot();
  await fs.mkdir(path.join(active, "core", "demo-skill"), { recursive: true });

  const plan = await buildInstallPlan({
    installSource: fixture,
    category: "core",
    sourceRoot: active,
    home: await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-home-")),
    tools: [],
    skills: [],
    config: {},
  });

  assert.equal(plan.ok, false);
  assert.equal(plan.status, "target_exists");
});

test("install rejects same target name in another category", async () => {
  const fixture = await makeSkill("Dup", "");
  const active = await makeSourceRoot();
  await makeSkillAt(path.join(active, "meta", "dup"), "dup", "");

  const plan = await buildInstallPlan({
    installSource: fixture,
    category: "core",
    sourceRoot: active,
    home: await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-home-")),
    tools: [],
    skills: [],
    config: {},
  });

  assert.equal(plan.ok, false);
  assert.equal(plan.status, "source_name_collision");
  assert.deepEqual(plan.collidingSkills, ["meta/dup"]);
});

test("source name collisions are reported", async () => {
  const active = await makeSourceRoot();
  await makeSkillAt(path.join(active, "core", "dup"), "dup", "");
  await makeSkillAt(path.join(active, "meta", "dup"), "dup", "");

  const plan = await buildPlan({
    sourceRoot: active,
    home: await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-home-")),
    tools: [],
    skills: ["dup"],
    config: {},
  });

  assert.equal(plan.records[0].status, "source_name_collision");
});

test("legacy active-root links are planned for replacement", async () => {
  const active = await makeSourceRoot();
  const home = await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-home-"));
  const targetRoot = path.join(home, ".codex", "skills");
  await makeSkillAt(path.join(active, "core", "demo-skill"), "demo-skill", "");
  await fs.mkdir(targetRoot, { recursive: true });
  await fs.symlink(
    path.join(active, "active", "skills", "core", "demo-skill"),
    path.join(targetRoot, "demo-skill"),
    "dir",
  );

  const plan = await buildPlan({
    sourceRoot: active,
    home,
    tools: ["codex"],
    skills: ["demo-skill"],
    config: {},
  });

  assert.equal(plan.records.length, 1);
  assert.equal(plan.records[0].status, "planned");
  assert.equal(plan.records[0].action, "replace_link");
  assert.equal(plan.records[0].reason, "legacy_active_root_link");
  assert.equal(plan.records[0].wouldChange, true);
});

test("real target directories remain blocking conflicts", async () => {
  const active = await makeSourceRoot();
  const home = await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-home-"));
  const targetPath = path.join(home, ".codex", "skills", "demo-skill");
  await makeSkillAt(path.join(active, "core", "demo-skill"), "demo-skill", "");
  await fs.mkdir(targetPath, { recursive: true });

  const plan = await buildPlan({
    sourceRoot: active,
    home,
    tools: ["codex"],
    skills: ["demo-skill"],
    config: {},
  });

  assert.equal(plan.records.length, 1);
  assert.equal(plan.records[0].status, "real_path_conflict");
  assert.equal(plan.records[0].wouldChange, false);
});

test("source root with spaces plans host links", async () => {
  const active = await makeSourceRoot("skill installer active root ");
  const home = await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-home-"));
  await makeSkillAt(path.join(active, "core", "demo-skill"), "demo-skill", "");
  await fs.mkdir(path.join(home, ".codex", "skills"), { recursive: true });

  const plan = await buildPlan({
    sourceRoot: active,
    home,
    tools: ["codex"],
    skills: ["demo-skill"],
    config: {},
  });

  assert.equal(plan.records.length, 1);
  assert.equal(plan.records[0].status, "planned");
  assert.equal(plan.records[0].action, "create_link");
  assert.match(plan.records[0].sourcePath, /skill installer active root /);
});

test("full sync reports and applies source-root orphan links only", async () => {
  const active = await makeSourceRoot();
  const home = await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-home-"));
  const targetRoot = path.join(home, ".codex", "skills");
  const sourceSkill = path.join(active, "core", "demo-skill");
  const goodLink = path.join(targetRoot, "demo-skill");
  const orphanLink = path.join(targetRoot, "removed-skill");
  const externalLink = path.join(targetRoot, "external-removed");
  const realDirectory = path.join(targetRoot, "real-directory");
  const externalRoot = await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-external-"));

  await makeSkillAt(sourceSkill, "demo-skill", "");
  await fs.mkdir(targetRoot, { recursive: true });
  await fs.symlink(sourceSkill, goodLink, "dir");
  await fs.symlink(path.join(active, "core", "removed-skill"), orphanLink, "dir");
  await fs.symlink(path.join(externalRoot, "removed-skill"), externalLink, "dir");
  await fs.mkdir(realDirectory);

  const plan = await buildPlan({
    sourceRoot: active,
    home,
    tools: ["codex"],
    skills: [],
    config: {},
  });
  const orphanRecords = plan.records.filter((record) => record.status === "orphan_link");

  assert.equal(orphanRecords.length, 1);
  assert.equal(orphanRecords[0].targetPath, orphanLink);
  assert.equal(plan.summary.byStatus.orphan_link, 1);
  assert.equal(plan.summary.byAction.remove_orphan_link, 1);

  await applyPlan(plan.records);

  assert.equal(await linkExists(orphanLink), false);
  assert.equal(await linkExists(externalLink), true);
  assert.equal(await exists(realDirectory), true);
});

test("targeted sync does not prune unrelated orphan links", async () => {
  const active = await makeSourceRoot();
  const home = await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-home-"));
  const targetRoot = path.join(home, ".codex", "skills");
  const sourceSkill = path.join(active, "core", "demo-skill");
  const orphanLink = path.join(targetRoot, "removed-skill");

  await makeSkillAt(sourceSkill, "demo-skill", "");
  await fs.mkdir(targetRoot, { recursive: true });
  await fs.symlink(sourceSkill, path.join(targetRoot, "demo-skill"), "dir");
  await fs.symlink(path.join(active, "core", "removed-skill"), orphanLink, "dir");

  const plan = await buildPlan({
    sourceRoot: active,
    home,
    tools: ["codex"],
    skills: ["demo-skill"],
    config: {},
  });

  assert.equal(plan.records.some((record) => record.status === "orphan_link"), false);
  assert.equal(await linkExists(orphanLink), true);
});

test("orphan apply skips links changed after dry-run", async () => {
  const active = await makeSourceRoot();
  const home = await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-home-"));
  const targetRoot = path.join(home, ".codex", "skills");
  const sourceSkill = path.join(active, "core", "demo-skill");
  const orphanLink = path.join(targetRoot, "removed-skill");
  const externalRoot = await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-external-"));

  await makeSkillAt(sourceSkill, "demo-skill", "");
  await fs.mkdir(targetRoot, { recursive: true });
  await fs.symlink(sourceSkill, path.join(targetRoot, "demo-skill"), "dir");
  await fs.symlink(path.join(active, "core", "removed-skill"), orphanLink, "dir");

  const plan = await buildPlan({
    sourceRoot: active,
    home,
    tools: ["codex"],
    skills: [],
    config: {},
  });
  const orphanRecord = plan.records.find((record) => record.status === "orphan_link");
  assert.ok(orphanRecord);

  await fs.unlink(orphanLink);
  await fs.symlink(path.join(externalRoot, "removed-skill"), orphanLink, "dir");
  await applyPlan([orphanRecord]);

  assert.equal(await linkExists(orphanLink), true);
  assert.equal(orphanRecord.status, "skipped");
  assert.equal(orphanRecord.reason, "orphan_link_changed");
});

test("windows uses junction while posix uses directory symlink", () => {
  assert.equal(linkTypeForPlatform("win32"), "junction");
  assert.equal(linkTypeForPlatform("linux"), "dir");
  assert.equal(linkTypeForPlatform("darwin"), "dir");
});

test("optional host aliases resolve under host home", () => {
  const home = path.join(os.tmpdir(), "example-home");
  const tools = resolveTools(
    ["qoder", "qoderwork", "workbuddy", "trae", "openclaw", "opencode", "qoder-work", "trae-ide", "claude-code", "antigravity"],
    home,
    {},
  );
  const roots = Object.fromEntries(tools.map((tool) => [tool.name, tool.root]));

  assert.equal(roots.qoder, path.join(home, ".qoder/skills"));
  assert.equal(roots.qoderwork, path.join(home, ".qoderwork/skills"));
  assert.equal(roots.workbuddy, path.join(home, ".workbuddy/skills"));
  assert.equal(roots.trae, path.join(home, ".trae/skills"));
  assert.equal(roots.openclaw, path.join(home, ".openclaw/workspace/skills"));
  assert.equal(roots.opencode, path.join(home, ".opencode/skills"));
  assert.equal(tools[6].name, "qoderwork");
  assert.equal(tools[7].name, "trae");
  assert.equal(tools[8].name, "claude");
  assert.equal(tools[9].name, "antigravity-cli");
});

async function makeSourceRoot(prefix = "skill-installer-active-") {
  const active = await fs.mkdtemp(path.join(os.tmpdir(), prefix));
  for (const category of ["automation", "core", "kingdee", "meta"]) {
    await fs.mkdir(path.join(active, category), { recursive: true });
  }
  return active;
}

async function makeSkill(name, extraFrontmatter) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-source-"));
  await makeSkillAt(root, name, extraFrontmatter);
  return root;
}

async function makeSkillAt(dir, name, extraFrontmatter) {
  await fs.mkdir(dir, { recursive: true });
  await fs.writeFile(
    path.join(dir, "SKILL.md"),
    `---\nname: ${name}\ndescription: Sample capability\n${extraFrontmatter}\n---\n# ${name}\n`,
    "utf8",
  );
}

async function linkExists(targetPath) {
  try { await fs.lstat(targetPath); return true; } catch { return false; }
}

async function exists(targetPath) {
  try {
    await fs.stat(targetPath);
    return true;
  } catch {
    return false;
  }
}
