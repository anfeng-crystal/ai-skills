import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { CATEGORY_NAMES } from "./config.mjs";
import { buildPlan, applyPlan, listSourceSkills } from "./sync-links.mjs";

const execFileAsync = promisify(execFile);
const EXCLUDED_DIRS = new Set([".git", "node_modules", "dist", ".cache", "tmp", "temp"]);
const EXCLUDED_FILES = new Set([".DS_Store"]);

export async function buildInstallPlan(options) {
  const prepared = await prepareInstallSource(options);
  try {
    const sourceSkillDir = options.path
      ? path.resolve(prepared.rootPath, options.path)
      : prepared.rootPath;
    const skillMdPath = path.join(sourceSkillDir, "SKILL.md");
    const frontmatter = await readSkillFrontmatter(skillMdPath);

    if (!frontmatter.exists) {
      return installResult(options, prepared, {
        ok: false,
        status: "invalid_source",
        reason: "skill_md_missing",
        sourceSkillDir,
      });
    }

    const skillName = kebabCase(options.name || frontmatter.name || path.basename(sourceSkillDir));
    const category = resolveCategory(options.category, frontmatter);
    const targetRelativePath = path.posix.join("skills", category, skillName);
    const targetPath = path.join(options.sourceRoot, ...targetRelativePath.split("/"));
    const targetExists = await pathExists(targetPath);
    const collidingSkills = await findCollidingSkills(options.sourceRoot, skillName, targetRelativePath);
    const willSync = category !== "incoming";

    return installResult(options, prepared, {
      ok: !targetExists && collidingSkills.length === 0,
      status: targetExists
        ? "target_exists"
        : collidingSkills.length > 0
          ? "source_name_collision"
          : category === "incoming"
            ? "needs_review"
            : "planned",
      reason: targetExists
        ? "target_directory_exists"
        : collidingSkills.length > 0
          ? "multiple_source_skills_share_target_name"
          : category === "incoming"
            ? "incoming_not_synced"
            : "ready_to_install",
      sourceSkillDir,
      skillName,
      category,
      targetRelativePath,
      targetPath,
      targetExists,
      collidingSkills,
      willSync,
      plannedSyncSkill: willSync ? targetRelativePath : null,
      frontmatter,
    });
  } finally {
    if (prepared.cleanupPath && !options.apply) {
      await fs.rm(prepared.cleanupPath, { recursive: true, force: true });
    }
  }
}

async function findCollidingSkills(sourceRoot, skillName, targetRelativePath) {
  const skills = await listSourceSkills(sourceRoot, { includeExcluded: true });
  return skills.filter((skill) => path.posix.basename(skill) === skillName && skill !== targetRelativePath);
}

export async function applyInstallPlan(plan) {
  if (!plan.ok || plan.status === "target_exists" || !plan.sourceSkillDir || !plan.targetPath) {
    return {
      ...plan,
      applied: false,
    };
  }

  try {
    await copySkillDirectory(plan.sourceSkillDir, plan.targetPath);

    let syncPlan = null;
    if (plan.willSync) {
      syncPlan = await buildPlan({
        ...plan.options,
        skills: [plan.targetRelativePath],
      });
      await applyPlan(syncPlan.records);
    }

    return {
      ...plan,
      status: "installed",
      reason: plan.willSync ? "installed_and_synced" : "installed_to_incoming",
      targetExists: true,
      applied: true,
      syncPlan,
    };
  } finally {
    if (plan.cleanupPath) {
      await fs.rm(plan.cleanupPath, { recursive: true, force: true });
    }
  }
}

async function prepareInstallSource(options) {
  if (!options.installSource) {
    throw new Error("错误：install 子命令需要指定本地路径或 Git URL");
  }

  if (isGitUrl(options.installSource)) {
    const tempRoot = await fs.mkdtemp(path.join(os.tmpdir(), "skill-installer-install-"));
    const clonePath = path.join(tempRoot, "repo");
    await execFileAsync("git", ["clone", "--depth", "1", options.installSource, clonePath]);
    return {
      input: options.installSource,
      type: "git",
      rootPath: clonePath,
      cleanupPath: tempRoot,
    };
  }

  return {
    input: options.installSource,
    type: "local",
    rootPath: path.resolve(options.installSource),
    cleanupPath: null,
  };
}

