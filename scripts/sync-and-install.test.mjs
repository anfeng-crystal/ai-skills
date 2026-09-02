import assert from "node:assert/strict";
import path from "node:path";
import { test } from "node:test";

import { buildPlan, parseArgs } from "./sync-and-install.mjs";

test("parseArgs captures host and install filters", () => {
  const options = parseArgs([
    "--home",
    "/tmp/host-home",
    "--source-root",
    "/tmp/skills root",
    "--tool",
    "codex",
    "--tool",
    "claude",
    "--skill",
    "web-access",
    "--skip-doctor",
    "--no-pull",
  ]);

  assert.equal(options.home, path.resolve("/tmp/host-home"));
  assert.equal(options.sourceRoot, path.resolve("/tmp/skills root"));
  assert.deepEqual(options.tools, ["codex", "claude"]);
  assert.deepEqual(options.skills, ["web-access"]);
  assert.equal(options.runDoctor, false);
  assert.equal(options.pull, false);
});

test("buildPlan runs git pull, install, and doctor in order", () => {
  const plan = buildPlan({
    activeRoot: "/repo/skills/active",
    gitRoot: "/repo",
    home: "/home/anfeng",
    sourceRoot: "/repo/skills",
    tools: ["codex"],
    skills: ["web-access"],
    runDoctor: true,
    pull: true,
  });

  assert.deepEqual(
    plan.commands.map((command) => command.label),
    ["Pull latest skills", "Install skills", "Run doctor"],
  );

  assert.deepEqual(plan.commands[0], {
    label: "Pull latest skills",
    command: "git",
    args: ["pull", "--ff-only"],
    cwd: "/repo",
  });
  assert.equal(plan.commands[1].command, process.execPath);
  assert.deepEqual(plan.commands[1].args, [
    path.join("/repo/skills/active", "install.mjs"),
    "--source-root",
    "/repo/skills",
    "--home",
    "/home/anfeng",
    "--tool",
    "codex",
    "--skill",
    "web-access",
  ]);
  assert.equal(plan.commands[1].cwd, "/repo/skills/active");
  assert.equal(plan.commands[2].command, process.execPath);
  assert.deepEqual(plan.commands[2].args, [
    path.join("/repo/skills/active", "scripts/doctor.mjs"),
    "--source-root",
    "/repo/skills/active",
    "--home",
    "/home/anfeng",
  ]);
});

test("buildPlan supports non-mutating dry runs", () => {
  const plan = buildPlan({
    activeRoot: "/repo/skills/active",
    gitRoot: "/repo",
    home: "/home/anfeng",
    sourceRoot: "/repo/skills",
    tools: [],
    skills: [],
    runDoctor: true,
    pull: true,
    dryRun: true,
  });

  assert.equal(plan.dryRun, true);
  assert.deepEqual(
    plan.commands.map((command) => command.label),
    ["Pull latest skills", "Install skills", "Run doctor"],
  );
});
