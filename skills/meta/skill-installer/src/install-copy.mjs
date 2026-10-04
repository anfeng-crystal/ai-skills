import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

const EXCLUDED_DIRS = new Set([".git", "node_modules", "dist", ".cache", "tmp", "temp"]);
const EXCLUDED_FILES = new Set([".DS_Store"]);

// This is a bounded undo of confirmed creations, not a filesystem transaction.
// Unknown children and paths whose identities changed are always left in place.
export async function copyInstallSource(sourceDir, targetDir) {
  const owned = [];
  let phase = "parent_create";
  let targetCreated = false;
  try {
    await fs.mkdir(path.dirname(targetDir), { recursive: true });
    phase = "target_create";
    targetCreated = null;
    await fs.mkdir(targetDir);
    targetCreated = true;
    phase = "target_inspect";
    owned.push(await inspectCreated(targetDir));
    phase = "source_copy";
    await copyContents(sourceDir, targetDir, owned);
    return { ok: true };
  } catch (error) {
    const conflict = phase === "target_create" && error.code === "EEXIST";
    if (conflict) targetCreated = false;
    const cleanup = await cleanCreated(owned, targetDir);
    let targetExists = null;
    try { targetExists = Boolean(await statOrMissing(targetDir)); }
    catch (inspectionError) { cleanup.errors.push(failure("target_verification", inspectionError, ".")); }
    if (cleanup.errors.length) cleanup.status = "incomplete";
    return {
      ok: false,
      status: conflict ? "target_exists" : "install_incomplete",
      reason: conflict ? "target_appeared_before_install" : "source_install_not_completed",
      applied: false,
      sourceInstalled: false,
      synced: false,
      targetCreated,
      targetExists,
      installError: failure(phase, error),
      cleanup,
    };
  }
}

async function inspectCreated(target) {
  const stat = await fs.lstat(target);
  return { path: target, stat };
}

async function copyContents(source, target, owned) {
  const entries = await fs.readdir(source, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.isDirectory() && EXCLUDED_DIRS.has(entry.name)) continue;
    if (entry.isFile() && EXCLUDED_FILES.has(entry.name)) continue;
    const sourcePath = path.join(source, entry.name), targetPath = path.join(target, entry.name);
    const stat = await fs.lstat(sourcePath);
    await assertParentsOwned(targetPath, owned);
    if (stat.isDirectory()) {
      await fs.mkdir(targetPath);
      owned.push(await inspectCreated(targetPath));
      await copyContents(sourcePath, targetPath, owned);
    } else if (stat.isFile()) {
      // Never overwrite a file/symlink another writer inserted after planning.
      // A throwing copy may leave a partial file; without confirmed ownership it
      // is deliberately untracked and the parent rmdir will preserve it.
      await fs.copyFile(sourcePath, targetPath, fs.constants.COPYFILE_EXCL);
      owned.push(await inspectCreated(targetPath));
    }
  }
}

function sameIdentity(expected, actual) {
  return actual && expected.dev === actual.dev && expected.ino === actual.ino
    && expected.isDirectory() === actual.isDirectory()
    && expected.isFile() === actual.isFile()
    && expected.isSymbolicLink() === actual.isSymbolicLink();
}

async function assertParentsOwned(target, owned) {
  for (const entry of owned) {
    if (!entry.stat.isDirectory() || (target !== entry.path && !target.startsWith(entry.path + path.sep))) continue;
    if (!sameIdentity(entry.stat, await statOrMissing(entry.path))) {
      throw Object.assign(new Error("安装目标目录归属已改变"), { code: "OWNERSHIP_CHANGED" });
    }
  }
}

async function cleanCreated(owned, targetDir) {
  const cleanup = { attempted: owned.length > 0, status: "not_needed", removed: [], errors: [] };
  for (const entry of [...owned].reverse()) {
    const relativePath = path.relative(targetDir, entry.path) || ".";
    try {
      await assertParentsOwned(entry.path, owned);
      const current = await statOrMissing(entry.path);
      if (!current) continue;
      const unchangedFile = !entry.stat.isFile() || (entry.stat.size === current.size
        && entry.stat.mtimeMs === current.mtimeMs && entry.stat.ctimeMs === current.ctimeMs);
      if (!sameIdentity(entry.stat, current) || !unchangedFile) {
        throw Object.assign(new Error("安装目标归属或内容已改变"), { code: "OWNERSHIP_CHANGED" });
      }
      if (entry.stat.isDirectory()) await fs.rmdir(entry.path);
      else await fs.unlink(entry.path);
      cleanup.removed.push(relativePath);
    } catch (error) {
      cleanup.errors.push(failure("target_cleanup", error, relativePath));
    }
  }
  if (owned.length) cleanup.status = cleanup.errors.length ? "incomplete" : "removed";
  return cleanup;
}

async function statOrMissing(target) {
  try { return await fs.lstat(target); }
  catch (error) { if (error.code === "ENOENT") return null; throw error; }
}

function failure(phase, error, relativePath) {
  const knownCode = error?.code === "OWNERSHIP_CHANGED"
    || (typeof error?.code === "string" && Object.hasOwn(os.constants.errno, error.code));
  return {
    phase, code: knownCode ? error.code : null,
    message: phase === "target_cleanup" ? "本次创建对象清理未确认完成"
      : phase === "target_verification" ? "安装目标存在状态无法确认" : "源目录安装未完成",
    ...(relativePath === undefined ? {} : { relativePath }),
  };
}
