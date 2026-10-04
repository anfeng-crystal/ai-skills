/** Read-only local Chrome sources; failures travel with successful source results. */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

function failure(source, file, error) {
  // Do not include parser exceptions: recent Node versions can quote source content.
  const code = /^[A-Z0-9_]+$/.test(error?.code || "") ? error.code : "READ_FAILED";
  return { source, path: file, code };
}

function chromeUserDataCandidates() {
  const home = os.homedir();
  switch (process.platform) {
    case "darwin":
      return ["Google/Chrome", "Chromium", "BraveSoftware/Brave-Browser"]
        .map((name) => path.join(home, "Library/Application Support", name));
    case "win32": {
      const local = process.env.LOCALAPPDATA || path.join(home, "AppData/Local");
      return ["Google/Chrome/User Data", "Chromium/User Data", "BraveSoftware/Brave-Browser/User Data"]
        .map((name) => path.join(local, name));
    }
    default:
      return ["google-chrome", "chromium", "BraveSoftware/Brave-Browser"]
        .map((name) => path.join(home, ".config", name));
  }
}

export function resolveProfileDirs(parsed, errors = null, source = "profiles") {
  if (parsed.profileDir) return [path.resolve(parsed.profileDir)];
  const profileDirs = [];
  for (const root of chromeUserDataCandidates()) {
    try {
      for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
        if (entry.isDirectory() && (entry.name === "Default" || /^Profile \d+$/.test(entry.name) || entry.name === "Guest Profile")) {
          profileDirs.push(path.join(root, entry.name));
        }
      }
    } catch (error) {
      // An uninstalled browser is normal; an unreadable installed source is not.
      if (!["ENOENT", "ENOTDIR"].includes(error.code)) errors?.push(failure(source, root, error));
    }
  }
  return [...new Set(profileDirs)];
}

function resolvePaths(parsed, source, filename, explicit, errors) {
  if (explicit) return [path.resolve(explicit)];
  const files = resolveProfileDirs(parsed, errors, source).map((dir) => path.join(dir, filename));
  if (parsed.profileDir) return files;
  return files.filter((file) => {
    try { fs.statSync(file); return true; }
    catch (error) {
      if (!["ENOENT", "ENOTDIR"].includes(error.code)) errors?.push(failure(source, file, error));
      return false;
    }
  });
}

export function resolveBookmarkPaths(parsed, errors = null) {
  return resolvePaths(parsed, "bookmarks", "Bookmarks", parsed.bookmarksPath, errors);
}

export function resolveHistoryPaths(parsed, errors = null) {
  return resolvePaths(parsed, "history", "History", parsed.historyPath, errors);
}

function collectBookmarkNodes(node, profileName, bucket = [], folder = null) {
  if (!node || typeof node !== "object") return bucket;
  if (node.type === "url") {
    bucket.push({ source: "bookmark", title: node.name || "", url: node.url || "",
      addedAt: node.date_added || null, profile: profileName, folder });
    return bucket;
  }
  for (const child of Array.isArray(node.children) ? node.children : []) {
    collectBookmarkNodes(child, profileName, bucket, node.name || folder);
  }
  return bucket;
}

