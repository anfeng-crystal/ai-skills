import assert from "node:assert/strict";
import fs from "node:fs";
import fsPromises from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { collectFiles } from "./scan-files.mjs";

const inspector = process.env.SKILL_INSPECTOR || fileURLToPath(new URL("./inspect-skill.mjs", import.meta.url));

test("detects Python standard-library HTTP clients", (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "skill-vetter-network-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.writeFileSync(
    path.join(root, "SKILL.md"),
    "---\nname: network-demo\ndescription: \"Network demo.\"\n---\n\n# Network Demo\n",
    "utf8",
  );
  fs.writeFileSync(
    path.join(root, "client.py"),
    "from urllib.request import Request, build_opener\nrequest = Request('https://example.invalid')\n",
    "utf8",
  );

  const result = spawnSync(process.execPath, [inspector, "--path", root, "--json"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.recommendation, "review_needed");
  assert.ok(report.findings.some((finding) => finding.category === "network_access"));
  assert.ok(report.networkDbAccess.some((item) => item === "client.py:1"));
});

function fixture(t, frontmatter = "name: demo\ndescription: Demo") {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "skill-vetter-regression-"));
  t.after(() => fs.rmSync(base, { recursive: true, force: true }));
  const root = path.join(base, "skill");
  fs.mkdirSync(root);
  fs.writeFileSync(path.join(root, "SKILL.md"), `---\n${frontmatter}\n---\n`);
  return { base, root };
}

function inspect(root, extra = []) {
  const result = spawnSync(process.execPath, [inspector, "--path", root, "--json", ...extra], { encoding: "utf8" });
  assert.ok([0, 2].includes(result.status), result.stderr);
  return { result, report: JSON.parse(result.stdout) };
}

test("redacts credentials and URLs from excerpts and frontmatter", (t) => {
  const { root } = fixture(t, 'name: demo\ndescription: "API_KEY=FAKE_FRONTMATTER_SENTINEL"');
  fs.writeFileSync(path.join(root, "client.py"), [
    'API_KEY="FAKE_KEY_SENTINEL"',
    'headers = {"Cookie": "session=FAKE_COOKIE_SENTINEL"}',
    'fetch("https://fake-user:FAKE_URL_SENTINEL@private.invalid/private-path")',
  ].join("\n"));
  const { result, report } = inspect(root);
  assert.doesNotMatch(result.stdout + result.stderr, /FAKE_(?:FRONTMATTER|KEY|COOKIE|URL)_SENTINEL|private\.invalid/);
  assert.ok(report.secretHits.includes("client.py:1"));
  assert.ok(report.secretHits.includes("client.py:2"));
  assert.ok(report.networkDbAccess.includes("client.py:3"));
  assert.ok(report.findings.some((finding) => finding.match === "[REDACTED_CREDENTIAL_CONTEXT]"));
});

test("reports internal package symlinks without reading their targets", (t) => {
  const { base, root } = fixture(t);
  fs.writeFileSync(path.join(base, "outside.sh"), "rm -rf /FAKE_EXTERNAL_SENTINEL\n");
  fs.symlinkSync(path.join(base, "outside.sh"), path.join(root, "linked.sh"), "file");
  fs.symlinkSync(path.join(base, "missing"), path.join(root, "broken.sh"), "file");
  fs.symlinkSync(base, path.join(root, "directory"), "dir");
  const { result, report } = inspect(root, ["--strict"]);
  assert.equal(result.status, 2);
  assert.equal(report.recommendation, "review_needed");
  assert.equal(report.findings.filter((finding) => finding.match === "symbolic_link_not_followed").length, 3);
  assert.equal(report.destructiveOps.length, 0);
  assert.doesNotMatch(result.stdout, /FAKE_EXTERNAL_SENTINEL/);
});

test("curl Basic Auth arguments are detected and redacted without losing network evidence", (t) => {
  const { root } = fixture(t);
  fs.writeFileSync(path.join(root, "client.sh"), [
    'curl -u "demo:FAKE_CURL_SPACE" https://example.invalid/resource',
    "curl --user='demo:FAKE_CURL_EQUALS' https://example.invalid/resource",
    'curl -udemo:FAKE_CURL_ATTACHED https://example.invalid/resource',
    'curl --user demo:FAKE_CURL_LONG -u other:FAKE_CURL_SECOND https://example.invalid/resource',
    'curl -u "demo:prefix\\"FAKE_CURL_ESCAPED" https://example.invalid/resource',
    'curl -u "demo:prefix"FAKE_CURL_CONCAT https://example.invalid/resource',
    'curl -u demo:prefix\\ FAKE_CURL_UNQUOTED https://example.invalid/resource',
  ].join("\n"));
  const { result, report } = inspect(root);
  assert.doesNotMatch(result.stdout, /FAKE_CURL_(?:SPACE|EQUALS|ATTACHED|LONG|SECOND|ESCAPED|CONCAT|UNQUOTED)/);
  for (let line = 1; line <= 7; line += 1) {
    assert.ok(report.secretHits.includes(`client.sh:${line}`));
    assert.ok(report.networkDbAccess.includes(`client.sh:${line}`));
  }
  assert.ok(report.findings.some((finding) => finding.match === "[REDACTED_CREDENTIAL_CONTEXT]"));
});

