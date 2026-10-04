import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const inspector = process.env.SKILL_VETTER_SCRIPT || fileURLToPath(new URL("./inspect-skill.mjs", import.meta.url));
const header = "---\nname: demo\ndescription: Demo\n---\n";

function fixture(t) {
  const base = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "vetter-entry-coverage-")));
  t.after(() => fs.rmSync(base, { recursive: true, force: true }));
  const root = path.join(base, "skill");
  fs.mkdirSync(root);
  fs.writeFileSync(path.join(root, "SKILL.md"), header);
  return { base, root };
}

function inspect(t, root, options = {}) {
  const support = fs.mkdtempSync(path.join(os.tmpdir(), "vetter-entry-fault-"));
  t.after(() => fs.rmSync(support, { recursive: true, force: true }));
  const preload = path.join(support, "preload.mjs");
  const reads = path.join(support, "reads.jsonl");
  fs.writeFileSync(preload, `
import fs from 'node:fs';
import promises from 'node:fs/promises';
import path from 'node:path';
const denied = new Set(${JSON.stringify(options.denied || [])}.map(p => path.resolve(p)));
const unreadable = new Set(${JSON.stringify(options.unreadable || [])}.map(p => path.resolve(p)));
const readDirectory = promises.readdir;
promises.readdir = async (directory, ...args) => {
  if (denied.has(path.resolve(directory))) throw Object.assign(new Error('Synthetic directory denial'), {code:'EACCES'});
  return readDirectory(directory, ...args);
};
const readFile = promises.readFile;
promises.readFile = async (file, ...args) => {
  fs.appendFileSync(${JSON.stringify(reads)}, JSON.stringify(String(file)) + '\\n');
  if (unreadable.has(path.resolve(file))) throw Object.assign(new Error('Synthetic file denial'), {code:'EACCES'});
  return readFile(file, ...args);
};
`);
  const run = spawnSync(process.execPath, ["--import", preload, inspector, "--path", root, "--json", "--strict"], {
    encoding: "utf8", timeout: 5000,
  });
  assert.ok([0, 2].includes(run.status), run.stdout + run.stderr);
  return {
    ...run,
    report: JSON.parse(run.stdout),
    reads: fs.existsSync(reads) ? fs.readFileSync(reads, "utf8").trim().split("\n").filter(Boolean).map(JSON.parse) : [],
  };
}

function assertGap(report, count = 1) {
  assert.equal(report.fileSummary.unscannedDirectories, count);
  assert.ok(report.findings.some(f => f.match === "unreadable_directory:EACCES"));
}

for (const explicitEntry of [false, true]) {
  test(`known ${explicitEntry ? "explicit" : "directory"} entry keeps risk scanning after directory enumeration fails`, (t) => {
    const { root } = fixture(t);
    const entry = path.join(root, "SKILL.md");
    fs.appendFileSync(entry, "rm -rf /synthetic-fixture\n");
    const { status, report, reads } = inspect(t, explicitEntry ? entry : root, { denied: [root] });
    assert.equal(status, 2);
    assert.equal(report.recommendation, "block");
    assert.deepEqual(report.destructiveOps, ["SKILL.md:5"]);
    assert.equal(report.fileSummary.totalFiles, 1);
    assert.equal(report.fileSummary.textScanned, 1);
    assert.equal(reads.filter(p => p === entry).length, 1);
    assertGap(report);
  });
}

test("a readable clean entry is counted while its unreadable directory remains review_needed", (t) => {
  const { root } = fixture(t);
  const { status, report } = inspect(t, root, { denied: [root] });
  assert.equal(status, 2);
  assert.equal(report.recommendation, "review_needed");
  assert.equal(report.frontmatter.name, "demo");
  assert.equal(report.fileSummary.totalFiles, 1);
  assert.equal(report.fileSummary.textScanned, 1);
  assert.equal(report.fileSummary.skippedBinaryOrLarge, 0);
  assertGap(report);
});

test("a known unreadable entry retains its file failure as well as its directory gap", (t) => {
  const { root } = fixture(t);
  const entry = path.join(root, "SKILL.md");
  const { report, reads } = inspect(t, entry, { denied: [root], unreadable: [entry] });
  assert.equal(report.recommendation, "review_needed");
  assert.equal(report.fileSummary.totalFiles, 1);
  assert.equal(report.fileSummary.textScanned, 0);
  assert.equal(report.fileSummary.skippedBinaryOrLarge, 1);
  assert.ok(report.findings.some(f => f.file === "SKILL.md" && f.match === "unreadable_file:EACCES"));
  assert.equal(reads.filter(p => p === entry).length, 1);
  assertGap(report);
});

