import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { spawnSync } from "node:child_process";

const script = new URL("./extract-session-evidence.mjs", import.meta.url);

test("scans active and archived main sessions while excluding subagents and injected blocks", () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "session-evidence-"));
  const active = path.join(temp, "sessions");
  const archived = path.join(temp, "archived_sessions");
  fs.mkdirSync(active);
  fs.mkdirSync(archived);

  writeSession(path.join(active, "active.jsonl"), {
    id: "active-1",
    session_id: "active-1",
    thread_source: "user",
    timestamp: "2026-08-01T00:00:00Z",
    cwd: "/work",
  }, [
    message("user", ["<recommended_plugins>noise</recommended_plugins>", "先做方案"]),
    message("assistant", ["已经改好了"]),
    message("user", ["不是让你修改，只要方案"]),
  ]);
  writeSession(path.join(archived, "archived.jsonl"), {
    id: "archived-1",
    session_id: "archived-1",
    thread_source: null,
    timestamp: "2026-07-01T00:00:00Z",
    cwd: "/work",
  }, [message("user", ["这个字段应该传编码，不是名称"])]);
  writeSession(path.join(active, "subagent.jsonl"), {
    id: "child-1",
    session_id: "active-1",
    thread_source: "subagent",
    timestamp: "2026-08-01T00:01:00Z",
  }, [message("user", ["错误也不能进入结果"])]);
  writeSession(path.join(active, "object-subagent.jsonl"), {
    id: "object-child",
    session_id: "object-child",
    thread_source: null,
    source: { subagent: { thread_spawn: { parent_thread_id: "active-1" } } },
    timestamp: "2026-08-01T00:02:00Z",
  }, [message("user", ["这种 source object 也不能进入结果"])]);

  const result = spawnSync(process.execPath, [
    script.pathname,
    "--root", active,
    "--root", archived,
  ], { encoding: "utf8" });

  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.deepEqual(report.stats, {
    files: 4,
    mainSessions: 2,
    activeSessions: 1,
    archivedSessions: 1,
    userMessages: 3,
    candidateMessages: 2,
  });
  assert.equal(report.candidates[0].sessionId, "archived-1");
  assert.equal(report.candidates[1].sessionId, "active-1");
  assert.equal(report.candidates[1].previousAssistantText, "已经改好了");
  assert.ok(!result.stdout.includes("recommended_plugins"));
  assert.ok(!result.stdout.includes("child-1"));
  assert.ok(!result.stdout.includes("object-child"));
  assert.ok(!result.stdout.includes("/work"));
  assert.equal(report.candidates[1].sourceFile, "active.jsonl");
  assert.equal(report.candidates[1].sourceLine, 4);
});

test("redacts common secret and identity values", () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "session-evidence-redact-"));
  writeSession(path.join(temp, "one.jsonl"), {
    id: "one",
    session_id: "one",
    thread_source: "user",
    timestamp: "2026-08-01T00:00:00Z",
  }, [message("user", [
    "错误：token=abc123 cookie:session-value 身份证 11010519491231002X\n"
      + "Authorization: Bearer header-secret\n"
      + "Cookie: sid=one; tenant=two\n"
      + "{\"DB_PASSWORD\": \"json-secret\", \"refresh_token\": \"refresh-secret\"}\n"
      + "https://admin:url-secret@example.invalid/path AKIA1234567890ABCDEF\n"
      + "mail=user@example.com phone=13800138000 ip=10.20.30.40\n"
      + "jdbc:postgresql://db.internal:5432/prod user_id=123456789012\n"
      + "uuid=123e4567-e89b-42d3-a456-426614174000 path=/Users/private/project/file.txt\n"
      + "attachment=/var/folders/private/a.png host=pm.example.cn/ierp id=0-001-016-092",
  ])]);

  const result = spawnSync(process.execPath, [script.pathname, "--root", temp], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.ok(result.stdout.includes("token=<redacted>"));
  assert.ok(result.stdout.includes("cookie=<redacted>"));
  assert.ok(result.stdout.includes("<redacted-id>"));
  assert.ok(!result.stdout.includes("abc123"));
  assert.ok(!result.stdout.includes("11010519491231002X"));
  for (const secret of [
    "header-secret", "sid=one", "tenant=two", "json-secret", "refresh-secret",
    "url-secret", "AKIA1234567890ABCDEF", "user@example.com", "13800138000",
    "10.20.30.40", "db.internal", "123456789012", "123e4567-e89b-42d3-a456-426614174000",
    "/Users/private/project/file.txt", "/var/folders/private/a.png", "pm.example.cn", "0-001-016-092",
  ]) {
    assert.ok(!result.stdout.includes(secret), `leaked ${secret}`);
  }
});

