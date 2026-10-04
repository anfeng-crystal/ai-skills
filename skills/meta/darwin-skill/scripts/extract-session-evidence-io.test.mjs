import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";

const script = new URL("./extract-session-evidence.mjs", import.meta.url);
const privateError = "private-io-exception-secret";

function fixture(t) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "session-evidence-io-"));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  return temp;
}

function writeSession(file, id = "valid") {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const records = [
    { type: "session_meta", payload: { id, source: "cli" } },
    { type: "response_item", payload: { type: "message", role: "user", content: [
      { type: "input_text", text: "错误：保留有效候选" },
    ] } },
  ];
  fs.writeFileSync(file, records.map(JSON.stringify).join("\n") + "\n");
}

function run(temp, args, injection = "") {
  const preload = path.join(temp, "inject.mjs");
  fs.writeFileSync(preload, `import fs from "node:fs";\n${injection}`);
  return spawnSync(process.execPath, ["--import", pathToFileURL(preload).href, script.pathname, ...args], {
    encoding: "utf8", timeout: 10000,
  });
}

function partialReport(result, expectedIds = ["valid"]) {
  assert.equal(result.status, 1, result.stderr);
  assert.equal(result.stderr, "");
  const report = JSON.parse(result.stdout);
  assert.deepEqual(report.candidates.map((candidate) => candidate.sessionId).sort(), expectedIds.sort());
  assert.ok(report.errors.length > 0);
  assert.ok(!result.stdout.includes(privateError));
  return report;
}

test("a regular-file root preserves candidates from roots before and after it", (t) => {
  const temp = fixture(t);
  const first = path.join(temp, "first");
  const last = path.join(temp, "last");
  const invalid = path.join(temp, "plain-file");
  writeSession(path.join(first, "one.jsonl"), "first");
  writeSession(path.join(last, "two.jsonl"), "last");
  fs.writeFileSync(invalid, "not a directory");
  const report = partialReport(run(temp, ["--root", first, "--root", invalid, "--root", last]), ["first", "last"]);
  assert.deepEqual(report.errors, [{ directory: invalid, message: "cannot read directory" }]);
  assert.equal(report.stats.files, 2);
});

test("an inaccessible or disappeared subtree does not discard its readable siblings", (t) => {
  const temp = fixture(t);
  const root = path.join(temp, "sessions");
  const badDirectory = path.join(root, "bad");
  fs.mkdirSync(badDirectory, { recursive: true });
  writeSession(path.join(root, "good", "one.jsonl"));
  const injection = `const original = fs.readdirSync;
    fs.readdirSync = function (target, ...args) {
      if (target === ${JSON.stringify(badDirectory)}) throw new Error(${JSON.stringify(privateError)});
      return original.call(this, target, ...args);
    };`;
  const report = partialReport(run(temp, ["--root", root], injection));
  assert.deepEqual(report.errors, [{ directory: badDirectory, message: "cannot read directory" }]);
});

for (const method of ["statSync", "createReadStream"]) {
  test(`${method} synchronous failure is scoped to its file with honest coverage`, (t) => {
    const temp = fixture(t);
    const root = path.join(temp, "sessions");
    const bad = path.join(root, "a-bad.jsonl");
    writeSession(bad, "unreadable");
    writeSession(path.join(root, "z-good.jsonl"));
    const size = fs.statSync(bad).size;
    const injection = `const original = fs[${JSON.stringify(method)}];
      fs[${JSON.stringify(method)}] = function (target, ...args) {
        if (target === ${JSON.stringify(bad)}) throw new Error(${JSON.stringify(privateError)});
        return original.call(this, target, ...args);
      };`;
    const normal = partialReport(run(temp, ["--root", root], injection));
    assert.deepEqual(normal.errors, [{ file: bad, sourceLine: 0, message: "cannot read JSONL" }]);
    const report = partialReport(run(temp, ["--root", root, "--tool-errors-only"], injection), []);
    assert.equal(report.stats.files, 2);
    assert.equal(report.stats.mainSessions, 1);
    const coverage = report.coverage.find((entry) => entry.sourceFile === "a-bad.jsonl");
    assert.equal(coverage.bytesAtOpen, method === "statSync" ? null : size);
    assert.equal(coverage.lines, 0);
    assert.equal(coverage.rolloutId, null);
  });
}