test("still supports a user-selected managed root symlink", (t) => {
  const { base, root } = fixture(t);
  fs.writeFileSync(path.join(root, "script.sh"), "rm -rf /synthetic-fixture\n");
  const alias = path.join(base, "alias");
  fs.symlinkSync(root, alias, "dir");
  const { report } = inspect(alias);
  assert.equal(report.recommendation, "block");
  assert.ok(report.destructiveOps.includes("script.sh:1"));
});

test("an explicit SKILL.md symlink does not expand scanning into its target tree", (t) => {
  const { base, root } = fixture(t);
  const entry = path.join(root, "SKILL.md");
  fs.unlinkSync(entry);
  fs.writeFileSync(path.join(base, "outside.md"), "rm -rf /FAKE_ENTRY_SENTINEL\n");
  fs.symlinkSync(path.join(base, "outside.md"), entry, "file");
  const { result, report } = inspect(entry);
  assert.equal(report.inspectedRoot, fs.realpathSync(root));
  assert.equal(report.recommendation, "review_needed");
  assert.ok(report.findings.some((finding) => finding.match === "symbolic_link_not_followed"));
  assert.doesNotMatch(result.stdout, /FAKE_ENTRY_SENTINEL/);
});

test("unscanned large files and binaries cannot receive allow", (t) => {
  const { root } = fixture(t);
  fs.writeFileSync(path.join(root, "large.sh"), "#".repeat(256 * 1024 + 1));
  fs.writeFileSync(path.join(root, "tool.exe"), Buffer.from([0, 1, 2]));
  const { result, report } = inspect(root, ["--strict"]);
  assert.equal(result.status, 2);
  assert.equal(report.recommendation, "review_needed");
  assert.equal(report.findings.filter((finding) => finding.category === "unscanned_content").length, 2);
  assert.deepEqual(report.binaryArtifacts, ["tool.exe"]);
});

test("entrypoint size limits also apply before frontmatter parsing", (t) => {
  const { root } = fixture(t);
  fs.appendFileSync(path.join(root, "SKILL.md"), "x".repeat(256 * 1024));
  const { report } = inspect(root);
  assert.equal(report.frontmatter.hasFrontmatter, false);
  assert.ok(report.findings.some((finding) => finding.match === "file_exceeds_256_kib"));
});

test("CRLF entrypoints retain valid metadata and allow clean text", (t) => {
  const { root } = fixture(t);
  fs.writeFileSync(path.join(root, "SKILL.md"), "---\r\nname: demo\r\ndescription: Demo\r\n---\r\n");
  const { report } = inspect(root);
  assert.equal(report.frontmatter.name, "demo");
  assert.equal(report.recommendation, "allow");
});

test("excluded package directories are visible gaps and cannot receive allow", (t) => {
  const { root } = fixture(t);
  for (const name of ["dist", "build", "node_modules", ".git"]) {
    fs.mkdirSync(path.join(root, name));
    fs.writeFileSync(path.join(root, name, "hidden.sh"), "rm -rf /synthetic-fixture\n");
  }
  const { result, report } = inspect(root, ["--strict"]);
  assert.equal(result.status, 2);
  assert.equal(report.recommendation, "review_needed");
  assert.equal(report.fileSummary.unscannedDirectories, 4);
  assert.equal(report.findings.filter((finding) => finding.match === "excluded_directory").length, 4);
});

test("invalid UTF-8 and NUL-containing text cannot be counted as scanned", (t) => {
  const { root } = fixture(t);
  fs.writeFileSync(path.join(root, "invalid.md"), Buffer.from([0xff, 0xfe, 0x41]));
  fs.writeFileSync(path.join(root, "utf16.sh"), Buffer.from("rm -rf /synthetic-fixture\n", "utf16le"));
  const { result, report } = inspect(root, ["--strict"]);
  assert.equal(result.status, 2);
  assert.equal(report.recommendation, "review_needed");
  assert.equal(report.fileSummary.textScanned, 1);
  assert.ok(report.findings.some((finding) => finding.match === "invalid_utf8"));
  assert.ok(report.findings.some((finding) => finding.match === "nul_byte_in_text"));
});

test("incomplete bundle entry discovery cannot receive allow", (t) => {
  const { base } = fixture(t);
  const deepRoot = path.join(base, "one", "two", "three", "four", "five", "six", "deep");
  fs.mkdirSync(deepRoot, { recursive: true });
  fs.writeFileSync(path.join(deepRoot, "SKILL.md"), "No frontmatter\n");
  const { result, report } = inspect(base, ["--strict"]);
  assert.equal(result.status, 2);
  assert.equal(report.recommendation, "review_needed");
  assert.ok(report.findings.some((finding) => finding.match === "entry_discovery_depth_limit"));
});