test("truncates on Unicode code-point boundaries and keeps JSON parseable", () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "session-evidence-unicode-"));
  writeSession(path.join(temp, "one.jsonl"), {
    id: "one",
    session_id: "one",
    thread_source: "user",
    timestamp: "2026-08-01T00:00:00Z",
  }, [message("user", [`错误：${"a".repeat(76)}😀尾部`])]);

  const result = spawnSync(process.execPath, [
    script.pathname,
    "--root", temp,
    "--max-chars", "80",
  ], { encoding: "utf8" });

  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.candidates.length, 1);
  assert.match(report.candidates[0].userText, /😀…$/u);
});

function writeSession(file, meta, records) {
  const lines = [
    JSON.stringify({ timestamp: meta.timestamp, type: "session_meta", payload: meta }),
    ...records.map((payload) => JSON.stringify({ timestamp: meta.timestamp, type: "response_item", payload })),
  ];
  fs.writeFileSync(file, `${lines.join("\n")}\n`, "utf8");
}

function message(role, texts) {
  return {
    type: "message",
    role,
    content: texts.map((text) => ({ type: role === "assistant" ? "output_text" : "input_text", text })),
  };
}

test("streams malformed lines, accepts modern metadata and links repeated child tool failures without output text", () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "session-evidence-tools-"));
  const file = path.join(temp, "child.jsonl");
  const call = (id) => ({ type: "function_call", name: "exec_command", call_id: id,
    arguments: JSON.stringify({ cmd: "python skills/demo/scripts/run.py --token private-secret" }) });
  const result = (id, output) => ({ type: "function_call_output", call_id: id, output });
  writeSession(file, { id: "child", source: { subagent: { thread_spawn: { parent_thread_id: "parent" } } } }, [
    call("a"), result("a", "Process exited with code 2\ncan't open file: private-output"),
    call("b"), result("b", "Process exited with code 2\ncan't open file: private-output"),
    call("c"), result("c", "Process exited with code 0\nOK"),
    call("d"), result("d", "Process exited with code 2\ncan't open file: private-output"),
  ]);
  fs.appendFileSync(file, '{"private-parser-secret"\n');
  writeSession(path.join(temp, "main.jsonl"), { id: "modern", source: "cli" }, [message("user", ["错误"])]);
  const run = spawnSync(process.execPath, [script.pathname, "--root", temp, "--include-subagents", "--tool-errors-only"], { encoding: "utf8" });
  assert.equal(run.status, 1);
  const report = JSON.parse(run.stdout);
  assert.equal(report.stats.mainSessions, 1);
  assert.equal(report.stats.subagentSessions, 1);
  assert.equal(report.stats.toolCalls, 4);
  assert.equal(report.stats.errorResults, 3);
  assert.equal(report.stats.repeatedIdenticalFailures, 1);
  assert.equal(report.candidates[0].callLine, 2);
  assert.equal(report.candidates[0].sourceLine, 3);
  assert.equal(report.candidates[1].repeatedAfterLine, 3);
  assert.equal(report.candidates[2].repeatedAfterLine, null);
  assert.deepEqual(report.candidates[0].scripts, ["run.py"]);
  assert.equal(report.candidates[0].skillReference, true);
  assert.equal(report.errors[0].sourceLine, 10);
  for (const secret of ["private-secret", "private-output", "private-parser-secret"]) assert.ok(!run.stdout.includes(secret));
  fs.rmSync(temp, { recursive: true });
});

test("unwraps nested tool content and detects nonzero structured exits without exposing output", () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "session-evidence-nested-"));
  writeSession(path.join(temp, "main.jsonl"), { id: "modern", source: "cli" }, [
    { type: "custom_tool_call", name: "exec", call_id: "nested", input: "node skills/demo/check.mjs" },
    { type: "custom_tool_call_output", call_id: "nested", output: JSON.stringify([
      { type: "text", text: JSON.stringify({ exit_code: -9, output: "nested-secret" }) },
    ]) },
  ]);
  const run = spawnSync(process.execPath, [script.pathname, "--root", temp, "--tool-errors-only"], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  const report = JSON.parse(run.stdout);
  assert.deepEqual(report.candidates[0].categories, ["nonzero_exit"]);
  assert.deepEqual(report.candidates[0].exitCodes, [-9]);
  assert.ok(!run.stdout.includes("nested-secret"));
  fs.rmSync(temp, { recursive: true });
});

test("reads a log larger than the Node heap without retaining every record", () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "session-evidence-stream-"));
  const file = path.join(temp, "large.jsonl");
  const fd = fs.openSync(file, "w");
  fs.writeSync(fd, JSON.stringify({ type: "session_meta", payload: { id: "modern" } }) + "\n");
  const line = JSON.stringify({ type: "response_item", payload: { type: "reasoning", text: "x".repeat(65536) } }) + "\n";
  for (let i = 0; i < 1024; i += 1) fs.writeSync(fd, line);
  fs.closeSync(fd);
  const run = spawnSync(process.execPath, ["--max-old-space-size=48", script.pathname, "--root", temp, "--tool-errors-only"], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  assert.equal(JSON.parse(run.stdout).stats.mainSessions, 1);
  fs.rmSync(temp, { recursive: true });
});

