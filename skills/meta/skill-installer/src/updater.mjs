/**
 * 更新执行：下载、对比、更新 skill
 */

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { MetadataReadError, readMeta, updateUpstreamHash } from "./meta.mjs";
import { getUpstreamCommit } from "./update-checker.mjs";
import { buildPlan, applyPlan } from "./sync-links.mjs";
import { appendHistory } from "./history.mjs";

/**
 * 固定上游 commit 后下载 SKILL.md，保证版本记录与内容属于同一快照。
 */
async function fetchUpstreamSkill(repoUrl, skillPath, branch = "main") {
  const hash = await getUpstreamCommit(repoUrl, branch);
  if (!hash) return null;

  const rawUrl = repoUrl
    .replace("github.com", "raw.githubusercontent.com")
    + `/${hash}/${skillPath}/SKILL.md`;

  try {
    const response = await fetch(rawUrl);
    if (!response.ok) return null;
    const content = await response.text();
    return content ? { content, hash } : null;
  } catch {
    return null;
  }
}

/**
 * 对比本地和上游的 SKILL.md
 */
export async function diffSkill(sourceRoot, skill) {
  const skillDir = path.join(sourceRoot, skill);
  const targetFailure = await validateUpdateTarget(skillDir, skill);
  if (targetFailure) return targetFailure;
  let meta;
  try {
    meta = await readMeta(skillDir);
  } catch (error) {
    return metadataReadFailure(skill, error);
  }

  if (!meta || !meta.source) {
    return {
      skill,
      found: true,
      status: "no_source",
      reason: "未记录来源仓库",
    };
  }

  const { source } = meta;

  if (source.type !== "git") {
    return {
      skill,
      found: true,
      status: "local_source",
      reason: "本地源，无需对比",
    };
  }

  // 获取上游内容
  const upstream = await fetchUpstreamSkill(source.url, source.path || skill, source.branch);
  if (!upstream) {
    return {
      skill,
      found: true,
      status: "fetch_failed",
      reason: "无法获取上游内容",
    };
  }

  const { content: upstreamContent, hash: upstreamHash } = upstream;

  // 读取本地内容
  let localContent;
  try {
    localContent = await fs.readFile(path.join(skillDir, "SKILL.md"), "utf8");
  } catch {
    return {
      skill,
      found: true,
      status: "local_missing",
      reason: "本地 SKILL.md 不存在",
    };
  }

  // 对比
  const localHash = meta.lastUpstreamHash;

  if (localContent === upstreamContent) {
    return {
      skill,
      found: true,
      status: "up_to_date",
      source: source.url,
      hash: upstreamHash,
    };
  }

  // 生成简单 diff
  const diff = generateSimpleDiff(localContent, upstreamContent);

  return {
    skill,
    found: true,
    status: "updatable",
    source: source.url,
    localHash,
    upstreamHash,
    diff,
  };
}

/**
 * 生成简单的文本对比
 */
function generateSimpleDiff(local, upstream) {
  const localLines = local.split("\n");
  const upstreamLines = upstream.split("\n");

  const changes = [];
  const maxLen = Math.max(localLines.length, upstreamLines.length);

  for (let i = 0; i < maxLen; i++) {
    const localLine = localLines[i] || "";
    const upstreamLine = upstreamLines[i] || "";

    if (localLine !== upstreamLine) {
      if (localLine && !upstreamLine) {
        changes.push(`- ${localLine}`);
      } else if (!localLine && upstreamLine) {
        changes.push(`+ ${upstreamLine}`);
      } else {
        changes.push(`- ${localLine}`);
        changes.push(`+ ${upstreamLine}`);
      }
    }
  }

  return changes.slice(0, 50).join("\n") + (changes.length > 50 ? "\n..." : "");
}

/**
 * 执行更新单个 skill
 */