function installResult(options, prepared, fields) {
  return {
    sourceRoot: options.sourceRoot,
    home: options.home,
    command: "install",
    applied: false,
    options: sanitizeOptions(options),
    input: prepared.input,
    inputType: prepared.type,
    cleanupPath: prepared.cleanupPath,
    ...fields,
  };
}

function sanitizeOptions(options) {
  return {
    sourceRoot: options.sourceRoot,
    home: options.home,
    skills: options.skills || [],
    tools: options.tools || [],
    category: options.category,
    name: options.name,
    path: options.path,
  };
}

function resolveCategory(category, frontmatter) {
  if (!category) {
    throw new Error("错误：install 子命令需要指定 --category");
  }

  if (category !== "auto") {
    if (!CATEGORY_NAMES.has(category)) {
      throw new Error(`错误：未知 category: ${category}`);
    }
    return category;
  }

  const text = [
    frontmatter.name,
    frontmatter.description,
    ...(Array.isArray(frontmatter.tags) ? frontmatter.tags : []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  if (/(金蝶|苍穹|kingdee|cosmic|bos|元数据|sdk)/i.test(text)) return "kingdee";
  if (/(playwright|browser|web-access|e2e|automation|data|spreadsheet|document)/i.test(text)) return "automation";
  if (/(darwin|meta|linker|vetter|multi-agent|search)/i.test(text)) return "meta";
  if (/(explain|review|fix|implement|clarify|core)/i.test(text)) return "core";

  return "incoming";
}

async function readSkillFrontmatter(skillMdPath) {
  try {
    const content = await fs.readFile(skillMdPath, "utf8");
    return {
      exists: true,
      ...parseFrontmatter(content),
    };
  } catch {
    return { exists: false };
  }
}

function parseFrontmatter(content) {
  if (!content.startsWith("---")) {
    return {};
  }

  const end = content.indexOf("\n---", 3);
  if (end === -1) {
    return {};
  }

  const values = {};
  for (const rawLine of content.slice(3, end).split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;

    const match = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!match) continue;

    const [, key, rawValue] = match;
    values[key] = parseScalar(rawValue);
  }

  return values;
}

function parseScalar(value) {
  const trimmed = value.trim();
  if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
    return trimmed
      .slice(1, -1)
      .split(",")
      .map((item) => normalizeScalar(item))
      .filter(Boolean);
  }
  return normalizeScalar(trimmed);
}

function normalizeScalar(value) {
  return String(value).trim().replace(/^['"]|['"]$/g, "");
}

function kebabCase(value) {
  return String(value)
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .replace(/[^A-Za-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
}

function isGitUrl(value) {
  return /^(https?:\/\/|git@|ssh:\/\/).+\.git(?:#.+)?$/.test(value) || /^https:\/\/github\.com\/[^/]+\/[^/]+(?:\.git)?$/.test(value);
}

async function pathExists(targetPath) {
  try {
    await fs.lstat(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function copySkillDirectory(sourceDir, targetDir) {
  await fs.mkdir(path.dirname(targetDir), { recursive: true });
  await copyRecursive(sourceDir, targetDir);
}

async function copyRecursive(source, target) {
  const stat = await fs.lstat(source);
  if (stat.isDirectory()) {
    await fs.mkdir(target, { recursive: true });
    const entries = await fs.readdir(source, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory() && EXCLUDED_DIRS.has(entry.name)) continue;
      if (entry.isFile() && EXCLUDED_FILES.has(entry.name)) continue;
      await copyRecursive(path.join(source, entry.name), path.join(target, entry.name));
    }
    return;
  }

  if (stat.isFile()) {
    await fs.copyFile(source, target);
  }
}