test("reports non-object JSON records and keeps later messages and assistant context", (t) => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "session-evidence-shapes-"));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const file = path.join(temp, "main.jsonl");
  writeSession(file, { id: "modern", source: "cli" }, [
    message("assistant", ["先前助手上下文"]),
    message("user", ["错误：前一条消息"]),
  ]);
  fs.appendFileSync(file, [null, [], 3, "private-shape-secret", false].map(JSON.stringify).join("\n") + "\n");
  fs.appendFileSync(file, '{"private-parser-secret"\n');
  fs.appendFileSync(file, JSON.stringify({ type: "response_item", payload: message("user", ["错误：后一条消息"]) }) + "\n");

  const run = spawnSync(process.execPath, [script.pathname, "--root", temp], { encoding: "utf8" });
  assert.equal(run.status, 1, run.stderr);
  const report = JSON.parse(run.stdout);
  assert.deepEqual(report.candidates.map((candidate) => candidate.sourceLine), [3, 10]);
  assert.equal(report.stats.userMessages, 2);
  assert.equal(report.stats.candidateMessages, 2);
  assert.ok(report.candidates.every((candidate) => candidate.previousAssistantText === "先前助手上下文"));
  assert.deepEqual(report.errors.map(({ sourceLine, message }) => ({ sourceLine, message })), [
    ...[4, 5, 6, 7, 8].map((sourceLine) => ({ sourceLine, message: "invalid JSONL record" })),
    { sourceLine: 9, message: "invalid JSONL" },
  ]);
  for (const secret of ["private-shape-secret", "private-parser-secret"]) assert.ok(!run.stdout.includes(secret));

  const jsonl = spawnSync(process.execPath, [script.pathname, "--root", temp, "--format", "jsonl"], { encoding: "utf8" });
  assert.equal(jsonl.status, 1, jsonl.stderr);
  assert.deepEqual(jsonl.stdout.trim().split("\n").map((line) => JSON.parse(line).sourceLine), [3, 10]);
});

test("skips non-object records before metadata without admitting other non-session files", (t) => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "session-evidence-leading-shapes-"));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  for (const [index, record] of [null, [], 3, "private-leading-secret", false].entries()) {
    const file = path.join(temp, `${index}.jsonl`);
    writeSession(file, { id: `session-${index}`, source: "cli" }, [message("user", ["错误：有效消息"])]);
    fs.writeFileSync(file, JSON.stringify(record) + "\n" + fs.readFileSync(file, "utf8"));
  }
  const unknown = path.join(temp, "non-session.jsonl");
  writeSession(unknown, { id: "must-not-enter" }, [message("user", ["错误：不纳入"])]);
  fs.writeFileSync(unknown, '{"type":"event_msg","payload":{}}\n' + fs.readFileSync(unknown, "utf8"));

  const run = spawnSync(process.execPath, [script.pathname, "--root", temp], { encoding: "utf8" });
  assert.equal(run.status, 1, run.stderr);
  const report = JSON.parse(run.stdout);
  assert.equal(report.stats.files, 6);
  assert.equal(report.stats.mainSessions, 5);
  assert.equal(report.candidates.length, 5);
  assert.ok(report.candidates.every((candidate) => candidate.sourceLine === 3));
  assert.equal(report.errors.length, 5);
  assert.ok(report.errors.every((error) => error.sourceLine === 1 && error.message === "invalid JSONL record"));
  assert.ok(!run.stdout.includes("private-leading-secret"));
  assert.ok(!run.stdout.includes("must-not-enter"));
});

test("retains tool-call linkage and coverage across a non-object JSON record", (t) => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "session-evidence-tool-shapes-"));
  t.after(() => fs.rmSync(temp, { recursive: true, force: true }));
  const file = path.join(temp, "main.jsonl");
  writeSession(file, { id: "modern", source: "cli" }, [
    { type: "function_call", name: "exec_command", call_id: "one", arguments: '{"cmd":"node skills/demo/check.mjs"}' },
  ]);
  fs.appendFileSync(file, "null\n" + JSON.stringify({ type: "response_item", payload: {
    type: "function_call_output", call_id: "one", output: '{"exit_code":2,"output":"private-output-secret"}',
  } }) + "\n");

  const run = spawnSync(process.execPath, [script.pathname, "--root", temp, "--tool-errors-only"], { encoding: "utf8" });
  assert.equal(run.status, 1, run.stderr);
  const report = JSON.parse(run.stdout);
  assert.equal(report.stats.toolCalls, 1);
  assert.equal(report.stats.toolResults, 1);
  assert.equal(report.stats.unmatchedResults, 0);
  assert.equal(report.stats.errorResults, 1);
  assert.equal(report.candidates[0].callLine, 2);
  assert.equal(report.candidates[0].sourceLine, 4);
  assert.deepEqual(report.candidates[0].scripts, ["check.mjs"]);
  assert.equal(report.errors[0].sourceLine, 3);
  assert.equal(report.coverage[0].lines, 4);
  assert.equal(report.coverage[0].bytesAtOpen, fs.statSync(file).size);
  assert.ok(!run.stdout.includes("private-output-secret"));
});
