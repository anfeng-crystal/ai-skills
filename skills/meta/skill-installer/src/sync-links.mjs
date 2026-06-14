/**
 * 软链接分发核心逻辑
 */

import fs from "node:fs/promises";
import path from "node:path";

const TARGET_DIR_SUFFIXES = {
  codex: ".codex/skills",
  claude: ".claude/skills",
  junie: ".junie/skills",
  agents: ".agents/skills",
  hermes: ".hermes/skills",
  qoder: ".qoder/skills",
  qoderwork: ".qoderwork/skills",
  workbuddy: ".workbuddy/skills",
  trae: ".trae/skills",
  openclaw: ".openclaw/workspace/skills",
  opencode: ".opencode/skills",
  "antigravity-cli": ".gemini/antigravity-cli/skills",
  "antigravity-desktop": ".gemini/config/plugins/anfeng-active-skills/skills",
};

const TOOL_ALIASES = {
  agy: "antigravity-cli",
  "claude-code": "claude",
  antigravity: "antigravity-cli",
  "qoder-work": "qoderwork",
  "trae-ide": "trae",
};

const DEFAULT_EXCLUDED_SOURCE_PREFIXES = ["incoming/", "skills/incoming/"];

/**
 * 只把带 SKILL.md 的可见目录视为可分发 skill。
 * 支持递归扫描子目录（最多 2 层）。
 */
export async function listSourceSkills(sourceRoot, options = {}) {
  const result = [];

  async function scanDir(dir, depth = 0) {
    if (depth > 2) return;

    const entries = await fs.readdir(dir, { withFileTypes: true });

    for (const entry of entries) {
      if (!entry.isDirectory() || entry.name.startsWith(".")) {
        continue;
      }

      const fullPath = path.join(dir, entry.name);

      // 检查是否有 SKILL.md
      try {
        const stat = await fs.stat(path.join(fullPath, "SKILL.md"));
        if (stat.isFile()) {
          // 计算相对于 sourceRoot 的路径
          const relativePath = path.relative(sourceRoot, fullPath);
          const normalizedRelativePath = toSkillId(relativePath);
          if (options.includeExcluded || !isExcludedSourceSkill(normalizedRelativePath)) {
            result.push(normalizedRelativePath);
          }
        }
      } catch {
        // 没有 SKILL.md，继续递归扫描
        if (depth < 2) {
          await scanDir(fullPath, depth + 1);
        }
      }
    }
  }

  await scanDir(sourceRoot);
  return result.sort();
}

/**
 * 根据 host home 推导各宿主的固定 skills 目录。
 */
export function buildTargets(hostHome, config = {}) {
  return Object.entries(TARGET_DIR_SUFFIXES).map(([name, suffix]) => ({
    name,
    root: path.resolve(config.targetDirs?.[name] || path.join(hostHome, suffix)),
    hermesConfigPath: name === "hermes"
      ? path.resolve(config.hermesConfigPath || path.join(hostHome, ".hermes", "config.yaml"))
      : null,
    invalid: false,
  }));
}

export function linkTypeForPlatform(platform = process.platform) {
  return platform === "win32" ? "junction" : "dir";
}

/**
 * 只接受白名单工具名；路径形式或未知工具都视为校验失败。
 */
export function resolveTools(requestedTools, hostHome, config = {}) {
  const targets = buildTargets(hostHome, config);
  if (requestedTools.length === 0) {
    return targets.map((target) => ({ ...target, explicit: false }));
  }

  return requestedTools.map((tool) => {
    const resolvedTool = TOOL_ALIASES[tool] || tool;
    const match = targets.find((candidate) => candidate.name === resolvedTool);
    if (!match) {
      return {
        name: tool,
        root: null,
        hermesConfigPath: null,
        invalid: true,
        explicit: true,
      };
    }

    return { ...match, explicit: true };
  });
}

/**
 * 为每个 skill 和工具目标生成审计记录。
 */
