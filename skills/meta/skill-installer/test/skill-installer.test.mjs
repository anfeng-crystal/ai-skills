import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { buildInstallPlan, applyInstallPlan } from "../src/install.mjs";
import { buildPlan, linkTypeForPlatform, resolveTools } from "../src/sync-links.mjs";

test("install dry-run plans classified target without writing files", async () => {
  const fixture = await makeSkill("Demo Skill", "tags: [meta]");
  const active = await makeActiveRoot();

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
  assert.equal(plan.targetRelativePath, "skills/meta/demo-skill");
  await assert.rejects(fs.stat(plan.targetPath));
});

test("install apply copies into category and keeps incoming out of sync", async () => {
  const fixture = await makeSkill("Unknown Skill", "");
  const active = await makeActiveRoot();

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
  assert.equal(await exists(path.join(active, "skills", "incoming", "unknown-skill", "SKILL.md")), true);

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
  const active = await makeActiveRoot();
  await fs.mkdir(path.join(active, "skills", "core", "demo-skill"), { recursive: true });

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
  const active = await makeActiveRoot();
  await makeSkillAt(path.join(active, "skills", "meta", "dup"), "dup", "");

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
  assert.deepEqual(plan.collidingSkills, ["skills/meta/dup"]);
});

test("source name collisions are reported", async () => {
  const active = await makeActiveRoot();
  await makeSkillAt(path.join(active, "skills", "core", "dup"), "dup", "");
  await makeSkillAt(path.join(active, "skills", "meta", "dup"), "dup", "");

  const plan = await buildPlan({
    sourceRoot: active,
    home: await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-home-")),
    tools: [],
    skills: ["dup"],
    config: {},
  });

  assert.equal(plan.records[0].status, "source_name_collision");
});

test("windows uses junction while posix uses directory symlink", () => {
  assert.equal(linkTypeForPlatform("win32"), "junction");
  assert.equal(linkTypeForPlatform("linux"), "dir");
  assert.equal(linkTypeForPlatform("darwin"), "dir");
});

test("optional host aliases resolve under host home", () => {
  const home = path.resolve("/tmp/example-home");
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

async function makeActiveRoot() {
  const active = await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-active-"));
  for (const category of ["automation", "core", "kingdee", "meta"]) {
    await fs.mkdir(path.join(active, "skills", category), { recursive: true });
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

async function exists(targetPath) {
  try {
    await fs.stat(targetPath);
    return true;
  } catch {
    return false;
  }
}