test("credential contexts in paths are redacted in JSON and human summaries", (t) => {
  const { base, root } = fixture(t);
  const privateRoot = path.join(base, "api_key=FAKE_ROOT_SENTINEL");
  fs.renameSync(root, privateRoot);
  fs.writeFileSync(path.join(privateRoot, "password=FAKE_FILE_SENTINEL.sh"), "rm -rf /synthetic-fixture\n");
  const { result, report } = inspect(privateRoot);
  assert.equal(report.recommendation, "block");
  assert.doesNotMatch(result.stdout + result.stderr, /FAKE_(?:ROOT|FILE)_SENTINEL/);
  assert.equal(path.dirname(report.inputPath), base);
  assert.ok(report.inputPath.endsWith("[REDACTED_PATH_SEGMENT]"));
  const summary = spawnSync(process.execPath, [inspector, "--path", privateRoot], { encoding: "utf8" });
  assert.equal(summary.status, 0);
  assert.doesNotMatch(summary.stdout + summary.stderr, /FAKE_(?:ROOT|FILE)_SENTINEL/);
  assert.ok(report.destructiveOps.some((location) => location.endsWith(":1")));
});

test("non-HTTP and protocol-relative URLs are redacted in source excerpts", (t) => {
  const { root } = fixture(t);
  fs.writeFileSync(path.join(root, "client.js"), ["ftp:", "sftp:", "wss:", "mongodb+srv:", "redis:", ""].map(
    (scheme) => `fetch("${scheme}//fake-user:FAKE_SCHEME_SENTINEL@private.invalid/resource")`,
  ).join("\n"));
  const { result, report } = inspect(root);
  assert.doesNotMatch(result.stdout, /FAKE_SCHEME_SENTINEL|private\.invalid/);
  assert.equal(report.networkDbAccess.filter((location) => location.startsWith("client.js:")).length, 6);
});

test("unreadable directories retain partial scan results and a review gap", async (t) => {
  const { root } = fixture(t);
  const denied = path.join(root, "denied");
  fs.mkdirSync(denied);
  const readdir = fsPromises.readdir;
  t.mock.method(fsPromises, "readdir", async (directory, options) => {
    if (directory === denied) throw Object.assign(new Error("Synthetic read denial"), { code: "EACCES" });
    return readdir(directory, options);
  });
  const collection = await collectFiles(root);
  assert.deepEqual(collection.files, [path.join(root, "SKILL.md")]);
  assert.deepEqual(collection.unscanned, [{ filePath: denied, reason: "unreadable_directory:EACCES" }]);
});


for (const value of [undefined, '', '--strict', '--json']) {
  test(`path requires a value before inspection: ${String(value)}`, (t) => {
    const { base } = fixture(t);
    if (value) {
      const dir = path.join(base, value);
      fs.mkdirSync(dir);
      fs.writeFileSync(path.join(dir, 'SKILL.md'), '---\nname: example\ndescription: Example\n---\n');
      fs.writeFileSync(path.join(dir, 'client.py'), 'import urllib.request\n');
    }
    const trace = path.join(base, 'scan.txt');
    const preload = path.join(base, 'trace.mjs');
    fs.writeFileSync(preload, `import fs from 'node:fs';import fsp from 'node:fs/promises';
      const original = fsp.lstat;
      fsp.lstat = async function(...args) { fs.appendFileSync(${JSON.stringify(trace)}, 'scan\\n'); return original.apply(this,args); };`);
    const result = spawnSync(process.execPath, ['--import', preload, inspector, '--path', ...(value === undefined ? [] : [value])],
      { cwd: base, encoding: 'utf8', timeout: 10000 });
    assert.ifError(result.error);
    assert.equal(result.status, 1);
    assert.equal(result.stdout, '');
    assert.match(result.stderr, /--path requires a path value/);
    assert.equal(fs.existsSync(trace), false);
  });
}

for (const [label, dirname, positional] of [
  ['space path', 'with space', false], ['explicit switch-name path', '--strict', false], ['positional input', 'example', true],
]) {
  test(`path control retains strict review: ${label}`, (t) => {
    const { base } = fixture(t);
    const root = path.join(base, dirname);
    fs.mkdirSync(root);
    fs.writeFileSync(path.join(root, 'SKILL.md'), '---\nname: example\ndescription: Example\n---\n');
    fs.writeFileSync(path.join(root, 'client.py'), 'import urllib.request\n');
    const result = spawnSync(process.execPath, [inspector, ...(positional ? [] : ['--path']), `./${dirname}`, '--json', '--strict'],
      { cwd: base, encoding: 'utf8', timeout: 10000 });
    assert.ifError(result.error);
    assert.equal(result.status, 2, result.stderr);
    const report = JSON.parse(result.stdout);
    assert.equal(report.recommendation, 'review_needed');
    assert.ok(report.findings.some((item) => item.category === 'network_access'));
  });
}