export async function buildPlan(options) {
  const availableSkills = await listSourceSkills(options.sourceRoot);
  const selectedSkills = resolveSelectedSkills(options.skills, availableSkills);
  const sourceNameCollisions = findSourceNameCollisions(availableSkills);
  const blockedSkillNames = new Set();
  const tools = resolveTools(options.tools, options.home, options.config);
  const records = [];

  for (const tool of tools) {
    if (tool.invalid) {
      records.push({
        scannedAt: new Date().toISOString(),
        tool: tool.name,
        skill: null,
        sourcePath: null,
        sourceExists: false,
        sourceIsDir: false,
        sourceHasSkillMd: false,
        targetRoot: null,
        targetPath: null,
        targetExists: false,
        targetType: "missing",
        targetIsSymlink: false,
        targetLinkRaw: null,
        targetLinkResolved: null,
        action: "skip",
        status: "invalid_tool",
        reason: "tool_not_in_whitelist",
        wouldChange: false,
      });
    }
  }

  for (const collision of sourceNameCollisions) {
    const selected = selectedSkills.some((skill) =>
      skill === collision.targetName || path.basename(skill) === collision.targetName || collision.skills.includes(skill)
    );
    if (!selected) {
      continue;
    }

    for (const skill of collision.skills) {
      blockedSkillNames.add(skill);
    }
    blockedSkillNames.add(collision.targetName);

    records.push({
      scannedAt: new Date().toISOString(),
      tool: "source",
      skill: collision.targetName,
      sourcePath: null,
      sourceExists: true,
      sourceIsDir: true,
      sourceHasSkillMd: true,
      sourcePaths: collision.skills.map((skill) => path.join(options.sourceRoot, skill)),
      targetRoot: null,
      targetPath: null,
      targetExists: false,
      targetType: "missing",
      targetIsSymlink: false,
      targetLinkRaw: null,
      targetLinkResolved: null,
      action: "skip",
      status: "source_name_collision",
      reason: "multiple_source_skills_share_target_name",
      wouldChange: false,
    });
  }

  for (const skill of selectedSkills) {
    if (blockedSkillNames.has(skill) || blockedSkillNames.has(path.basename(skill))) {
      continue;
    }

    const sourcePath = path.join(options.sourceRoot, skill);
    const sourceMeta = await inspectSource(sourcePath, availableSkills.includes(skill));

    if (!sourceMeta.sourceHasSkillMd) {
      records.push({
        scannedAt: new Date().toISOString(),
        tool: "source",
        skill,
        ...sourceMeta,
        targetRoot: null,
        targetPath: null,
        targetExists: false,
        targetType: "missing",
        targetIsSymlink: false,
        targetLinkRaw: null,
        targetLinkResolved: null,
        action: "skip",
        status: sourceMeta.sourceExists ? "invalid_source" : "missing_skill",
        reason: sourceMeta.sourceExists ? "skill_md_missing" : "skill_not_found_in_source_root",
        wouldChange: false,
      });
      continue;
    }

    for (const tool of tools.filter((item) => !item.invalid)) {
      records.push(await inspectTarget(tool, skill, sourceMeta));
    }
  }

  return {
    sourceRoot: options.sourceRoot,
    home: options.home,
    tools: tools.filter((item) => !item.invalid),
    summary: summarize(records),
    records,
  };

  // 孤儿链接检测：全量同步时扫描各宿主，找出指向 sourceRoot 内部的断裂 symlink。
  if (selectedSkills.length === 0 || selectedSkills === availableSkills) {
    for (const tool of tools.filter((item) => !item.invalid && item.name !== "hermes")) {
      const orphans = await findOrphanLinks(tool, options.sourceRoot);
      for (const orphan of orphans) {
        records.push({
          scannedAt: new Date().toISOString(),
          tool: tool.name,
          skill: orphan.skillName,
          sourcePath: orphan.resolvedTarget,
          sourceExists: false, sourceIsDir: false, sourceHasSkillMd: false,
          targetRoot: tool.root, targetPath: orphan.targetPath,
          targetExists: true, targetType: "symlink", targetIsSymlink: true,
          targetLinkRaw: orphan.rawTarget, targetLinkResolved: orphan.resolvedTarget,
          action: "remove_orphan_link", status: "orphan_link",
          reason: "dangling_symlink_into_source_root", wouldChange: true,
        });
      }
    }
  }

  return {
    sourceRoot: options.sourceRoot,
    home: options.home,
    tools: tools.filter((item) => !item.invalid),
    summary: summarize(records),
    records,
  };
}


