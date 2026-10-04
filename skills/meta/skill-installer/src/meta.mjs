/**
 * 来源追踪：管理 .skill-meta.json
 */

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const META_FILE = ".skill-meta.json";

// Keep unreadable metadata distinct from a legitimately absent source record.
// Never attach raw parser errors or I/O messages: they may contain private data.
export class MetadataReadError extends Error {
  constructor(code) {
    super("元数据读取或解析失败");
    this.name = "MetadataReadError";
    this.code = code;
  }
}

/**
 * 读取 .skill-meta.json
 */
export async function readMeta(skillDir) {
  const metaPath = path.join(skillDir, META_FILE);
  let content;
  try {
    content = await fs.readFile(metaPath, "utf8");
  } catch (error) {
    if (error?.code === "ENOENT") return null;
    const code = typeof error?.code === "string" && Object.hasOwn(os.constants.errno, error.code)
      ? error.code : "METADATA_READ_FAILED";
    throw new MetadataReadError(code);
  }
  try {
    return JSON.parse(content);
  } catch {
    throw new MetadataReadError("INVALID_METADATA_JSON");
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
 * branch 为单个路径段，path 为非空 Skill 目录；不推测带斜杠的分支。
 * 只接受 HTTPS 官方主机且不含凭据，query/fragment 不属于来源路径。
 * 不接受根级 raw SKILL.md：现有更新器会将空目录回退为 skill 名。
 */
export function parseSourceUrl(url) {
  if (typeof url !== "string" || !url) return null;

  // 本地目录中的 github.com 只是路径文本，不是远程主机。
  if (url.startsWith("/") || url.startsWith("./") || url.startsWith("../")) {
    return {
      type: "local",
      url: path.resolve(url),
    };
  }

  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:" || parsed.username || parsed.password || parsed.port) return null;
  if (!["github.com", "raw.githubusercontent.com"].includes(parsed.hostname)) return null;

  const segments = parsed.pathname.replace(/\/$/, "").slice(1).split("/");
  if (segments.length < 2 || segments.some((segment) => !segment)) return null;
  const [owner, repo, ...rest] = segments;
  // 解码后仍须是单个路径段；尤其不能猜测 %2F 对应分支还是目录。
  let decoded;
  try {
    decoded = segments.map((segment) => decodeURIComponent(segment));
  } catch {
    return null;
  }
  if (decoded.some((segment) => /[\\/\u0000-\u001f\u007f]/.test(segment))) return null;

  let branch = "main";
  let skillPath = null;
  if (parsed.hostname === "github.com") {
    if (rest.length > 0) {
      if (rest[0] !== "tree" || rest.length < 3) return null;
      branch = decoded[3];
      skillPath = rest.slice(2).join("/");
    }
  } else {
    if (rest.length < 3 || rest.at(-1) !== "SKILL.md") return null;
    branch = decoded[2];
    skillPath = rest.slice(1, -1).join("/");
  }

  return { type: "git", url: `https://github.com/${owner}/${repo}`, path: skillPath, branch };
}

/**
 * 安装时记录来源；git 来源的 upstreamHash 应为所安装内容对应的 commit。
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
 * 记录来源的上游 commit，不使用内容摘要或可变分支名。
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
