#!/usr/bin/env node

/**
 * 交互式创建新 skill，支持选择现有分类或创建新分类。
 *
 * 用法:
 *   node scripts/create-skill.mjs                                    # 交互模式
 *   node scripts/create-skill.mjs --name my-skill \                  # 命令行模式
 *     --description "描述" \
 *     --category core \
 *     --runtime markdown \
 *     --optional
 */

import fs from "node:fs/promises";
import path from "node:path";
import readline from "node:readline/promises";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPT_DIR, "..");
const SKILLS_ROOT = path.join(REPO_ROOT, "skills");
const MANIFEST_PATH = path.join(REPO_ROOT, "config/skills-manifest.json");

const SKILL_TEMPLATE = `---
name: {{SKILL_NAME}}
description: {{DESCRIPTION}}
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: []
---

# {{SKILL_TITLE}}

> **Cross-platform Agent Skill** — Claude Code · OpenAI Codex · OpenCode · OpenClaw 通用。
> 跨平台 SKILL.md，遵循开放 Agent Skill 规范。

## 触发边界
- 描述何时使用此 skill
- 描述何时不使用此 skill

## 快速工作流
1. 步骤一
2. 步骤二
3. 步骤三

## 门禁与降级
- 关键约束条件
- 降级策略

## Guardrails
- 不做什么
- 必须遵守的规则
`;

main();

async function main() {
  try {
    const args = parseArgs(process.argv.slice(2));

    if (args.help) {
      printHelp();
      return;
    }

    let config;
    if (args.name) {
      // 命令行模式
      config = await buildConfigFromArgs(args);
    } else {
      // 交互模式
      config = await buildConfigInteractive();
    }

    await createSkill(config);
  } catch (error) {
    console.error(`错误: ${error instanceof Error ? error.message : String(error)}`);
    process.exit(1);
  }
}

function parseArgs(argv) {
  const parsed = {
    name: null,
    description: null,
    category: null,
    newCategory: null,
    runtime: null,
    requiresKnowledge: false,
    optional: false,
    help: false,
  };

  for (let i = 0; i < argv.length; i++) {
    switch (argv[i]) {
      case "--name":
        parsed.name = argv[++i];
        break;
      case "--description":
        parsed.description = argv[++i];
        break;
      case "--category":
        parsed.category = argv[++i];
        break;
      case "--new-category":
        parsed.newCategory = argv[++i];
        break;
      case "--runtime":
        parsed.runtime = argv[++i];
        break;
      case "--requires-knowledge":
        parsed.requiresKnowledge = true;
        break;
      case "--optional":
        parsed.optional = true;
        break;
      case "--help":
      case "-h":
        parsed.help = true;
        break;
      default:
        throw new Error(`未知参数: ${argv[i]}`);
    }
  }

  return parsed;
}

function printHelp() {
  console.log(`用法:
  node scripts/create-skill.mjs [options]

交互模式（无参数）:
  node scripts/create-skill.mjs

命令行模式:
  node scripts/create-skill.mjs --name <skill-name> \\
    --description <description> \\
    --category <existing-category> \\
    [--runtime <runtime>] \\
    [--requires-knowledge] \\
    [--optional]

  或创建新分类:
  node scripts/create-skill.mjs --name <skill-name> \\
    --description <description> \\
    --new-category <new-category> \\
    [--runtime <runtime>] \\
    [--requires-knowledge] \\
    [--optional]

选项:
  --name <name>              Skill 名称（kebab-case）
  --description <desc>       简短描述
  --category <cat>           使用现有分类
  --new-category <cat>       创建新分类
  --runtime <runtime>        运行时依赖（逗号分隔，默认 markdown）
  --requires-knowledge       需要 AI_KNOWLEDGE_ROOT
  --optional                 标记为可选 skill
  --help, -h                 显示帮助
`);
}

async function buildConfigFromArgs(args) {
  if (!args.name || !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(args.name)) {
    throw new Error("--name 必须是 kebab-case 格式");
  }
  if (!args.description) {
    throw new Error("--description 不能为空");
  }

  let category;
  if (args.newCategory) {
    if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(args.newCategory)) {
      throw new Error("--new-category 必须是 kebab-case 格式");
    }
    category = args.newCategory;
    const categoryPath = path.join(SKILLS_ROOT, category);
    await fs.mkdir(categoryPath, { recursive: true });
    console.log(`✓ 创建新分类: ${category}`);
  } else if (args.category) {
    const existingCategories = await scanCategories();
    if (!existingCategories.includes(args.category)) {
      throw new Error(`分类 "${args.category}" 不存在。现有分类: ${existingCategories.join(", ")}`);
    }
    category = args.category;
  } else {
    throw new Error("必须指定 --category 或 --new-category");
  }

  const runtime = args.runtime
    ? args.runtime.split(",").map((r) => r.trim()).filter(Boolean)
    : ["markdown"];

  return {
    skillName: args.name,
    description: args.description,
    category,
    runtime,
    requiresKnowledge: args.requiresKnowledge,
    optional: args.optional,
  };
}