test("a file disappearing between stat and open is reported without interrupting later files", (t) => {
  const temp = fixture(t);
  const root = path.join(temp, "sessions");
  const bad = path.join(root, "a-bad.jsonl");
  writeSession(bad, "disappeared");
  writeSession(path.join(root, "z-good.jsonl"));
  const injection = `const original = fs.statSync;
    fs.statSync = function (target, ...args) {
      const result = original.call(this, target, ...args);
      if (target === ${JSON.stringify(bad)}) fs.unlinkSync(target);
      return result;
    };`;
  const report = partialReport(run(temp, ["--root", root], injection));
  assert.deepEqual(report.errors, [{ file: bad, sourceLine: 0, message: "cannot read JSONL" }]);
  assert.equal(report.stats.files, 2);
});

test("mid-stream read errors retain earlier candidates and continue other files", (t) => {
  const temp = fixture(t);
  const root = path.join(temp, "sessions");
  const bad = path.join(root, "a-bad.jsonl");
  writeSession(bad, "partial");
  writeSession(path.join(root, "z-good.jsonl"));
  const injection = `import { Readable } from "node:stream";
    const original = fs.createReadStream;
    fs.createReadStream = function (target, ...args) {
      if (target !== ${JSON.stringify(bad)}) return original.call(this, target, ...args);
      const text = fs.readFileSync(target, "utf8");
      let sent = false;
      return new Readable({ read() {
        if (sent) return;
        sent = true;
        this.push(text);
        setImmediate(() => this.destroy(new Error(${JSON.stringify(privateError)})));
      } });
    };`;
  const report = partialReport(run(temp, ["--root", root], injection), ["partial", "valid"]);
  assert.deepEqual(report.errors, [{ file: bad, sourceLine: 2, message: "cannot read JSONL" }]);
});

test("JSONL keeps stdout candidate-only and emits structured directory, root and parse failures on stderr", (t) => {
  const temp = fixture(t);
  const root = path.join(temp, "sessions");
  const file = path.join(root, "one.jsonl");
  const invalid = path.join(temp, "plain-file");
  const missing = path.join(temp, "missing");
  fs.writeFileSync(invalid, "not a directory");
  writeSession(file);
  fs.appendFileSync(file, `{"${privateError}"\nnull\n`);
  const result = run(temp, ["--root", root, "--root", invalid, "--root", missing, "--format", "jsonl"]);
  assert.equal(result.status, 1, result.stderr);
  const candidates = result.stdout.trim().split("\n").map((line) => JSON.parse(line));
  assert.deepEqual(candidates.map((candidate) => candidate.sessionId), ["valid"]);
  assert.ok(candidates.every((candidate) => candidate.evidenceStatus === "candidate_requires_context_review"));
  const errors = result.stderr.trim().split("\n").map((line) => JSON.parse(line));
  assert.deepEqual(errors, [
    { type: "extraction_error", file, sourceLine: 3, message: "invalid JSONL" },
    { type: "extraction_error", file, sourceLine: 4, message: "invalid JSONL record" },
    { type: "extraction_error", directory: invalid, message: "cannot read directory" },
    { type: "extraction_error", root: missing, message: "root does not exist" },
  ]);
  assert.ok(!(result.stdout + result.stderr).includes(privateError));
});

test("JSONL parse errors remain discoverable without mixing diagnostic rows into candidates", (t) => {
  const temp = fixture(t);
  const file = path.join(temp, "one.jsonl");
  writeSession(file);
  fs.appendFileSync(file, `{"${privateError}"\n`);
  const result = run(temp, ["--root", temp, "--format", "jsonl"]);
  assert.equal(result.status, 1, result.stderr);
  assert.equal(JSON.parse(result.stdout).sessionId, "valid");
  assert.deepEqual(JSON.parse(result.stderr), {
    type: "extraction_error", file, sourceLine: 3, message: "invalid JSONL",
  });
  assert.ok(!(result.stdout + result.stderr).includes(privateError));
});

test("a successful JSONL run has no diagnostic stderr", (t) => {
  const temp = fixture(t);
  writeSession(path.join(temp, "one.jsonl"));
  const result = run(temp, ["--root", temp, "--format", "jsonl"]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stderr, "");
  assert.equal(JSON.parse(result.stdout).sessionId, "valid");
});