export async function updateSkill(sourceRoot, skill, options = {}) {
  const { dryRun = false, sync = false } = options;
  const skillDir = path.join(sourceRoot, skill);
  const targetFailure = await validateUpdateTarget(skillDir, skill);
  if (targetFailure) return targetFailure;
  let meta;
  try {
    meta = await readMeta(skillDir);
  } catch (error) {
    return metadataReadFailure(skill, error);
  }

  if (!meta || !meta.source) {
    return {
      skill,
      status: "skipped",
      reason: "未记录来源仓库",
    };
  }

  const { source } = meta;

  if (source.type !== "git") {
    return {
      skill,
      status: "skipped",
      reason: "本地源，无需更新",
    };
  }

  // 获取上游内容
  const upstream = await fetchUpstreamSkill(source.url, source.path || skill, source.branch);
  if (!upstream) {
    return {
      skill,
      status: "failed",
      reason: "无法获取上游内容",
    };
  }

  const { content: upstreamContent, hash: upstreamHash } = upstream;

  if (dryRun) {
    return {
      skill,
      status: "would_update",
      source: source.url,
      upstreamHash,
      dryRun: true,
    };
  }

  const result = {
    skill, ok: false, status: "update_incomplete",
    // false: not attempted; null: attempted but not confirmed; true: completed.
    sourceUpdated: false, metadataUpdated: false,
    updateHistoryRecorded: false, syncHistoryRecorded: false,
    source: source.url,
    fromHash: meta.lastUpstreamHash,
    toHash: upstreamHash,
    syncAttempted: false, synced: false, syncedTools: [],
    syncPlan: null, syncVerification: null, syncError: null,
  };
  let phase = "source_write";
  try {
    // A rejected write may already have changed the file; do not claim it stayed intact.
    result.sourceUpdated = null;
    await fs.writeFile(path.join(skillDir, "SKILL.md"), upstreamContent, "utf8");
    result.sourceUpdated = true;

    phase = "metadata_write";
    result.metadataUpdated = null;
    const updatedMeta = await updateUpstreamHash(skillDir, upstreamHash);
    if (!updatedMeta) {
      result.metadataUpdated = false;
      return { ...result, updateError: { phase, code: "METADATA_UNAVAILABLE", message: "更新元数据不可读取，未写入版本基线" } };
    }
    result.metadataUpdated = true;

    phase = "update_history";
    result.updateHistoryRecorded = null;
    await appendHistory({
      action: "update", skill,
      fromHash: meta.lastUpstreamHash, toHash: upstreamHash,
      source: source.url, synced: false,
    });
    result.updateHistoryRecorded = true;
  } catch (error) {
    if (phase === "metadata_write" && error instanceof MetadataReadError) {
      // The second read failed before writeMeta was called; preserve the established
      // unavailable-metadata contract and do not imply an attempted metadata write.
      result.metadataUpdated = false;
      return { ...result, updateError: { phase, code: "METADATA_UNAVAILABLE", message: "更新元数据不可读取，未写入版本基线" } };
    }
    return { ...result, updateError: updateFailure(phase, error) };
  }

  // 如果需要同步
  let syncPlan = null;
  let syncVerification = null;
  let syncError = null;
  if (sync) {
    result.syncAttempted = true;
    const syncOptions = {
      sourceRoot,
      home: options.home || process.env.AI_HOST_HOME || os.homedir(),
      skills: [skill],
      tools: options.tools || [],
      config: options.config,
    };
    try {
      syncPlan = await buildPlan(syncOptions);
      await applyPlan(syncPlan.records);
    } catch (error) {
      syncError = updateFailure("host_sync", error);
    }
    // 即使 apply 部分失败，也重新检查已成功的独立目标，避免把计划当作最终状态。
    try {
      syncVerification = await buildPlan(syncOptions);
    } catch (error) {
      syncError ||= updateFailure("host_verification", error);
    }
  }

  const syncComplete = !sync || (!syncError && syncVerification?.records.every(
    (record) => ["already_linked", "managed_via_external_dir", "optional_host_unavailable"].includes(record.status),
  ));
  const syncedTools = (syncVerification?.records || [])
    .filter(r => ["already_linked", "managed_via_external_dir"].includes(r.status))
    .map(r => r.tool);
  const status = syncComplete ? "updated" : "updated_sync_incomplete";

  Object.assign(result, {
    ok: syncComplete, status, synced: sync && syncComplete,
    syncedTools, syncPlan, syncVerification, syncError,
  });
  if (sync) {
    result.syncHistoryRecorded = null;
    try {
      await appendHistory({ action: "sync", skill, status, synced: syncComplete, syncedTools, syncError });
      result.syncHistoryRecorded = true;
    } catch (error) {
      return { ...result, ok: false, status: "update_incomplete", updateError: updateFailure("sync_history", error) };
    }
  }

  return result;
}

