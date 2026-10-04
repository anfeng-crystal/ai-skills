import fs from "node:fs/promises";
import path from "node:path";

const MAX_SKILL_DEPTH = 4;
const MAX_SCAN_BYTES = 256 * 1024;
const IGNORED_DIRS = new Set([
  ".git", ".svn", ".hg", "node_modules", "dist", "build", "__pycache__", ".idea", ".vscode",
]);
const TEXT_EXTENSIONS = new Set([
  ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".sh", ".bash", ".zsh",
  ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".bat", ".ps1",
]);
export const BINARY_EXTENSIONS = new Set([
  ".jar", ".db", ".sqlite", ".class", ".pyc", ".zip", ".exe", ".dll", ".so", ".dylib",
]);
export const AGENT_FILES = new Set(["AGENTS.md", "CLAUDE.md", "openai.yaml", "plugin.json"]);

export async function resolveSkillTarget(inputPath) {
  const inputStat = await fs.lstat(inputPath).catch(() => null);
  if (path.basename(inputPath) === "SKILL.md" && (inputStat?.isFile() || inputStat?.isSymbolicLink())) {
    // Resolve the parent alias, not an untrusted SKILL.md link into another tree.
    const root = await fs.realpath(path.dirname(inputPath));
    return { scanRoot: root, skillRoots: [root] };
  }
  // The explicitly selected root may itself be a host's managed alias.
  const resolved = await fs.realpath(inputPath).catch(() => null);
  if (!resolved) throw new Error(`Path not found: ${inputPath}`);
  const stat = await fs.stat(resolved);
  if (stat.isFile()) {
    if (path.basename(inputPath) !== "SKILL.md") {
      throw new Error(`Expected a skill directory or SKILL.md, got file: ${inputPath}`);
    }
    return { scanRoot: path.dirname(resolved), skillRoots: [path.dirname(resolved)] };
  }
  if (!stat.isDirectory()) throw new Error(`Expected a skill directory: ${inputPath}`);
  if (await hasEntry(resolved)) return { scanRoot: resolved, skillRoots: [resolved] };

  const skillRoots = [];
  const discoveryGaps = [];
  await searchSkillRoots(resolved, 0, skillRoots, discoveryGaps);
  if (!skillRoots.length) throw new Error(`No SKILL.md found under: ${inputPath}`);
  return { scanRoot: resolved, skillRoots: skillRoots.sort(), discoveryGaps };
}

async function hasEntry(root) {
  const stat = await fs.lstat(path.join(root, "SKILL.md")).catch(() => null);
  return Boolean(stat && (stat.isFile() || stat.isSymbolicLink()));
}

async function searchSkillRoots(root, depth, found, gaps) {
  if (depth > MAX_SKILL_DEPTH) {
    gaps.push({ filePath: root, reason: "entry_discovery_depth_limit" });
    return;
  }
  let entries;
  try {
    entries = await fs.readdir(root, { withFileTypes: true });
  } catch (error) {
    gaps.push({ filePath: root, reason: `unreadable_directory:${error.code || "unknown"}` });
    return;
  }
  for (const entry of entries) {
    if (!entry.isDirectory() || IGNORED_DIRS.has(entry.name)) continue;
    const child = path.join(root, entry.name);
    if (await hasEntry(child)) found.push(child);
    else await searchSkillRoots(child, depth + 1, found, gaps);
  }
}

export async function collectFiles(root) {
  const collected = [];
  const unscanned = [];
  async function walk(dir) {
    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch (error) {
      unscanned.push({ filePath: dir, reason: `unreadable_directory:${error.code || "unknown"}` });
      return;
    }
    for (const entry of entries) {
      const child = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (IGNORED_DIRS.has(entry.name)) unscanned.push({ filePath: child, reason: "excluded_directory" });
        else await walk(child);
      } else collected.push(child);
    }
  }
  await walk(root);
  return { files: collected.sort(), unscanned };
}

export async function readScanText(filePath) {
  try {
    // Never implicitly follow links found inside an untrusted package.
    const stat = await fs.lstat(filePath);
    if (stat.isSymbolicLink()) return { reason: "symbolic_link_not_followed" };
    if (!stat.isFile()) return { reason: "non_regular_file" };
    if (stat.size > MAX_SCAN_BYTES) return { reason: "file_exceeds_256_kib" };
    if (!TEXT_EXTENSIONS.has(path.extname(filePath).toLowerCase())) {
      return { reason: "unsupported_file_type" };
    }
    const bytes = await fs.readFile(filePath);
    if (bytes.length > MAX_SCAN_BYTES) return { reason: "file_exceeds_256_kib" };
    let text;
    try {
      text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    } catch {
      return { reason: "invalid_utf8" };
    }
    if (text.includes("\0")) return { reason: "nul_byte_in_text" };
    return { text };
  } catch (error) {
    return { reason: `unreadable_file:${error.code || "unknown"}` };
  }
}
