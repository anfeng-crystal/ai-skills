import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { spawnSync } from "node:child_process";

const script = new URL("./extract-session-evidence.mjs", import.meta.url);
const secret = "private-nested-content-secret";
const text = (value, type = "input_text") => ({ type, text: value });
const message = (role, content) => ({ type: "message", role, content });

function fixture(t, records) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "session-evidence-content-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  writeSession(root, "main.jsonl", { id: "main", source: "cli" }, records);
  return root;
}

function writeSession(root, name, meta, records) {
  fs.writeFileSync(path.join(root, name), [
    { type: "session_meta", payload: meta },
    ...records.map((payload) => ({ type: "response_item", payload })),
  ].map(JSON.stringify).join("\n") + "\n");
}

function run(root, ...args) {
  const result = spawnSync(process.execPath, [script.pathname, "--root", root, ...args], {
    encoding: "utf8", timeout: 10000,
  });
  assert.ok(!(result.stdout + result.stderr).includes(secret), "invalid content leaked");
  assert.ok(!(result.stdout + result.stderr).includes("[object Object]"), "invalid object was coerced");
  return result;
}

function partial(root, expectedLines, ...args) {
  const result = run(root, ...args);
  assert.equal(result.status, 1, result.stderr);
  assert.equal(result.stderr, "");
  const report = JSON.parse(result.stdout);
  assert.deepEqual(report.errors.map(({ sourceLine, message }) => ({ sourceLine, message })).sort((a, b) => a.sourceLine - b.sourceLine),
    expectedLines.map((sourceLine) => ({ sourceLine, message: "invalid message content" })).sort((a, b) => a.sourceLine - b.sourceLine));
  return report;
}

test("object-valued user text is a record error and preserves later messages and context", (t) => {
  const root = fixture(t, [
    message("assistant", [text("先前助手上下文", "output_text")]),
    message("user", [text({ unexpected: secret })]),
    message("user", [text("不要丢掉这条后续合成消息")]),
  ]);
  const report = partial(root, [3]);
  assert.equal(report.stats.userMessages, 1);
  assert.equal(report.stats.candidateMessages, 1);
  assert.equal(report.candidates[0].sourceLine, 4);
  assert.equal(report.candidates[0].userMessageIndex, 1);
  assert.equal(report.candidates[0].previousAssistantText, "先前助手上下文");
});

test("non-string recognized text fields are reported instead of coerced or silently lost", (t) => {
  const invalid = [null, false, 0, 42, [secret], { nested: secret }, undefined];
  const root = fixture(t, invalid.flatMap((value) => [
    message("user", [text(value)]), message("user", [text("错误：后续记录")]),
  ]));
  const report = partial(root, invalid.map((_, index) => index * 2 + 2));
  assert.equal(report.stats.userMessages, invalid.length);
  assert.deepEqual(report.candidates.map((item) => item.sourceLine), invalid.map((_, index) => index * 2 + 3));
  assert.deepEqual(report.candidates.map((item) => item.userMessageIndex), invalid.map((_, index) => index + 1));
});

test("invalid outer content and malformed members remain visible once per record", (t) => {
  const invalid = [undefined, null, secret, 7, false, { text: secret },
    [null, secret, 0, false, [], { text: secret }, { type: 3, text: secret }]];
  const root = fixture(t, [
    ...invalid.map((content) => message("user", content)),
    message("user", [text("错误：仍然可读")]),
  ]);
  const report = partial(root, invalid.map((_, index) => index + 2));
  assert.equal(report.stats.userMessages, 1);
  assert.equal(report.candidates[0].sourceLine, invalid.length + 2);
});

test("mixed user content retains valid strings, injected filtering and redaction", (t) => {
  const root = fixture(t, [message("user", [
    text("错误：有效 token=synthetic-value"),
    text({ nested: secret }), text([secret]),
    text("<environment_context>injected-secret</environment_context>"),
    { type: "input_image", image_url: secret },
    text({ nested: secret }, "output_text"),
    text("第二段", "text"), text(""), text("   "),
  ])]);
  const report = partial(root, [2]);
  assert.equal(report.stats.userMessages, 1);
  assert.equal(report.candidates[0].userText, "错误：有效 token=<redacted>\n第二段");
  assert.ok(!JSON.stringify(report).includes("injected-secret"));
  assert.ok(!JSON.stringify(report).includes("synthetic-value"));
});