test("a known oversized entry keeps the size-limit finding when enumeration fails", (t) => {
  const { root } = fixture(t);
  fs.appendFileSync(path.join(root, "SKILL.md"), "x".repeat(256 * 1024));
  const { report } = inspect(t, root, { denied: [root] });
  assert.equal(report.recommendation, "review_needed");
  assert.equal(report.fileSummary.totalFiles, 1);
  assert.equal(report.fileSummary.textScanned, 0);
  assert.equal(report.fileSummary.skippedBinaryOrLarge, 1);
  assert.ok(report.findings.some(f => f.file === "SKILL.md" && f.match === "file_exceeds_256_kib"));
  assertGap(report);
});

test("a known entry symlink is reported without following it when enumeration fails", (t) => {
  const { base, root } = fixture(t);
  const entry = path.join(root, "SKILL.md");
  const outside = path.join(base, "outside.md");
  fs.writeFileSync(outside, header + "rm -rf /FAKE_EXTERNAL_SENTINEL\n");
  fs.unlinkSync(entry);
  fs.symlinkSync(outside, entry, "file");
  const { report, stdout, reads } = inspect(t, entry, { denied: [root] });
  assert.equal(report.recommendation, "review_needed");
  assert.equal(report.fileSummary.totalFiles, 1);
  assert.equal(report.fileSummary.textScanned, 0);
  assert.equal(report.fileSummary.skippedBinaryOrLarge, 1);
  assert.ok(report.findings.some(f => f.file === "SKILL.md" && f.match === "symbolic_link_not_followed"));
  assert.deepEqual(report.destructiveOps, []);
  assert.doesNotMatch(stdout, /FAKE_EXTERNAL_SENTINEL/);
  assert.ok(!reads.includes(entry) && !reads.includes(outside));
  assertGap(report);
});

test("bundle discovery preserves known entries alongside readable sibling files", (t) => {
  const { base, root } = fixture(t);
  fs.appendFileSync(path.join(root, "SKILL.md"), "rm -rf /synthetic-fixture\n");
  const sibling = path.join(base, "sibling");
  fs.mkdirSync(sibling);
  fs.writeFileSync(path.join(sibling, "SKILL.md"), header);
  fs.writeFileSync(path.join(sibling, "client.js"), 'fetch("https://example.invalid")\n');
  const { report } = inspect(t, base, { denied: [root] });
  assert.equal(report.recommendation, "block");
  assert.equal(report.skills.length, 2);
  assert.deepEqual(report.entryFiles, [path.join("sibling", "SKILL.md"), path.join("skill", "SKILL.md")]);
  assert.equal(report.fileSummary.totalFiles, 3);
  assert.equal(report.fileSummary.textScanned, 3);
  assert.ok(report.destructiveOps.includes(`${path.join("skill", "SKILL.md")}:5`));
  assert.ok(report.networkDbAccess.includes(`${path.join("sibling", "client.js")}:1`));
  assertGap(report);
});

test("managed root aliases keep known entry risk coverage after enumeration fails", (t) => {
  const { base, root } = fixture(t);
  const alias = path.join(base, "alias");
  fs.symlinkSync(root, alias, "dir");
  fs.appendFileSync(path.join(root, "SKILL.md"), "rm -rf /synthetic-fixture\n");
  const { report } = inspect(t, alias, { denied: [root] });
  assert.equal(report.inspectedRoot, fs.realpathSync(root));
  assert.equal(report.recommendation, "block");
  assert.deepEqual(report.destructiveOps, ["SKILL.md:5"]);
  assert.equal(report.fileSummary.totalFiles, 1);
  assertGap(report);
});

test("normally enumerated entries stay deduplicated and are read only once", (t) => {
  const { root } = fixture(t);
  const entry = path.join(root, "SKILL.md");
  const { status, report, reads } = inspect(t, root);
  assert.equal(status, 0);
  assert.equal(report.recommendation, "allow");
  assert.equal(report.fileSummary.totalFiles, 1);
  assert.equal(report.fileSummary.textScanned, 1);
  assert.equal(reads.filter(p => p === entry).length, 1);
  assert.deepEqual(report.findings, []);
});
