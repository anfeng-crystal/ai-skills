import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));

export const CATEGORY_NAMES = new Set(["core", "automation", "kingdee", "meta", "incoming"]);

export function loadConfig() {
  const fileConfig = readConfigFile();
  const home = path.resolve(process.env.AI_HOST_HOME || fileConfig.home || os.homedir());
  const sourceRoot = path.resolve(
    process.env.AI_SKILLS_HOME ||
      fileConfig.sourceRoot ||
      inferSourceRoot() ||
      defaultSourceRoot(home),
  );

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

function defaultSourceRoot(home) {
  return path.join(home, "AI", "skills", "active");
}

function inferSourceRoot() {
  const cwd = process.cwd();
  if (looksLikeSourceRoot(cwd)) {
    return cwd;
  }

  const activeAncestor = findNamedAncestor(SCRIPT_DIR, "active");
  if (activeAncestor && looksLikeSourceRoot(activeAncestor)) {
    return activeAncestor;
  }

  let current = SCRIPT_DIR;
  for (let depth = 0; depth < 10; depth += 1) {
    if (looksLikeSourceRoot(current)) {
      return current;
    }

    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }

  return null;
}

function findNamedAncestor(startDir, name) {
  let current = startDir;
  for (let depth = 0; depth < 10; depth += 1) {
    if (path.basename(current) === name) {
      return current;
    }

    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }

  return null;
}

function looksLikeSourceRoot(dir) {
  return hasSkillChild(dir, 0);
}

function hasSkillChild(dir, depth) {
  if (depth > 2) return false;

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

    const fullPath = path.join(dir, entry.name);
    if (fs.existsSync(path.join(fullPath, "SKILL.md"))) {
      return true;
    }

    if (hasSkillChild(fullPath, depth + 1)) {
      return true;
    }
  }

  return false;
}