async function buildConfigInteractive() {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log("=== 创建新 Skill ===\n");

  // 1. 输入 skill 名称
  const skillName = await rl.question("Skill 名称（kebab-case，如 my-new-skill）: ");
  if (!skillName || !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(skillName)) {
    rl.close();
    throw new Error("Skill 名称必须是 kebab-case 格式（小写字母、数字、连字符）");
  }

  // 2. 输入简短描述
  const description = await rl.question("简短描述（一句话说明用途）: ");
  if (!description) {
    rl.close();
    throw new Error("描述不能为空");
  }

  // 3. 扫描现有分类
  const existingCategories = await scanCategories();
  console.log("\n现有分类:");
  existingCategories.forEach((cat, index) => {
    console.log(`  ${index + 1}. ${cat}`);
  });
  console.log(`  ${existingCategories.length + 1}. 创建新分类\n`);

  const categoryChoice = await rl.question(`选择分类（1-${existingCategories.length + 1}）: `);
  const choiceIndex = parseInt(categoryChoice, 10) - 1;

  let category;
  if (choiceIndex === existingCategories.length) {
    // 创建新分类
    category = await rl.question("新分类名称（kebab-case，如 my-category）: ");
    if (!category || !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(category)) {
      rl.close();
      throw new Error("分类名称必须是 kebab-case 格式");
    }
    const categoryPath = path.join(SKILLS_ROOT, category);
    await fs.mkdir(categoryPath, { recursive: true });
    console.log(`✓ 创建新分类: ${category}`);
  } else if (choiceIndex >= 0 && choiceIndex < existingCategories.length) {
    category = existingCategories[choiceIndex];
  } else {
    rl.close();
    throw new Error("无效的选择");
  }

  // 4. 运行时依赖
  console.log("\n运行时依赖（多选，逗号分隔，留空表示仅 markdown）:");
  console.log("  可选: node, python3, npx, playwright, browser, cdp, yt-dlp, local-knowledge, env-file");
  const runtimeInput = await rl.question("运行时: ");
  const runtime = runtimeInput
    ? runtimeInput.split(",").map((r) => r.trim()).filter(Boolean)
    : ["markdown"];

  // 5. 是否需要知识库
  const requiresKnowledgeInput = await rl.question("是否需要 AI_KNOWLEDGE_ROOT？(y/N): ");
  const requiresKnowledge = requiresKnowledgeInput.toLowerCase() === "y";

  // 6. 是否可选
  const optionalInput = await rl.question("是否为可选 skill？(y/N): ");
  const optional = optionalInput.toLowerCase() === "y";

  rl.close();

  return {
    skillName,
    description,
    category,
    runtime,
    requiresKnowledge,
    optional,
  };
}

async function createSkill(config) {
  const { skillName, description, category, runtime, requiresKnowledge, optional } = config;

  // 创建 skill 目录和文件
  const skillPath = path.join(SKILLS_ROOT, category, skillName);
  await fs.mkdir(skillPath, { recursive: true });

  const skillTitle = skillName
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

  const skillContent = SKILL_TEMPLATE
    .replace(/{{SKILL_NAME}}/g, skillName)
    .replace(/{{DESCRIPTION}}/g, description)
    .replace(/{{SKILL_TITLE}}/g, skillTitle);

  await fs.writeFile(path.join(skillPath, "SKILL.md"), skillContent, "utf8");
  console.log(`\n✓ 创建 skill 目录: ${category}/${skillName}`);
  console.log(`✓ 创建 SKILL.md`);

  // 更新 manifest
  const manifest = JSON.parse(await fs.readFile(MANIFEST_PATH, "utf8"));
  const newSkillEntry = {
    name: skillName,
    runtime,
    requiresKnowledge,
    optional,
  };

  // 按字母顺序插入
  const insertIndex = manifest.skills.findIndex((s) => s.name > skillName);
  if (insertIndex === -1) {
    manifest.skills.push(newSkillEntry);
  } else {
    manifest.skills.splice(insertIndex, 0, newSkillEntry);
  }

  await fs.writeFile(MANIFEST_PATH, JSON.stringify(manifest, null, 2) + "\n", "utf8");
  console.log(`✓ 更新 config/skills-manifest.json`);

  console.log("\n=== 创建完成 ===");
  console.log(`\n下一步:`);
  console.log(`  1. 编辑 ${category}/${skillName}/SKILL.md 完善内容`);
  console.log(`  2. 如需脚本或资源，在 ${category}/${skillName}/ 下创建 scripts/ 或其他目录`);
  console.log(`  3. 运行 ./scripts/bootstrap.sh --apply 创建软链接`);
  console.log(`  4. 运行 node ./scripts/doctor.mjs 验证配置`);
}

async function scanCategories() {
  const entries = await fs.readdir(SKILLS_ROOT, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith("."))
    .map((entry) => entry.name)
    .sort();
}
