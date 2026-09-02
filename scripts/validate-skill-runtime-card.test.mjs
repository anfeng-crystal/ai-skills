import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const validator = fileURLToPath(new URL("./validate-skill-runtime-card.mjs", import.meta.url));

test("accepts a complete runtime card in a path with spaces", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "skill card "));
  const skill = path.join(root, "demo-skill");
  fs.mkdirSync(skill);
  fs.writeFileSync(path.join(skill, "SKILL.md"), runtimeCard(), "utf8");

  const result = spawnSync(process.execPath, [validator, "--path", skill, "--strict"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("rejects human manuals, placeholders, and hard-coded home paths", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "skill-card-invalid-"));
  const skill = path.join(root, "bad-skill");
  fs.mkdirSync(skill);
  fs.writeFileSync(path.join(skill, "SKILL.md"), `${runtimeCard()}\n## 教程\n- [填写步骤]\n- /Users/example/private\n`, "utf8");

  const result = spawnSync(process.execPath, [validator, "--path", skill, "--json"], { encoding: "utf8" });
  assert.equal(result.status, 1);
  const parsed = JSON.parse(result.stdout);
  assert.ok(parsed.errors.some((item) => item.message.includes("human-manual")));
  assert.ok(parsed.errors.some((item) => item.message.includes("placeholder")));
  assert.ok(parsed.errors.some((item) => item.message.includes("user path")));
});

test("allows destructive command names when they are explicit risk examples", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "skill-card-risk-"));
  const skill = path.join(root, "risk-skill");
  fs.mkdirSync(skill);
  fs.writeFileSync(path.join(skill, "SKILL.md"), `${runtimeCard()}\n- 禁止执行 rm -rf 或 git reset --hard。\n`, "utf8");

  const result = spawnSync(process.execPath, [validator, "--path", skill, "--strict"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("accepts CRLF skill files", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "skill-card-crlf-"));
  const skill = path.join(root, "crlf-skill");
  fs.mkdirSync(skill);
  fs.writeFileSync(path.join(skill, "SKILL.md"), runtimeCard().replace(/\n/g, "\r\n"), "utf8");

  const result = spawnSync(process.execPath, [validator, "--path", skill, "--strict"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("new skill mode rejects extra frontmatter keys", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "skill-card-frontmatter-"));
  const skill = path.join(root, "extra-frontmatter-skill");
  fs.mkdirSync(skill);
  fs.writeFileSync(
    path.join(skill, "SKILL.md"),
    runtimeCard().replace('description: "Use for a deterministic demo task."', 'description: "Use for a deterministic demo task."\nlicense: MIT'),
    "utf8",
  );

  const result = spawnSync(
    process.execPath,
    [validator, "--path", skill, "--new-skill", "--json"],
    { encoding: "utf8" },
  );
  assert.equal(result.status, 1);
  const parsed = JSON.parse(result.stdout);
  assert.ok(parsed.errors.some((item) => item.message.includes("unsupported keys: license")));
});

test("accepts an English routing heading", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "skill-card-routing-"));
  const skill = path.join(root, "routing-skill");
  fs.mkdirSync(skill);
  fs.writeFileSync(path.join(skill, "SKILL.md"), runtimeCard().replace("## 触发与路由", "## Routing"), "utf8");

  const result = spawnSync(process.execPath, [validator, "--path", skill, "--strict"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

function runtimeCard() {
  return `---
name: demo-skill
description: "Use for a deterministic demo task."
---

# Demo

## 触发与路由
- Use for demo inputs.

## 契约
- Input and output are explicit.

## 工作流
1. Read input.
2. Emit output.

## 门禁与失败
- Stop when input is absent.

## 输出
- Return the result.
`;
}