function isExcludedSourceSkill(skillId) {
  return DEFAULT_EXCLUDED_SOURCE_PREFIXES.some((prefix) => skillId.startsWith(prefix));
}

function toSkillId(value) {
  return value.split(path.sep).join(path.posix.sep);
}

function resolveSelectedSkills(requestedSkills, availableSkills) {
  if (requestedSkills.length === 0) {
    return availableSkills;
  }

  return requestedSkills.map((skill) => {
    if (availableSkills.includes(skill)) {
      return skill;
    }

    const basenameMatches = availableSkills.filter((availableSkill) => path.basename(availableSkill) === skill);
    if (basenameMatches.length === 1) {
      return basenameMatches[0];
    }

    return skill;
  });
}

function findSourceNameCollisions(skills) {
  const byTargetName = new Map();
  for (const skill of skills) {
    const targetName = path.basename(skill);
    const existing = byTargetName.get(targetName) || [];
    existing.push(skill);
    byTargetName.set(targetName, existing);
  }

  return Array.from(byTargetName.entries())
    .filter(([, matchingSkills]) => matchingSkills.length > 1)
    .map(([targetName, matchingSkills]) => ({
      targetName,
      skills: matchingSkills.sort(),
    }));
}

/**
 * 检查源目录是否存在、是否为目录、是否带 SKILL.md。
 */
async function inspectSource(sourcePath, knownSkill) {
  try {
    const sourceStat = await fs.stat(sourcePath);
    const skillStat = await fs.stat(path.join(sourcePath, "SKILL.md"));
    return {
      sourcePath,
      sourceExists: sourceStat.isDirectory(),
      sourceIsDir: sourceStat.isDirectory(),
      sourceHasSkillMd: skillStat.isFile() && knownSkill,
    };
  } catch {
    return {
      sourcePath,
      sourceExists: false,
      sourceIsDir: false,
      sourceHasSkillMd: false,
    };
  }
}

/**
 * 检查单个目标位置当前状态，并给出严格的 v1 计划动作。
 */
async function inspectTarget(tool, skill, sourceMeta) {
  if (tool.name === "hermes") {
    return inspectHermesTarget(tool, skill, sourceMeta);
  }

  const targetRoot = tool.root;
  // 只使用 skill 的最后一段作为目标目录名
  const skillName = path.basename(skill);
  const targetPath = path.join(targetRoot, skillName);

  try {
    const rootStat = await fs.lstat(targetRoot);
    if (!rootStat.isDirectory()) {
      return buildRecord(tool.name, skill, sourceMeta, {
        targetRoot,
        targetPath,
        targetExists: false,
        targetType: "missing_root",
        targetIsSymlink: false,
        targetLinkRaw: null,
        targetLinkResolved: null,
        action: "skip",
        status: tool.explicit ? "missing_target_root" : "optional_host_unavailable",
        reason: tool.explicit ? "target_root_is_not_directory" : "optional_host_target_root_is_not_directory",
        wouldChange: false,
      });
    }
  } catch {
    return buildRecord(tool.name, skill, sourceMeta, {
      targetRoot,
      targetPath,
      targetExists: false,
      targetType: "missing_root",
      targetIsSymlink: false,
      targetLinkRaw: null,
      targetLinkResolved: null,
      action: "skip",
      status: tool.explicit ? "missing_target_root" : "optional_host_unavailable",
      reason: tool.explicit ? "target_root_missing" : "optional_host_target_root_missing",
      wouldChange: false,
    });
  }

  try {
    const targetStat = await fs.lstat(targetPath);
    if (targetStat.isSymbolicLink()) {
      const targetLinkRaw = await fs.readlink(targetPath);
      const targetLinkResolved = path.resolve(path.dirname(targetPath), targetLinkRaw);

      if (targetLinkResolved === sourceMeta.sourcePath) {
        return buildRecord(tool.name, skill, sourceMeta, {
          targetRoot,
          targetPath,
          targetExists: true,
          targetType: "symlink",
          targetIsSymlink: true,
          targetLinkRaw,
          targetLinkResolved,
          action: "noop",
          status: "already_linked",
          reason: "link_matches_source",
          wouldChange: false,
        });
      }

      if (isLegacyActiveRootLink(targetLinkResolved, sourceMeta.sourcePath, skill)) {
        return buildRecord(tool.name, skill, sourceMeta, {
          targetRoot,
          targetPath,
          targetExists: true,
          targetType: "symlink",
          targetIsSymlink: true,
          targetLinkRaw,
          targetLinkResolved,
          action: "replace_link",
          status: "planned",
          reason: "legacy_active_root_link",
          wouldChange: true,
        });
      }

      return buildRecord(tool.name, skill, sourceMeta, {
        targetRoot,
        targetPath,
        targetExists: true,
        targetType: "symlink",
        targetIsSymlink: true,
        targetLinkRaw,
        targetLinkResolved,
        action: "skip",
        status: "external_symlink_conflict",
        reason: "existing_symlink_points_outside_active_source",
        wouldChange: false,
      });
    }

    return buildRecord(tool.name, skill, sourceMeta, {
      targetRoot,
      targetPath,
      targetExists: true,
      targetType: targetStat.isDirectory() ? "directory" : "file",
      targetIsSymlink: false,
      targetLinkRaw: null,
      targetLinkResolved: null,
      action: "skip",
      status: "real_path_conflict",
      reason: targetStat.isDirectory() ? "real_directory_exists" : "real_file_exists",
      wouldChange: false,
    });
  } catch {
    return buildRecord(tool.name, skill, sourceMeta, {
      targetRoot,
      targetPath,
      targetExists: false,
      targetType: "missing",
      targetIsSymlink: false,
      targetLinkRaw: null,
      targetLinkResolved: null,
      action: "create_link",
      status: "planned",
      reason: "target_missing",
      wouldChange: true,
    });
  }
}