function chromeMicrosToIso(value) {
  const micros = Number(value || 0);
  if (!Number.isFinite(micros) || micros <= 0) return null;
  const date = new Date(micros / 1000 - 11644473600000);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function loadBookmarks(parsed) {
  const result = { items: [], errors: [], successfulSources: 0 };
  for (const file of resolveBookmarkPaths(parsed, result.errors)) {
    try {
      const raw = JSON.parse(fs.readFileSync(file, "utf8"));
      if (!raw || typeof raw !== "object" || !raw.roots || typeof raw.roots !== "object" || Array.isArray(raw.roots)) {
        throw Object.assign(new Error("Invalid Bookmarks roots"), { code: "INVALID_BOOKMARKS" });
      }
      const items = [];
      for (const node of Object.values(raw.roots)) collectBookmarkNodes(node, path.basename(path.dirname(file)), items);
      result.items.push(...items.map((item) => ({ ...item, addedAt: chromeMicrosToIso(item.addedAt) })));
      result.successfulSources += 1;
    } catch (error) {
      if (error instanceof SyntaxError) error.code = "INVALID_JSON";
      result.errors.push(failure("bookmarks", file, error));
    }
  }
  return result;
}

function parseSince(spec) {
  if (!spec) return null;
  if (/^\d+[dhm]$/.test(spec)) {
    const factors = { m: 60_000, h: 3_600_000, d: 86_400_000 };
    return Date.now() - Number(spec.slice(0, -1)) * factors[spec.slice(-1)];
  }
  const timestamp = Date.parse(spec);
  if (Number.isNaN(timestamp)) throw new Error(`Invalid --since value: ${spec}`);
  return timestamp;
}

const historyProgram = String.raw`import datetime, errno, json, os, shutil, sqlite3, sys, tempfile
payload = json.loads(sys.argv[1])
result = {'items': [], 'errors': [], 'successfulSources': 0}
for history_path in payload['paths']:
    conn = None
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix='web-access-history-', suffix='.sqlite3')
        os.close(fd)
        shutil.copy2(history_path, tmp)
        conn = sqlite3.connect(tmp)
        conn.row_factory = sqlite3.Row
        rows = []
        query = 'SELECT url, title, visit_count, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT 5000'
        for row in conn.execute(query):
            last_visit_time = row['last_visit_time'] or 0
            unix_ms = last_visit_time / 1000 - 11644473600000 if last_visit_time else None
            if payload['sinceMs'] and unix_ms and unix_ms < payload['sinceMs']:
                continue
            rows.append({
                'source': 'history', 'profile': os.path.basename(os.path.dirname(history_path)),
                'title': row['title'] or '', 'url': row['url'] or '', 'visitCount': row['visit_count'] or 0,
                'lastVisitedAt': unix_ms,
                'lastVisitedIso': None if unix_ms is None else datetime.datetime.utcfromtimestamp(unix_ms / 1000).isoformat() + 'Z',
            })
        result['items'].extend(rows)
        result['successfulSources'] += 1
    except Exception as error:
        code = errno.errorcode.get(getattr(error, 'errno', None), 'SQLITE_ERROR' if isinstance(error, sqlite3.Error) else 'READ_FAILED')
        result['errors'].append({'source': 'history', 'path': history_path, 'code': code})
    finally:
        if conn is not None:
            conn.close()
        if tmp is not None:
            try:
                os.remove(tmp)
            except OSError:
                pass
print(json.dumps(result, ensure_ascii=False))`;

export function loadHistory(parsed) {
  const output = { items: [], errors: [], successfulSources: 0 };
  const paths = resolveHistoryPaths(parsed, output.errors);
  if (paths.length === 0) return output;
  const sinceMs = parseSince(parsed.since);
  const result = spawnSync("python3", ["-c", historyProgram, JSON.stringify({ paths, sinceMs })], { encoding: "utf8" });
  if (result.status !== 0) {
    output.errors.push({ source: "history", code: result.error?.code || "PYTHON_FAILED" });
    return output;
  }
  let payload;
  try {
    payload = JSON.parse(result.stdout);
    if (!Array.isArray(payload.items) || !Array.isArray(payload.errors) || !Number.isInteger(payload.successfulSources)) throw new Error();
  } catch {
    output.errors.push({ source: "history", code: "INVALID_PYTHON_RESPONSE" });
    return output;
  }
  output.errors.push(...payload.errors);
  output.items = payload.items;
  output.successfulSources = payload.successfulSources;
  output.items.sort(parsed.sort === "visits"
    ? (a, b) => (b.visitCount || 0) - (a.visitCount || 0) || (b.lastVisitedAt || 0) - (a.lastVisitedAt || 0)
    : (a, b) => (b.lastVisitedAt || 0) - (a.lastVisitedAt || 0));
  return output;
}
