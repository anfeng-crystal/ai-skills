import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import zlib from "node:zlib";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const script = fileURLToPath(new URL("./extract-session-evidence.mjs", import.meta.url));
const hasZstd = typeof zlib.zstdCompressSync === "function" && spawnSync("zstd", ["--version"]).status === 0;
const records = [
  { type: "session_meta", payload: { id: "example", source: "cli" } },
  { type: "response_item", payload: { type: "message", role: "assistant", content: [{ type: "output_text", text: "已添加参数" }] } },
  { type: "response_item", payload: { type: "message", role: "user", content: [{ type: "input_text", text: "不要新增参数 token=private-secret" }] } },
  { type: "response_item", payload: { type: "function_call", name: "exec", call_id: "one", arguments: "node scripts/check.mjs" } },
  { type: "response_item", payload: { type: "function_call_output", call_id: "one", output: "Process exited with code 2 private-output" } },
];
const session = records.map(JSON.stringify).join("\n") + "\n";

function fixture(t) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "session-evidence-zstd-"));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  return temp;
}

function run(root, args = [], injection = "") {
  const preload = path.join(root, "inject.mjs");
  fs.writeFileSync(preload, injection);
  return spawnSync(process.execPath, ["--import", pathToFileURL(preload).href, script, "--root", root, ...args], {
    encoding: "utf8", timeout: 10000,
  });
}

test("plain and compressed sessions produce equivalent redacted messages and linked tool evidence", { skip: !hasZstd }, (t) => {
  const temp = fixture(t);
  fs.writeFileSync(path.join(temp, "plain.jsonl"), session);
  fs.writeFileSync(path.join(temp, "compressed.jsonl.zst"), zlib.zstdCompressSync(session));
  for (const args of [[], ["--tool-errors-only"]]) {
    const result = run(temp, args);
    assert.equal(result.status, 0, result.stderr);
    const report = JSON.parse(result.stdout);
    assert.equal(report.stats.files, 2);
    assert.equal(report.candidates.length, 2);
    const normalized = report.candidates.map(({ sourceFile, ...candidate }) => candidate);
    assert.deepEqual(normalized[0], normalized[1]);
    assert.deepEqual(report.candidates.map((item) => item.sourceFile).sort(), ["compressed.jsonl.zst", "plain.jsonl"]);
    assert.equal(report.candidates[0].sourceLine, args.length ? 5 : 3);
    assert.ok(report.candidates.every((item) => item.sessionKind === "main"));
    assert.ok(!result.stdout.includes("private-secret"));
    assert.ok(!result.stdout.includes("private-output"));
    if (args.length) {
      assert.ok(report.coverage.every((item) => item.lines === 5));
      assert.equal(report.coverage.find((item) => item.sourceFile.endsWith(".zst")).bytesAtOpen,
        fs.statSync(path.join(temp, "compressed.jsonl.zst")).size);
    }
  }
});

test("corrupt and truncated archives fail without losing valid sibling evidence", { skip: !hasZstd }, (t) => {
  const temp = fixture(t);
  fs.writeFileSync(path.join(temp, "bad.jsonl.zst"), "private-corrupt-archive");
  fs.writeFileSync(path.join(temp, "truncated.jsonl.zst"), zlib.zstdCompressSync(session).subarray(0, 6));
  fs.writeFileSync(path.join(temp, "partial.jsonl.zst"), Buffer.concat([
    zlib.zstdCompressSync(session), zlib.zstdCompressSync("tail").subarray(0, 6),
  ]));
  fs.writeFileSync(path.join(temp, "valid.jsonl"), session);
  for (const args of [[], ["--format", "jsonl"]]) {
    const result = run(temp, args);
    assert.equal(result.status, 1, result.stderr);
    const candidates = args.length ? result.stdout.trim().split("\n").map(JSON.parse) : JSON.parse(result.stdout).candidates;
    const errors = args.length ? result.stderr.trim().split("\n").map(JSON.parse) : JSON.parse(result.stdout).errors;
    assert.deepEqual(candidates.map((item) => item.sourceFile).sort(), ["partial.jsonl.zst", "valid.jsonl"]);
    assert.equal(errors.length, 3);
    assert.ok(errors.every((item) => item.message === "cannot decompress JSONL"));
    assert.equal(errors.find((item) => item.file.endsWith("partial.jsonl.zst")).sourceLine, 5);
    if (args.length) assert.ok(errors.every((item) => item.type === "extraction_error"));
    assert.ok(!(result.stdout + result.stderr).includes("private-corrupt-archive"));
  }
});

test("a missing Zstandard executable reports the uncovered archive and still reads plain sessions", (t) => {
  const temp = fixture(t);
  fs.writeFileSync(path.join(temp, "archive.jsonl.zst"), "not-decoded");
  fs.writeFileSync(path.join(temp, "valid.jsonl"), session);
  const result = run(temp, ["--tool-errors-only"], `import cp from "node:child_process";
    const original = cp.spawn;
    cp.spawn = (_command, args, options) => original("nonexistent-test-zstd-executable", args, options);`);
  assert.equal(result.status, 1, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.stats.files, 2);
  assert.equal(report.candidates.length, 1);
  assert.deepEqual(report.errors, [{ file: path.join(temp, "archive.jsonl.zst"), sourceLine: 0,
    message: "zstd executable not found" }]);
  assert.equal(report.coverage.find((item) => item.sourceFile.endsWith(".zst")).lines, 0);
});

test("an archive disappearing after stat reports failure and does not abort later files", { skip: !hasZstd }, (t) => {
  const temp = fixture(t);
  fs.writeFileSync(path.join(temp, "bad.jsonl.zst"), zlib.zstdCompressSync(session));
  fs.writeFileSync(path.join(temp, "valid.jsonl"), session);
  const result = run(temp, [], `import fs from "node:fs";
    const original = fs.statSync;
    fs.statSync = function (target, ...args) {
      const stat = original.call(this, target, ...args);
      if (target.endsWith(".zst")) fs.unlinkSync(target);
      return stat;
    };`);
  assert.equal(result.status, 1, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.candidates.length, 1);
  assert.equal(report.errors[0].message, "cannot decompress JSONL");
});

test("excluded compressed child sessions close cleanly and remain opt-in", { skip: !hasZstd }, (t) => {
  const temp = fixture(t);
  const child = [{ type: "session_meta", payload: { id: "child", thread_source: "subagent" } }, ...records.slice(1)];
  fs.writeFileSync(path.join(temp, "child.jsonl.zst"), zlib.zstdCompressSync(child.map(JSON.stringify).join("\n") + "\n"));
  const excluded = run(temp);
  assert.equal(excluded.status, 0, excluded.stderr);
  assert.equal(JSON.parse(excluded.stdout).candidates.length, 0);
  const included = run(temp, ["--include-subagents"]);
  assert.equal(included.status, 0, included.stderr);
  assert.equal(JSON.parse(included.stdout).stats.subagentSessions, 1);
  assert.equal(JSON.parse(included.stdout).candidates.length, 1);
  assert.equal(JSON.parse(included.stdout).candidates[0].sessionKind, "subagent");
});