function isLegacyActiveRootLink(targetLinkResolved, sourcePath, skill) {
  const skillParts = skill.split("/").filter(Boolean);
  const sourceRoot = ancestorDir(sourcePath, skillParts.length);
  const legacyPath = path.join(sourceRoot, "active", "skills", ...skillParts);
  return path.resolve(targetLinkResolved) === path.resolve(legacyPath);
}

function ancestorDir(dir, levels) {
  let current = dir;
  for (let i = 0; i < levels; i += 1) {
    current = path.dirname(current);
  }
  return current;
}

/**
 * 扫描宿主目标目录，找出指向 sourceRoot 内部但目标已不存在的断裂 symlink。
 * 只回收 skill-installer 自己创建的链接，不触碰外部链接或真实目录。
 */
async function findOrphanLinks(tool, sourceRoot) {
  const resolvedSourceRoot = path.resolve(sourceRoot);
  const orphans = [];
  let entries;
  try { entries = await fs.readdir(tool.root, { withFileTypes: true }); } catch { return orphans; }

  for (const entry of entries) {
    if (entry.name.startsWith(".") || !entry.isSymbolicLink()) continue;
    const targetPath = path.join(tool.root, entry.name);
    let rawTarget;
    try { rawTarget = await fs.readlink(targetPath); } catch { continue; }
    const resolvedTarget = path.resolve(tool.root, rawTarget);
    if (resolvedTarget !== resolvedSourceRoot && !resolvedTarget.startsWith(resolvedSourceRoot + path.sep)) continue;
    try { await fs.stat(targetPath); continue; } catch {} // 目标仍存在则跳过
    orphans.push({ skillName: entry.name, targetPath, rawTarget, resolvedTarget });
  }
  return orphans;
}

/**
 * Hermes 通过 config.yaml 里的 skills.external_dirs 原生发现统一源目录。
 * 保留旧软链接仅作兼容；新流程不再为 Hermes 创建目录级软链接。
 */