test("assistant partial text survives but unreadable assistant content clears stale context", (t) => {
  const root = fixture(t, [
    message("assistant", [text("旧上下文", "output_text")]),
    message("assistant", [text({ nested: secret }, "output_text"), text("新上下文 token=synthetic-value", "text")]),
    message("user", [text("错误：混合助手后")]),
    message("assistant", [text([secret], "output_text")]),
    message("user", [text("错误：非法助手后")]),
    message("assistant", [text("恢复上下文", "input_text")]),
    message("assistant", []),
    message("assistant", [{ type: "output_image", data: secret }]),
    message("user", [text("错误：正常非文本助手后")]),
    message("assistant", { unexpected: secret }),
    message("user", [text("错误：非法content后")]),
  ]);
  const report = partial(root, [3, 5, 11]);
  assert.deepEqual(report.candidates.map((item) => item.previousAssistantText), [
    "新上下文 token=<redacted>", "", "恢复上下文", "",
  ]);
});

test("JSONL emits content diagnostics on stderr while valid mixed and later records survive", (t) => {
  const root = fixture(t, [
    message("user", [text({ nested: secret }), text("普通有效文本")]),
    message("assistant", [text(false, "output_text")]),
    message("user", [text("后续有效文本")]),
  ]);
  const result = run(root, "--format", "jsonl", "--all-user-messages");
  assert.equal(result.status, 1);
  const candidates = result.stdout.trim().split("\n").map(JSON.parse);
  assert.deepEqual(candidates.map((item) => item.sourceLine), [2, 4]);
  assert.deepEqual(candidates.map((item) => item.userMessageIndex), [1, 2]);
  assert.ok(candidates.every((item) => item.previousAssistantText === ""));
  assert.deepEqual(result.stderr.trim().split("\n").map(JSON.parse), [2, 3].map((sourceLine) => ({
    type: "extraction_error", file: path.join(root, "main.jsonl"), sourceLine, message: "invalid message content",
  })));
  assert.equal(partial(root, [2, 3]).stats.candidateMessages, 0);
});

test("tool mode ignores message shapes without losing call linkage or coverage", (t) => {
  const root = fixture(t, [
    { type: "function_call", call_id: "one", name: "exec", arguments: "node skills/demo/check.mjs" },
    message("user", [text({ nested: secret })]),
    message("assistant", { unexpected: secret }),
    { type: "function_call_output", call_id: "one", output: { exit_code: 2, output: secret } },
  ]);
  const result = run(root, "--tool-errors-only");
  assert.equal(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.deepEqual(report.errors, []);
  assert.equal(report.stats.toolCalls, 1);
  assert.equal(report.stats.toolResults, 1);
  assert.equal(report.stats.unmatchedResults, 0);
  assert.equal(report.candidates[0].callLine, 2);
  assert.equal(report.candidates[0].sourceLine, 5);
  assert.deepEqual(report.candidates[0].scripts, ["check.mjs"]);
  assert.equal(report.coverage[0].lines, 5);
});

test("excluded sessions stay excluded and assistant context never crosses sessions", (t) => {
  const root = fixture(t, [
    message("assistant", [text("只属于主会话", "output_text")]),
    message("user", [text({ nested: secret })]),
    message("user", [text("错误：主会话")]),
  ]);
  writeSession(root, "other.jsonl", { id: "other" }, [message("user", [text("错误：独立会话")])]);
  writeSession(root, "child.jsonl", { id: "child", thread_source: "subagent" }, [message("user", { nested: secret })]);
  writeSession(root, "voice.jsonl", { id: "voice", thread_source: "realtime_voice" }, [message("assistant", secret)]);
  const report = partial(root, [3]);
  assert.equal(report.stats.mainSessions, 2);
  assert.equal(report.candidates.find((item) => item.sessionId === "main").previousAssistantText, "只属于主会话");
  assert.equal(report.candidates.find((item) => item.sessionId === "other").previousAssistantText, "");
  const included = partial(root, [2, 3, 2], "--include-subagents", "--include-realtime");
  assert.equal(included.stats.subagentSessions, 1);
  assert.equal(included.stats.mainSessions, 3);
});
