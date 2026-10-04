/**
 * 更新检测：检查 skill 是否有上游更新
 */

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { readMeta, updateLastChecked } from "./meta.mjs";
import { listSourceSkills } from "./sync-links.mjs";

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
 * 检查单个 skill 的更新
 */
export async function checkSkillUpdate(skillDir, { dryRun = false } = {}) {
  // A missing source record is a normal skip only for a usable Skill entry.
  try {
    if (!(await fs.stat(path.join(skillDir, "SKILL.md"))).isFile()) {
      return { status: "check_failed", reason: "Skill 入口 SKILL.md 不是普通文件", code: null };
    }
  } catch (error) {
    const code = typeof error?.code === "string" && Object.hasOwn(os.constants.errno, error.code)
      ? error.code : null;
    return { status: "check_failed", reason: "无法确认 Skill 入口 SKILL.md", code };
  }
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
    // 远端分支只证明上游版本，不能替代所安装内容的版本证据。
    // 保留未知基线；显式 update 成功后由更新器写入实际下载的 commit。
    if (!localHash) {
      return {
        status: "baseline_unknown",
        reason: "未记录已安装版本；先用 diff 核对内容，再按授权显式 update 建立版本基线",
        source: source.url,
        upstreamHash,
      };
    }
    const isUpdatable = localHash !== upstreamHash;

    // 更新检查时间
    if (!dryRun) await updateLastChecked(skillDir);

    if (isUpdatable) {
      return {
        status: "updatable",
        source: source.url,
        localHash,
        upstreamHash,
      };
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
export async function checkAllUpdates(sourceRoot, skills = [], options = {}) {
  const skillDirs = [];
  const results = {};

  if (skills.length > 0) {
    // 检查指定的 skill
    for (const skill of skills) {
      const skillDir = path.join(sourceRoot, skill);
      try {
        const stat = await fs.stat(skillDir);
        if (stat.isDirectory()) {
          skillDirs.push({ name: skill, dir: skillDir });
        } else {
          results[skill] = { status: "missing_skill", reason: "skill_path_not_directory" };
        }
      } catch (error) {
        results[skill] = { status: "missing_skill", reason: error.code || "skill_unavailable" };
      }
    }
  } else {
    // 复用分发入口的发现规则，覆盖分类路径并保持 incoming 的默认隔离。
    for (const name of await listSourceSkills(sourceRoot)) {
      skillDirs.push({ name, dir: path.join(sourceRoot, name) });
    }
  }

  // 逐个检查所有 skill
  for (const { name, dir } of skillDirs) {
    try {
      results[name] = await checkSkillUpdate(dir, options);
    } catch (error) {
      // A metadata I/O failure belongs to this item; preserve later independent checks.
      results[name] = {
        status: "check_failed",
        reason: "更新检查未完成",
        code: error.code || null,
      };
    }
  }

  // 统计
  const summary = {
    total: Object.keys(results).length,
    updatable: 0,
    upToDate: 0,
    noSource: 0,
    local: 0,
    failed: 0,
  };

  for (const result of Object.values(results)) {
    if (result.status === "updatable") summary.updatable++;
    else if (result.status === "up_to_date") summary.upToDate++;
    else if (result.status === "no_source") summary.noSource++;
    else if (result.status === "local") summary.local++;
    else summary.failed++;
  }

  return {
    ok: summary.failed === 0,
    summary,
    skills: results,
  };
}