async function inspectHermesTarget(tool, skill, sourceMeta) {
  const targetRoot = tool.root;
  const targetPath = path.join(targetRoot, path.basename(skill));
  // 沿 sourcePath 向上查找包含在 external_dirs 中的祖先目录
  const sourceRoot = await findAncestorInExternalDirs(sourceMeta.sourcePath, tool.hermesConfigPath);
  const externalDirConfig = await inspectHermesExternalDirs(sourceRoot || path.dirname(sourceMeta.sourcePath), tool.hermesConfigPath);

  let targetMeta = {
    targetRoot,
    targetPath,
    targetExists: false,
    targetType: "missing",
    targetIsSymlink: false,
    targetLinkRaw: null,
    targetLinkResolved: null,
  };

  try {
    const targetStat = await fs.lstat(targetPath);
    if (targetStat.isSymbolicLink()) {
      const targetLinkRaw = await fs.readlink(targetPath);
      targetMeta = {
        ...targetMeta,
        targetExists: true,
        targetType: "symlink",
        targetIsSymlink: true,
        targetLinkRaw,
        targetLinkResolved: path.resolve(path.dirname(targetPath), targetLinkRaw),
      };
    } else {
      targetMeta = {
        ...targetMeta,
        targetExists: true,
        targetType: targetStat.isDirectory() ? "directory" : "file",
      };
    }
  } catch {
    // Target missing is valid when Hermes is using external_dirs.
  }

  if (!externalDirConfig.isConfigured) {
    return buildRecord(tool.name, skill, sourceMeta, {
      ...targetMeta,
      action: "skip",
      status: tool.explicit ? "needs_external_dir_config" : "optional_host_unavailable",
      reason: tool.explicit
        ? `hermes_missing_skills.external_dirs:${externalDirConfig.reason}`
        : `optional_host_hermes_external_dirs:${externalDirConfig.reason}`,
      wouldChange: false,
    });
  }

  if (
    targetMeta.targetExists &&
    (
      !targetMeta.targetIsSymlink ||
      targetMeta.targetLinkResolved !== sourceMeta.sourcePath
    )
  ) {
    return buildRecord(tool.name, skill, sourceMeta, {
      ...targetMeta,
      action: "skip",
      status: "hermes_local_shadow_conflict",
      reason: "local_skill_path_will_shadow_skills.external_dirs",
      wouldChange: false,
    });
  }

  return buildRecord(tool.name, skill, sourceMeta, {
    ...targetMeta,
    action: "noop",
    status: "managed_via_external_dir",
    reason: targetMeta.targetExists
      ? "hermes_uses_skills.external_dirs_legacy_link_retained"
      : "hermes_uses_skills.external_dirs",
    wouldChange: false,
  });
}

/**
 * 沿 sourcePath 向上查找，找到第一个在 hermes config.yaml external_dirs 中配置的祖先目录。
 * 用于支持分类目录结构（如 core/xxx）下 Hermes external_dirs 指向统一源根的情况。
 */
async function findAncestorInExternalDirs(sourcePath, hermesConfigPath) {
  if (!hermesConfigPath) return null;
  try {
    const raw = await fs.readFile(hermesConfigPath, "utf8");
    const configuredDirs = parseHermesExternalDirs(raw).map((entry) => path.resolve(entry));
    let current = sourcePath;
    for (let i = 0; i < 10; i++) {
      if (configuredDirs.includes(current)) return current;
      const parent = path.dirname(current);
      if (parent === current) break;
      current = parent;
    }
  } catch {}
  return null;
}

/**
 * 仅解析 Hermes 当前需要的 skills.external_dirs 配置，避免为脚本额外引入 YAML 依赖。
 */
async function inspectHermesExternalDirs(sourceRoot, hermesConfigPath) {
  try {
    const raw = await fs.readFile(hermesConfigPath, "utf8");
    const configuredDirs = parseHermesExternalDirs(raw).map((entry) => path.resolve(entry));
    const normalizedSourceRoot = path.resolve(sourceRoot);

    return {
      isConfigured: configuredDirs.includes(normalizedSourceRoot),
      reason: configuredDirs.length > 0 ? "source_root_not_listed" : "external_dirs_empty",
      configuredDirs,
    };
  } catch {
    return {
      isConfigured: false,
      reason: "config_unreadable",
      configuredDirs: [],
    };
  }
}

