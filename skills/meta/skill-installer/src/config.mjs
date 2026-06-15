import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));

export const CATEGORY_NAMES = new Set(["incoming"]);

export async function loadCategoryNames(sourceRoot) {
  const fixed = new Set(["incoming"]);
  await addCategoryNamesFromDir(fixed, sourceRoot);
  await addCategoryNamesFromDir(fixed, path.join(sourceRoot, "skills"));
  return fixed;
}

async function addCategoryNamesFromDir(categories, root) {
  try {
    const entries = await fs.promises.readdir(root, { withFileTypes: true });
    for (const e of entries) {
      if (e.isDirectory() && isCategoryDirectory(e.name)) {
        categories.add(e.name);
      }
    }
  } catch {
    // 缺失的布局目录忽略；调用方会保留 incoming 兜底。
  }
}

function isCategoryDirectory(name) {
  return !name.startsWith(".") && !["node_modules", "scripts", "test", "tmp", "temp"].includes(name);
}

export function loadConfig() {
  const fileConfig = readConfigFile();
  const home = path.resolve(process.env.AI_HOST_HOME || fileConfig.home || os.homedir());
  const configuredSourceRoot = process.env.AI_SKILLS_HOME || fileConfig.sourceRoot || inferSourceRoot();
  const sourceRoot = configuredSourceRoot ? path.resolve(configuredSourceRoot) : null;

  return {
    ...fileConfig,
    sourceRoot,
    home,
    targetDirs: fileConfig.targetDirs || {},
    hermesConfigPath: fileConfig.hermesConfigPath || null,
  };
}

export function configFilePath() {
  if (process.platform === "win32") {
    const appData = process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming");
    return path.join(appData, "skill-installer", "config.json");
  }

  const configHome = process.env.XDG_CONFIG_HOME || path.join(os.homedir(), ".config");
  return path.join(configHome, "skill-installer", "config.json");
}

function readConfigFile() {
  try {
    return JSON.parse(fs.readFileSync(configFilePath(), "utf8"));
  } catch {
    return {};
  }
}

function inferSourceRoot() {
  const scriptRoot = findSourceRootAncestor(SCRIPT_DIR);
  if (scriptRoot) {
    return scriptRoot;
  }

  const cwd = process.cwd();
  if (looksLikeSourceRoot(cwd)) {
    return cwd;
  }

  const cwdSkills = path.join(cwd, "skills");
  return looksLikeSourceRoot(cwdSkills) ? cwdSkills : null;
}

function looksLikeSourceRoot(dir) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return false;
  }

  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name.startsWith(".")) {
      continue;
    }

    if (hasDirectSkillChild(path.join(dir, entry.name))) {
      return true;
    }
  }

  return null;
}

function hasDirectSkillChild(dir) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return false;
  }

  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name.startsWith(".")) {
      continue;
    }

    if (fs.existsSync(path.join(dir, entry.name, "SKILL.md"))) {
      return true;
    }
  }

  return false;
}

function findSourceRootAncestor(startDir) {
  let current = startDir;
  for (let depth = 0; depth < 10; depth += 1) {
    if (looksLikeSourceRoot(current)) {
      return current;
    }

    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }

  return false;
}