// Missing metadata is a normal skip only after a real Skill target is established.
async function validateUpdateTarget(skillDir, skill) {
  const invalid = (reason, code = null, status = "invalid_source") => ({
    skill, ok: false, found: false, status, reason, code,
  });
  let phase = "directory";
  try {
    if (!(await fs.stat(skillDir)).isDirectory()) {
      return invalid("Skill 路径不是目录");
    }
    phase = "entry";
    if (!(await fs.stat(path.join(skillDir, "SKILL.md"))).isFile()) {
      return invalid("Skill 入口 SKILL.md 不是普通文件");
    }
    return null;
  } catch (error) {
    const code = typeof error?.code === "string" && Object.hasOwn(os.constants.errno, error.code)
      ? error.code : null;
    if (phase === "directory" && code === "ENOENT") {
      return invalid("源目录中未找到 Skill", code, "missing_skill");
    }
    return invalid(phase === "directory" ? "无法确认 Skill 目录" : "无法确认 Skill 入口 SKILL.md", code);
  }
}

function metadataReadFailure(skill, error) {
  return {
    skill, ok: false, status: "metadata_read_failed",
    reason: "元数据读取或解析失败，未继续操作",
    code: error instanceof MetadataReadError ? error.code : "METADATA_READ_FAILED",
  };
}

function updateFailure(phase, error) {
  const messages = {
    source_write: "源内容写入未确认完成",
    metadata_write: "元数据写入未确认完成",
    update_history: "更新历史写入未确认完成",
    sync_history: "同步历史写入未确认完成",
    host_sync: "宿主同步执行未完成",
    host_verification: "宿主链接验证未完成",
  };
  // Arbitrary exception messages or custom codes may contain private source content.
  const code = typeof error?.code === "string" && Object.hasOwn(os.constants.errno, error.code) ? error.code : null;
  return {
    phase, code, message: messages[phase],
  };
}

/**
 * 批量更新所有可更新的 skill
 */
export async function updateAll(sourceRoot, options = {}) {
  const { dryRun = false } = options;

  // 先检查哪些可以更新
  const { checkAllUpdates } = await import("./update-checker.mjs");
  const checkResult = await checkAllUpdates(sourceRoot, [], { dryRun });
  const checkErrors = Object.fromEntries(Object.entries(checkResult.skills).filter(([, result]) =>
    !["updatable", "up_to_date", "no_source", "local"].includes(result.status)));

  const updatable = Object.entries(checkResult.skills)
    .filter(([, result]) => result.status === "updatable")
    .map(([name]) => name);

  if (updatable.length === 0) {
    return {
      status: checkResult.ok ? "nothing_to_update" : "check_failed",
      ok: checkResult.ok,
      checkErrors,
      summary: checkResult.summary,
    };
  }

  if (dryRun) {
    return {
      status: "would_update",
      ok: checkResult.ok,
      checkErrors,
      skills: updatable.map(name => ({
        name,
        localHash: checkResult.skills[name].localHash,
        upstreamHash: checkResult.skills[name].upstreamHash,
      })),
      dryRun: true,
    };
  }

  // 执行更新
  const results = [];
  for (const skill of updatable) {
    const result = await updateSkill(sourceRoot, skill, options);
    results.push(result);
  }

  return {
    status: "updated",
    ok: checkResult.ok && results.every((result) => result.status !== "failed" && result.ok !== false),
    checkErrors,
    results,
    summary: {
      total: updatable.length,
      updated: results.filter(r => r.status === "updated").length,
      failed: results.filter(r => r.status === "failed" || r.ok === false).length,
      syncIncomplete: results.filter(r => r.syncAttempted && !r.synced).length,
    },
  };
}