function parseHermesExternalDirs(content) {
  const lines = content.split(/\r?\n/);
  const results = [];
  let inSkills = false;
  let skillsIndent = -1;
  let inExternalDirs = false;
  let externalDirsIndent = -1;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const indent = line.length - line.trimStart().length;

    if (!inSkills) {
      if (/^skills:\s*$/.test(trimmed)) {
        inSkills = true;
        skillsIndent = indent;
      }
      continue;
    }

    if (indent <= skillsIndent && /^[A-Za-z0-9_-]+:\s*/.test(trimmed)) {
      inSkills = false;
      inExternalDirs = false;
      if (/^skills:\s*$/.test(trimmed)) {
        inSkills = true;
        skillsIndent = indent;
      }
      continue;
    }

    if (!inExternalDirs) {
      const match = trimmed.match(/^external_dirs:\s*(.*)$/);
      if (!match) {
        continue;
      }

      inExternalDirs = true;
      externalDirsIndent = indent;
      const rest = match[1].trim();
      if (rest.startsWith("[") && rest.endsWith("]")) {
        for (const entry of rest.slice(1, -1).split(",")) {
          const normalized = normalizeYamlScalar(entry);
          if (normalized) {
            results.push(normalized);
          }
        }
      }
      continue;
    }

    if (indent <= externalDirsIndent && /^[A-Za-z0-9_-]+:\s*/.test(trimmed)) {
      inExternalDirs = false;
      continue;
    }

    const itemMatch = trimmed.match(/^-\s+(.+)$/);
    if (!itemMatch) {
      continue;
    }

    const normalized = normalizeYamlScalar(itemMatch[1]);
    if (normalized) {
      results.push(normalized);
    }
  }

  return results;
}

