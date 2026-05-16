/**
 * 更新执行：下载、对比、更新 skill
 */

import fs from "node:fs/promises";
import path from "node:path";
import { readMeta, updateUpstreamHash } from "./meta.mjs";
import { getUpstreamCommit, fetchSkillMdHash } from "./update-checker.mjs";
import { buildPlan, applyPlan } from "./sync-links.mjs";
import { appendHistory } from "./history.mjs";

/**
 * 下载上游 SKILL.md 内容
 */
async function fetchUpstreamSkillMd(repoUrl, skillPath, branch = "main") {
  const rawUrl = repoUrl
    .replace("github.com", "raw.githubusercontent.com")
    + `/${branch}/${skillPath}/SKILL.md`;

  try {
    const response = await fetch(rawUrl);
    if (!response.ok) return null;
    return await response.text();
  } catch {
    return null;
  }
}

/**
 * 对比本地和上游的 SKILL.md
 */
export async function diffSkill(sourceRoot, skill) {
  const skillDir = path.join(sourceRoot, skill);
  const meta = await readMeta(skillDir);

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
  const upstreamContent = await fetchUpstreamSkillMd(source.url, source.path || skill, source.branch);
  if (!upstreamContent) {
    return {
      skill,
      found: true,
      status: "fetch_failed",
      reason: "无法获取上游内容",
    };
  }

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
  const upstreamHash = await fetchSkillMdHash(source.url, source.path || skill, source.branch);
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
  const meta = await readMeta(skillDir);

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
  const upstreamContent = await fetchUpstreamSkillMd(source.url, source.path || skill, source.branch);
  if (!upstreamContent) {
    return {
      skill,
      status: "failed",
      reason: "无法获取上游内容",
    };
  }

  // 获取上游 hash
  const upstreamHash = await fetchSkillMdHash(source.url, source.path || skill, source.branch);

  if (dryRun) {
    return {
      skill,
      status: "would_update",
      source: source.url,
      upstreamHash,
      dryRun: true,
    };
  }

  // 备份本地内容
  const localPath = path.join(skillDir, "SKILL.md");
  let localContent;
  try {
    localContent = await fs.readFile(localPath, "utf8");
  } catch {
    localContent = "";
  }

  // 写入新内容
  await fs.writeFile(localPath, upstreamContent, "utf8");

  // 更新 meta
  await updateUpstreamHash(skillDir, upstreamHash);

  // 记录历史
  await appendHistory({
    action: "update",
    skill,
    fromHash: meta.lastUpstreamHash,
    toHash: upstreamHash,
    source: source.url,
    synced: false,
  });

  // 如果需要同步
  let syncedTools = [];
  if (sync) {
    const plan = await buildPlan({
      sourceRoot,
      home: process.env.AI_HOST_HOME || process.env.HOME,
      skills: [skill],
      tools: [],
    });
    await applyPlan(plan.records);
    syncedTools = plan.records
      .filter(r => r.status === "applied" || r.status === "already_linked")
      .map(r => r.tool);

    // 更新历史记录
    await appendHistory({
      action: "sync",
      skill,
      synced: true,
      syncedTools,
    });
  }

  return {
    skill,
    status: "updated",
    source: source.url,
    fromHash: meta.lastUpstreamHash,
    toHash: upstreamHash,
    synced: sync,
    syncedTools,
  };
}

/**
 * 批量更新所有可更新的 skill
 */
export async function updateAll(sourceRoot, options = {}) {
  const { dryRun = false, sync = false } = options;

  // 先检查哪些可以更新
  const { checkAllUpdates } = await import("./update-checker.mjs");
  const checkResult = await checkAllUpdates(sourceRoot);

  const updatable = Object.entries(checkResult.skills)
    .filter(([, result]) => result.status === "updatable")
    .map(([name]) => name);

  if (updatable.length === 0) {
    return {
      status: "nothing_to_update",
      summary: checkResult.summary,
    };
  }

  if (dryRun) {
    return {
      status: "would_update",
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
    const result = await updateSkill(sourceRoot, skill, { sync });
    results.push(result);
  }

  return {
    status: "updated",
    results,
    summary: {
      total: updatable.length,
      updated: results.filter(r => r.status === "updated").length,
      failed: results.filter(r => r.status === "failed").length,
    },
  };
}
