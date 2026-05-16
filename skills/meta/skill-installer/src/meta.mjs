/**
 * 来源追踪：管理 .skill-meta.json
 */

import fs from "node:fs/promises";
import path from "node:path";

const META_FILE = ".skill-meta.json";

/**
 * 读取 .skill-meta.json
 */
export async function readMeta(skillDir) {
  const metaPath = path.join(skillDir, META_FILE);
  try {
    const content = await fs.readFile(metaPath, "utf8");
    return JSON.parse(content);
  } catch {
    return null;
  }
}

/**
 * 写入 .skill-meta.json
 */
export async function writeMeta(skillDir, meta) {
  const metaPath = path.join(skillDir, META_FILE);
  await fs.writeFile(metaPath, JSON.stringify(meta, null, 2) + "\n", "utf8");
}

/**
 * 从 GitHub URL 提取仓库信息
 * 支持格式：
 * - https://github.com/owner/repo
 * - https://github.com/owner/repo/tree/branch/path
 * - https://raw.githubusercontent.com/owner/repo/branch/path/SKILL.md
 */
export function parseSourceUrl(url) {
  if (!url) return null;

  // GitHub URL 格式
  const githubMatch = url.match(/github\.com\/([^/]+)\/([^/]+)/);
  if (githubMatch) {
    const [, owner, repo] = githubMatch;
    const repoUrl = `https://github.com/${owner}/${repo}`;

    // 提取分支和路径
    const pathMatch = url.match(/\/tree\/([^/]+)\/(.+)/);
    const branch = pathMatch ? pathMatch[1] : "main";
    const skillPath = pathMatch ? pathMatch[2] : null;

    return {
      type: "git",
      url: repoUrl,
      path: skillPath,
      branch,
    };
  }

  // 本地路径
  if (url.startsWith("/") || url.startsWith("./") || url.startsWith("../")) {
    return {
      type: "local",
      url: path.resolve(url),
    };
  }

  return null;
}

/**
 * 安装时自动记录来源
 */
export async function recordSource(skillDir, sourceInfo, upstreamHash = null) {
  const now = new Date().toISOString();
  const meta = await readMeta(skillDir) || {};

  const updated = {
    ...meta,
    source: sourceInfo,
    installedAt: meta.installedAt || now,
    installedBy: "skill-installer",
    lastCheckedAt: now,
  };

  if (upstreamHash) {
    updated.lastUpstreamHash = upstreamHash;
  }

  await writeMeta(skillDir, updated);
  return updated;
}

/**
 * 更新最后检查时间
 */
export async function updateLastChecked(skillDir) {
  const meta = await readMeta(skillDir);
  if (!meta) return null;

  meta.lastCheckedAt = new Date().toISOString();
  await writeMeta(skillDir, meta);
  return meta;
}

/**
 * 更新上游 hash
 */
export async function updateUpstreamHash(skillDir, hash) {
  const meta = await readMeta(skillDir);
  if (!meta) return null;

  meta.lastUpstreamHash = hash;
  meta.lastCheckedAt = new Date().toISOString();
  await writeMeta(skillDir, meta);
  return meta;
}

/**
 * 删除 .skill-meta.json
 */
export async function deleteMeta(skillDir) {
  const metaPath = path.join(skillDir, META_FILE);
  try {
    await fs.unlink(metaPath);
    return true;
  } catch {
    return false;
  }
}