function normalizeYamlScalar(value) {
  const trimmed = String(value).trim();
  if (!trimmed || trimmed === "[]") {
    return "";
  }
  return trimmed.replace(/^['"]|['"]$/g, "");
}

/**
 * 组装统一的审计记录，便于 dry-run 和 Darwin 评分。
 */
function buildRecord(tool, skill, sourceMeta, targetMeta) {
  return {
    scannedAt: new Date().toISOString(),
    tool,
    skill,
    sourcePath: sourceMeta.sourcePath,
    sourceExists: sourceMeta.sourceExists,
    sourceIsDir: sourceMeta.sourceIsDir,
    sourceHasSkillMd: sourceMeta.sourceHasSkillMd,
    ...targetMeta,
  };
}

/**
 * 汇总各类动作和状态数量，便于审阅 dry-run 结果。
 */
function summarize(records) {
  return records.reduce(
    (summary, record) => {
      summary.total += 1;
      summary.byAction[record.action] = (summary.byAction[record.action] || 0) + 1;
      summary.byStatus[record.status] = (summary.byStatus[record.status] || 0) + 1;
      if (record.wouldChange) {
        summary.wouldChange += 1;
      }
      return summary;
    },
    { total: 0, wouldChange: 0, byAction: {}, byStatus: {} },
  );
}

/**
 * 用临时链接 + rename 原子创建或更新链接，避免中间态。
 */
export async function applyPlan(records) {
  for (const record of records) {
    if (record.status !== "planned" || !["create_link", "replace_link"].includes(record.action)) {
      continue;
    }

    await replaceWithSymlink(record.sourcePath, record.targetPath, {
      replaceExisting: record.action === "replace_link",
    });
    record.status = "applied";
    record.reason = record.action === "replace_link" ? "replaced_legacy_active_root_link" : "created_symlink";
    record.wouldChange = false;
    record.targetExists = true;
    record.targetType = "symlink";
    record.targetIsSymlink = true;
    record.targetLinkRaw = record.sourcePath;
    record.targetLinkResolved = record.sourcePath;
    continue;
  }

  for (const record of records) {
    if (record.status === "orphan_link" && record.action === "remove_orphan_link") {
      await fs.unlink(record.targetPath);
      record.status = "applied";
      record.reason = "removed_dangling_symlink";
      record.wouldChange = false;
    }
  }
}

/**
 * 通过临时路径原子落链接，避免在 apply 期间暴露半成品。
 */
async function replaceWithSymlink(sourcePath, targetPath, options = {}) {
  const tempPath = `${targetPath}.tmp-${process.pid}`;
  await fs.symlink(sourcePath, tempPath, linkTypeForPlatform());
  if (options.replaceExisting) {
    await fs.unlink(targetPath);
  }
  await fs.rename(tempPath, targetPath);
}

/**
 * 为删除操作生成审计记录。
 */
export async function buildRemovePlan(options) {
  const availableSkills = await listSourceSkills(options.sourceRoot);
  const skills = resolveSelectedSkills(options.skills, availableSkills);
  const tools = resolveTools(options.tools, options.home, options.config);
  const records = [];

  for (const tool of tools) {
    if (tool.invalid) {
      records.push({
        scannedAt: new Date().toISOString(),
        tool: tool.name,
        skill: null,
        targetPath: null,
        action: "skip",
        status: "invalid_tool",
        reason: "tool_not_in_whitelist",
        wouldChange: false,
      });
      continue;
    }

    for (const skill of skills) {
      const sourcePath = path.join(options.sourceRoot, skill);
      const skillName = path.basename(skill);
      const targetPath = path.join(tool.root, skillName);

      if (tool.name === "hermes") {
        records.push({
          scannedAt: new Date().toISOString(),
          tool: tool.name,
          skill,
          sourcePath,
          targetPath,
          action: "skip",
          status: "hermes_managed",
          reason: "hermes_uses_external_dirs_use_config_yaml",
          wouldChange: false,
        });
        continue;
      }

      try {
        const targetStat = await fs.lstat(targetPath);

        if (targetStat.isSymbolicLink()) {
          const targetLinkRaw = await fs.readlink(targetPath);
          const targetLinkResolved = path.resolve(path.dirname(targetPath), targetLinkRaw);

          if (targetLinkResolved === sourcePath) {
            records.push({
              scannedAt: new Date().toISOString(),
              tool: tool.name,
              skill,
              sourcePath,
              targetPath,
              action: "remove_link",
              status: "planned",
              reason: "symlink_points_to_source",
              wouldChange: true,
              targetIsSymlink: true,
              targetLinkResolved,
            });
          } else {
            records.push({
              scannedAt: new Date().toISOString(),
              tool: tool.name,
              skill,
              sourcePath,
              targetPath,
              action: "skip",
              status: "external_symlink_conflict",
              reason: "symlink_points_elsewhere",
              wouldChange: false,
              targetIsSymlink: true,
              targetLinkResolved,
            });
          }
        } else {
          records.push({
            scannedAt: new Date().toISOString(),
            tool: tool.name,
            skill,
            sourcePath,
            targetPath,
            action: "skip",
            status: "real_path_conflict",
            reason: targetStat.isDirectory() ? "real_directory_exists" : "real_file_exists",
            wouldChange: false,
            targetIsSymlink: false,
          });
        }
      } catch {
        records.push({
          scannedAt: new Date().toISOString(),
          tool: tool.name,
          skill,
          sourcePath,
          targetPath,
          action: "noop",
          status: "not_found",
          reason: "target_does_not_exist",
          wouldChange: false,
        });
      }
    }
  }

  return {
    sourceRoot: options.sourceRoot,
    home: options.home,
    tools: tools.filter((item) => !item.invalid),
    summary: summarizeRemove(records),
    records,
  };
}

function summarizeRemove(records) {
  return records.reduce(
    (summary, record) => {
      summary.total += 1;
      summary.byAction[record.action] = (summary.byAction[record.action] || 0) + 1;
      summary.byStatus[record.status] = (summary.byStatus[record.status] || 0) + 1;
      if (record.wouldChange) {
        summary.wouldChange += 1;
      }
      return summary;
    },
    { total: 0, wouldChange: 0, byAction: {}, byStatus: {} },
  );
}

/**
 * 执行删除软链接。
 */
export async function applyRemovePlan(records) {
  for (const record of records) {
    if (record.status !== "planned" || record.action !== "remove_link") {
      continue;
    }

    await fs.unlink(record.targetPath);
    record.status = "removed";
    record.reason = "symlink_deleted";
    record.wouldChange = false;
  }
}
