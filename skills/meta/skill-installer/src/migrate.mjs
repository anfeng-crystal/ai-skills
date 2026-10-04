import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { resolveCategory } from "./install.mjs";
import { buildPlan, applyPlan } from "./sync-links.mjs";

export async function migrateSkills(options) {
  const sourceRoot = options.sourceRoot;
  const migrations = [];

  // 扫描 sourceRoot 一级子目录，找出未分类的根级 skill。
  const entries = await fs.readdir(sourceRoot, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name === "skills" || entry.name.startsWith(".")) continue;
    const skillMdPath = path.join(sourceRoot, entry.name, "SKILL.md");
    try {
      await fs.access(skillMdPath);
    } catch {
      continue;
    }

    // 读取 frontmatter
    const content = await fs.readFile(skillMdPath, "utf8");
    const frontmatter = parseFrontmatter(content);
    const category = await resolveCategory("auto", frontmatter, sourceRoot);
    const skillName = entry.name;
    const targetRelativePath = path.posix.join(category, skillName);
    const targetPath = path.join(sourceRoot, ...targetRelativePath.split("/"));

    let targetExists = false;
    try {
      await fs.access(targetPath);
      targetExists = true;
    } catch {}

    migrations.push({
      skillName,
      category,
      sourcePath: path.join(sourceRoot, entry.name),
      targetRelativePath,
      targetPath,
      targetExists,
      status: targetExists ? "target_exists" : "planned",
      reason: targetExists ? "target_directory_exists" : "ready_to_migrate",
    });
  }

  const result = {
    sourceRoot,
    home: options.home,
    command: "migrate",
    applied: false,
    ok: migrations.every((m) => !m.targetExists),
    count: migrations.length,
    planned: migrations.filter((m) => m.status === "planned").length,
    blocked: migrations.filter((m) => m.status === "target_exists").length,
    migrations,
  };

  if (options.apply && result.ok && migrations.length > 0) {
    for (const migration of migrations) {
      if (migration.status !== "planned") continue;
      let phase = "mkdir";
      try {
        await fs.mkdir(path.dirname(migration.targetPath), { recursive: true });
        phase = "rename";
        await fs.rename(migration.sourcePath, migration.targetPath);
        migration.status = "migrated";
        migration.reason = "moved_to_category";
      } catch (error) {
        migration.status = "failed";
        migration.reason = phase === "mkdir" ? "directory_creation_failed" : "directory_move_failed";
        const code = systemErrorCode(error);
        result.migrationError = {
          phase, code, message: "源目录迁移未确认完成",
          skillName: migration.skillName, sourcePath: migration.sourcePath, targetPath: migration.targetPath,
        };
        // Keep completed moves and their host sync; later entries remain unattempted plans.
        break;
      }
    }
    result.applied = migrations.some((migration) => migration.status === "migrated");

    // Only migrated, reviewed skills participate; [] would mean a full sync.
    const skills = migrations.filter((m) => m.status === "migrated" && m.category !== "incoming")
      .map((m) => m.targetRelativePath);
    result.syncPlan = null;
    result.syncVerification = null;
    result.syncError = null;
    let syncComplete = true;
    if (skills.length > 0) {
      const syncOptions = { ...options, skills };
      try {
        result.syncPlan = await buildPlan(syncOptions);
        await applyPlan(result.syncPlan.records);
        result.syncVerification = await buildPlan(syncOptions);
      } catch (error) {
        result.syncError = { code: systemErrorCode(error), message: "宿主链接同步未确认完成" };
      }
      syncComplete = !result.syncError && result.syncVerification.records.every((record) =>
        ["already_linked", "managed_via_external_dir", "optional_host_unavailable"].includes(record.status));
    }
    result.ok = !result.migrationError && syncComplete;
    result.status = result.migrationError ? "migration_incomplete"
      : result.ok ? "migrated" : "migrated_sync_incomplete";
    result.synced = skills.length > 0 && syncComplete;
  }

  return result;
}

function systemErrorCode(error) {
  return typeof error?.code === "string" && Object.hasOwn(os.constants.errno, error.code)
    ? error.code : null;
}

function parseFrontmatter(content) {
  if (!content.startsWith("---")) return {};
  const end = content.indexOf("\n---", 3);
  if (end === -1) return {};
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
    return trimmed.slice(1, -1).split(",").map((item) => normalizeScalar(item)).filter(Boolean);
  }
  return normalizeScalar(trimmed);
}

function normalizeScalar(value) {
  return String(value).trim().replace(/^['"]|['"]$/g, "");
}
