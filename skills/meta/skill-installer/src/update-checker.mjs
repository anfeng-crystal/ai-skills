/**
 * 更新检测：检查 skill 是否有上游更新
 */

import fs from "node:fs/promises";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { readMeta, updateLastChecked, updateUpstreamHash } from "./meta.mjs";

const execFileAsync = promisify(execFile);

/**
 * 获取上游最新 commit hash
 * 使用 git ls-remote 获取远程最新 commit
 */
export async function getUpstreamCommit(repoUrl, branch = "main") {
  try {
    const { stdout } = await execFileAsync("git", ["ls-remote", repoUrl, `refs/heads/${branch}`]);
    const hash = stdout.trim().split(/\s+/)[0];
    return hash || null;
  } catch {
    return null;
  }
}

/**
 * 从 GitHub raw URL 获取 SKILL.md 的内容 hash
 */
export async function fetchSkillMdHash(repoUrl, skillPath, branch = "main") {
  // 转换为 raw URL
  const rawUrl = repoUrl
    .replace("github.com", "raw.githubusercontent.com")
    + `/${branch}/${skillPath}/SKILL.md`;

  try {
    const response = await fetch(rawUrl);
    if (!response.ok) return null;

    const content = await response.text();
    // 简单 hash：使用内容长度 + 前 100 字符的 hash
    const simpleHash = `${content.length}-${content.slice(0, 100).replace(/\s/g, "")}`;
    return simpleHash;
  } catch {
    return null;
  }
}

/**
 * 检查单个 skill 的更新
 */
export async function checkSkillUpdate(skillDir) {
  const meta = await readMeta(skillDir);
  if (!meta || !meta.source) {
    return {
      status: "no_source",
      reason: "未记录来源仓库",
    };
  }

  const { source } = meta;

  if (source.type === "git") {
    // 获取上游最新 commit
    const upstreamHash = await getUpstreamCommit(source.url, source.branch);

    if (!upstreamHash) {
      return {
        status: "check_failed",
        reason: "无法获取上游信息",
      };
    }

    // 对比 hash
    const localHash = meta.lastUpstreamHash;
    const isUpdatable = localHash && localHash !== upstreamHash;

    // 更新检查时间
    await updateLastChecked(skillDir);

    if (isUpdatable) {
      return {
        status: "updatable",
        source: source.url,
        localHash,
        upstreamHash,
      };
    }

    // 如果没有本地 hash 记录，记录当前上游 hash
    if (!localHash) {
      await updateUpstreamHash(skillDir, upstreamHash);
    }

    return {
      status: "up_to_date",
      source: source.url,
      hash: upstreamHash,
    };
  }

  if (source.type === "local") {
    // 本地路径，检查文件是否存在
    try {
      await fs.stat(path.join(source.url, "SKILL.md"));
      return {
        status: "local",
        source: source.url,
      };
    } catch {
      return {
        status: "source_missing",
        reason: "本地源目录不存在",
      };
    }
  }

  return {
    status: "unknown_source",
    reason: "未知的来源类型",
  };
}

/**
 * 批量检查更新
 */
export async function checkAllUpdates(sourceRoot, skills = []) {
  const skillDirs = [];

  if (skills.length > 0) {
    // 检查指定的 skill
    for (const skill of skills) {
      const skillDir = path.join(sourceRoot, skill);
      try {
        const stat = await fs.stat(skillDir);
        if (stat.isDirectory()) {
          skillDirs.push({ name: skill, dir: skillDir });
        }
      } catch {
        // skill 目录不存在
      }
    }
  } else {
    // 扫描所有 skill
    const entries = await fs.readdir(sourceRoot, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory() || entry.name.startsWith(".")) continue;

      const skillDir = path.join(sourceRoot, entry.name);
      try {
        const skillMd = path.join(skillDir, "SKILL.md");
        await fs.stat(skillMd);
        skillDirs.push({ name: entry.name, dir: skillDir });
      } catch {
        // 没有 SKILL.md，跳过
      }
    }
  }

  // 并行检查所有 skill
  const results = {};
  for (const { name, dir } of skillDirs) {
    results[name] = await checkSkillUpdate(dir);
  }

  // 统计
  const summary = {
    total: skillDirs.length,
    updatable: 0,
    upToDate: 0,
    noSource: 0,
    failed: 0,
  };

  for (const result of Object.values(results)) {
    if (result.status === "updatable") summary.updatable++;
    else if (result.status === "up_to_date") summary.upToDate++;
    else if (result.status === "no_source") summary.noSource++;
    else summary.failed++;
  }

  return {
    summary,
    skills: results,
  };
}
