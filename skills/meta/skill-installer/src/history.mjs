/**
 * 版本历史：记录和查询操作历史
 */

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const HISTORY_DIR = path.join(os.homedir(), ".skill-installer");
const HISTORY_FILE = path.join(HISTORY_DIR, "history.jsonl");

/**
 * 确保历史目录存在
 */
async function ensureHistoryDir() {
  try {
    await fs.mkdir(HISTORY_DIR, { recursive: true });
  } catch {
    // 目录已存在
  }
}

/**
 * 追加历史记录
 */
export async function appendHistory(record) {
  await ensureHistoryDir();

  const entry = {
    timestamp: new Date().toISOString(),
    ...record,
  };

  const line = JSON.stringify(entry) + "\n";
  await fs.appendFile(HISTORY_FILE, line, "utf8");

  return entry;
}

/**
 * 读取所有历史记录
 */
export async function readHistory() {
  let content;
  try {
    content = await fs.readFile(HISTORY_FILE, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }

  const records = [];
  for (const [index, line] of content.split("\n").entries()) {
    if (!line.trim()) continue;
    let record;
    try {
      record = JSON.parse(line);
    } catch {
      throw invalidHistory("INVALID_HISTORY_JSON", index + 1);
    }
    // Appended entries are objects. Do not silently discard corrupt lines or
    // let non-record values appear in successful queries or cleanup rewrites.
    if (record === null || typeof record !== "object" || Array.isArray(record)) {
      throw invalidHistory("INVALID_HISTORY_RECORD", index + 1);
    }
    records.push(record);
  }
  return records;
}

function invalidHistory(code, lineNumber) {
  // Only a fixed code and line number enter the error; never expose raw JSON.
  const error = new Error(`${code}: 历史记录格式无效（第 ${lineNumber} 行）`);
  error.code = code;
  error.lineNumber = lineNumber;
  return error;
}

/**
 * 查询历史记录
 */
export async function queryHistory(options = {}) {
  const { skill, last = 10, action } = options;

  let records = await readHistory();

  // 按 skill 过滤
  if (skill) {
    records = records.filter(r => r.skill === skill);
  }

  // 按 action 过滤
  if (action) {
    records = records.filter(r => r.action === action);
  }

  // 按时间倒序
  records.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

  // 限制数量
  if (last > 0) {
    records = records.slice(0, last);
  }

  return {
    total: records.length,
    history: records,
  };
}

/**
 * 获取指定 skill 的最后一次同步记录
 */
export async function getLastSyncRecord(skill) {
  const records = await readHistory();
  const filtered = records
    .filter(r => r.skill === skill && r.action === "update")
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

  return filtered[0] || null;
}

/**
 * 清理旧历史记录（保留最近 N 条）
 */
export async function cleanupHistory(keepLast = 1000) {
  const records = await readHistory();

  if (records.length <= keepLast) {
    return { removed: 0 };
  }

  // 按时间倒序排序
  records.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

  // 保留最近的记录
  const toKeep = records.slice(0, keepLast);

  // 重写文件
  await ensureHistoryDir();
  const content = toKeep.map(r => JSON.stringify(r)).join("\n") + "\n";
  await fs.writeFile(HISTORY_FILE, content, "utf8");

  return { removed: records.length - keepLast };
}
