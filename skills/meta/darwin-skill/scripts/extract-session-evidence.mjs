#!/usr/bin/env node

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import readline from "node:readline";
import { createHash } from "node:crypto";

const DEFAULT_PATTERN = /不对|错了|错误|应该|不是|不要|别再|怎么又|为什么|并不是|并非|不该|遗漏|漏了|漏掉|没有按|没按|我说|我让|我要求|还没|还是不|不能|必须|只要|你这|又.{0,20}了/;

await main();

async function main() {
  const options = parseArgs(process.argv.slice(2));
  if (options.help) {
    printHelp();
    return;
  }

  const report = await extract(options);
  if (options.format === "jsonl") {
    for (const candidate of report.candidates) {
      process.stdout.write(`${JSON.stringify(candidate)}\n`);
    }
  } else {
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
  }

  if (report.errors.length > 0) process.exitCode = 1;
}

function parseArgs(argv) {
  const options = {
    roots: [],
    allUserMessages: false,
    includeRealtime: false,
    includeSubagents: false,
    toolErrorsOnly: false,
    format: "json",
    maxChars: 1200,
    help: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--root") {
      options.roots.push(path.resolve(requireValue(argv, ++index, token)));
    } else if (token === "--all-user-messages") {
      options.allUserMessages = true;
    } else if (token === "--include-subagents") {
      options.includeSubagents = true;
    } else if (token === "--tool-errors-only") {
      options.toolErrorsOnly = true;
    } else if (token === "--include-realtime") {
      options.includeRealtime = true;
    } else if (token === "--format") {
      options.format = requireValue(argv, ++index, token);
      if (!new Set(["json", "jsonl"]).has(options.format)) {
        throw new Error("--format must be json or jsonl");
      }
    } else if (token === "--max-chars") {
      options.maxChars = Number(requireValue(argv, ++index, token));
      if (!Number.isInteger(options.maxChars) || options.maxChars < 80) {
        throw new Error("--max-chars must be an integer >= 80");
      }
    } else if (token === "--help" || token === "-h") {
      options.help = true;
    } else {
      throw new Error(`unknown argument: ${token}`);
    }
  }

  if (options.roots.length === 0) {
    options.roots = [
      path.join(os.homedir(), ".codex", "sessions"),
      path.join(os.homedir(), ".codex", "archived_sessions"),
    ];
  }
  return options;
}

function requireValue(argv, index, flag) {
  if (!argv[index]) throw new Error(`${flag} requires a value`);
  return argv[index];
}

async function extract(options) {
  const candidates = [];
  const errors = [];
  const coverage = [];
  const stats = {
    files: 0, mainSessions: 0, activeSessions: 0, archivedSessions: 0,
    userMessages: 0, candidateMessages: 0,
  };
  if (options.includeSubagents) stats.subagentSessions = 0;
  if (options.toolErrorsOnly) Object.assign(stats, { toolCalls: 0, toolResults: 0, unmatchedResults: 0, errorResults: 0, repeatedIdenticalFailures: 0 });

  for (const root of options.roots) {
    if (!fs.existsSync(root)) {
      errors.push({ root, message: "root does not exist" });
      continue;
    }
    const rootKind = path.basename(root) === "archived_sessions" ? "archived" : "active";
    for (const file of walkJsonl(root)) {
      stats.files += 1;
      let meta = null;
      let sessionKind;
      let previousAssistant = "";
      let userMessageIndex = 0;
      let sourceLine = 0;
      const calls = new Map();
      const failures = new Map();
      const bytesAtOpen = fs.statSync(file).size;
      const input = fs.createReadStream(file, { encoding: "utf8", ...(bytesAtOpen ? { end: bytesAtOpen - 1 } : {}) });
      const lines = readline.createInterface({ input, crlfDelay: Infinity });
      try {
        for await (const line of lines) {
          sourceLine += 1;
          if (!line.trim()) continue;
          let record;
          try { record = JSON.parse(line); }
          catch {
            // Parser messages can contain private source text. Keep only its location.
            errors.push({ file, sourceLine, message: "invalid JSONL" });
            continue;
          }
          if (!meta) {
            if (record.type !== "session_meta") break;
            meta = record.payload || {};
            sessionKind = getSessionKind(meta);
            if (sessionKind === "subagent" && !options.includeSubagents) break;
            if (sessionKind === "realtime_voice" && !options.includeRealtime) break;
            if (sessionKind === "subagent") stats.subagentSessions += 1;
            else stats.mainSessions += 1;
            if (rootKind === "archived") stats.archivedSessions += 1;
            else stats.activeSessions += 1;
          }
          if (record.type !== "response_item") continue;
          const payload = record.payload || {};
          const evidence = {
            evidenceStatus: "candidate_requires_context_review",
            root: rootKind,
            sessionId: meta.session_id || meta.id || null,
            rolloutId: meta.id || null,
            sessionTimestamp: meta.timestamp || null,
            sourceFile: path.relative(root, file), sourceLine,
          };
          if (options.toolErrorsOnly) {
            if (["function_call", "custom_tool_call"].includes(payload.type)) {
              stats.toolCalls += 1;
              const command = payload.arguments || payload.input || "";
              const serialized = typeof command === "string" ? command : JSON.stringify(command);
              calls.set(payload.call_id, {
                sourceLine, toolName: payload.name,
                scripts: [...new Set([...serialized.matchAll(/(?:[\w.-]+\/)?([\w.-]+\.(?:py|mjs|cjs|js|sh|ps1))\b/g)].map((match) => match[1]))],
                skillReference: /(?:skills[\\/]|SKILL\.md)/i.test(serialized),
                signature: createHash("sha256").update(`${payload.name}\n${serialized}`).digest("hex"),
              });
            } else if (["function_call_output", "custom_tool_call_output"].includes(payload.type)) {
              stats.toolResults += 1;
              const call = calls.get(payload.call_id);
              if (!call) stats.unmatchedResults += 1;
              const outputText = flattenOutput(payload.output);
              const categories = errorCategories(outputText);
              if (categories.length) {
                stats.errorResults += 1;
                const prior = call && failures.get(call.signature);
                if (prior) stats.repeatedIdenticalFailures += 1;
                candidates.push({ ...evidence, sessionKind, kind: "tool_error", callId: payload.call_id || null,
                  callLine: call?.sourceLine || null, toolName: call?.toolName || null,
                  scripts: call?.scripts || [], skillReference: call?.skillReference || false,
                  categories, exitCodes: [...new Set([...outputText.matchAll(/(?:exit_code["']?\s*:\s*|Process exited with code |exit code[=: ]+)(-?\d+)/gi)].map((match) => Number(match[1])))],
                  repeatedAfterLine: prior || null });
                if (call) failures.set(call.signature, sourceLine);
              } else if (call) failures.delete(call.signature);
              calls.delete(payload.call_id);
            }
            continue;
          }
          if (payload.type !== "message") continue;
          if (payload.role === "assistant") {
            const text = messageText(payload.content);
            if (text) previousAssistant = sanitize(text, options.maxChars);
            continue;
          }
          if (payload.role !== "user") continue;
          const text = userText(payload.content);
          if (!text) continue;
          userMessageIndex += 1;
          stats.userMessages += 1;
          if (!options.allUserMessages && !DEFAULT_PATTERN.test(text)) continue;
          candidates.push({ ...evidence, userMessageIndex,
            userText: sanitize(text, options.maxChars), previousAssistantText: previousAssistant });
        }
      } catch {
        errors.push({ file, sourceLine, message: "cannot read JSONL" });
      } finally {
        lines.close();
        input.destroy();
        if (options.toolErrorsOnly) coverage.push({ root: rootKind, sourceFile: path.relative(root, file),
          sessionKind: sessionKind || null, rolloutId: meta?.id || null, bytesAtOpen, lines: sourceLine });
      }
    }
  }
  candidates.sort((left, right) => String(left.sessionTimestamp).localeCompare(String(right.sessionTimestamp))
    || left.sourceLine - right.sourceLine);
  stats.candidateMessages = candidates.length;
  return { stats, errors, candidates, ...(options.toolErrorsOnly ? { coverage } : {}) };
}

function getSessionKind(meta) {
  if (meta.thread_source === "subagent" || meta.source?.subagent
    || (meta.session_id && meta.id !== meta.session_id)) return "subagent";
  return meta.thread_source === "realtime_voice" ? "realtime_voice" : "main";
}

function flattenOutput(value) {
  if (typeof value === "string") {
    try { return flattenOutput(JSON.parse(value)); } catch { return value; }
  }
  if (Array.isArray(value)) return value.map(flattenOutput).join("\n");
  if (value && typeof value === "object") return Object.entries(value).map(([key, item]) => `${key}: ${flattenOutput(item)}`).join("\n");
  return String(value ?? "");
}

function errorCategories(output) {
  const text = typeof output === "string" ? output : JSON.stringify(output ?? "");
  // This is discovery, not proof: quoted logs and intentional negative tests need review.
  const patterns = {
    missing_file: /ENOENT|No such file or directory|can't open file|Cannot find (?:module|package)/i,
    missing_dependency: /ModuleNotFoundError|ImportError|MODULE_NOT_FOUND|ERR_MODULE_NOT_FOUND|command not found/i,
    invalid_arguments: /unrecognized arguments|required arguments|unknown (?:argument|option)|Invalid (?:tool|function) (?:arguments|call)/i,
    syntax_error: /SyntaxError|IndentationError|unexpected token/i,
    permission: /Permission denied|EACCES|EPERM|approval.{0,30}(?:denied|rejected)/i,
    timeout: /timed out|TimeoutError|deadline exceeded|timeout (?:after|of|exceeded)|(?:connect|read) timeout/i,
    runtime_error: /Traceback \(most recent call last\)|TypeError:|ReferenceError:|ValueError:|KeyError:|AttributeError:/,
    nonzero_exit: /(?:exit_code["']?\s*:\s*|Process exited with code |exit code[=: ]+)-?[1-9]\d*/i,
    tool_error: /isError["']?\s*:\s*true|Error executing tool|Error calling tool|tool (?:call )?failed/i,
  };
  return Object.entries(patterns).filter(([, pattern]) => pattern.test(text)).map(([category]) => category);
}

function userText(content) {
  return (Array.isArray(content) ? content : [])
    .filter((item) => item && ["input_text", "text"].includes(item.type))
    .map((item) => item.text || "")
    .filter((text) => text.trim() && !isInjectedBlock(text))
    .join("\n")
    .trim();
}

function messageText(content) {
  return (Array.isArray(content) ? content : [])
    .filter((item) => item && ["output_text", "input_text", "text"].includes(item.type))
    .map((item) => item.text || "")
    .filter(Boolean)
    .join("\n")
    .trim();
}

function isInjectedBlock(text) {
  const trimmed = text.trimStart();
  return trimmed.startsWith("<recommended_plugins>")
    || trimmed.startsWith("# AGENTS.md instructions")
    || trimmed.startsWith("<environment_context>")
    || trimmed.startsWith("<app-context>")
    || trimmed.startsWith("## Memory\n")
    || trimmed.startsWith("<skills_instructions>")
    || trimmed.startsWith("<permissions instructions>");
}

function sanitize(text, maxChars) {
  const redacted = text
    .replace(/-----BEGIN [^-\r\n]*PRIVATE KEY-----[\s\S]*?-----END [^-\r\n]*PRIVATE KEY-----/g, "<redacted-private-key>")
    .replace(/(https?:\/\/)[^\s\/@:]+:[^\s\/@]+@/gi, "$1<redacted-userinfo>@")
    .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]+/gi, "Bearer <redacted>")
    .replace(/(^|\r?\n)([ \t]*(?:authorization|cookie|set-cookie)\s*:\s*)[^\r\n]+/gim, "$1$2<redacted>")
    .replace(/\b(?:eyJ[A-Za-z0-9_-]{10,}\.){2}[A-Za-z0-9_-]{10,}\b/g, "<redacted-jwt>")
    .replace(/\b((?:[A-Za-z0-9]+[_-])*(?:password|passwd|pwd|client[_-]?secret|access[_-]?token|refresh[_-]?token|id[_-]?token|token|authorization|cookie|csrf(?:[_-]?token)?|api[_-]?key|access[_-]?key|signature|secret|tenant[_-]?id|account[_-]?id|user[_-]?id|person[_-]?id))["']?\s*[:=]\s*(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;&\r\n]+)/gi, "$1=<redacted>")
    .replace(/\bAKIA[0-9A-Z]{16}\b/g, "<redacted-access-key>")
    .replace(/\bjdbc:[^\s"'<>]+/gi, "<redacted-dsn>")
    .replace(/\bhttps?:\/\/[^\s"'<>]+/gi, "<redacted-url>")
    .replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, "<redacted-email>")
    .replace(/(?<!\d)1[3-9]\d{9}(?!\d)/g, "<redacted-phone>")
    .replace(/\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b/g, "<redacted-ip>")
    .replace(/\b(?:[A-F0-9]{1,4}:){2,7}[A-F0-9]{1,4}\b/gi, "<redacted-ip>")
    .replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi, "<redacted-uuid>")
    .replace(/\b\d{17}[0-9Xx]\b/g, "<redacted-id>")
    .replace(/\b\d+(?:-\d+){2,}\b/g, "<redacted-business-id>")
    .replace(/(?<!\d)\d{8,17}(?!\d)/g, "<redacted-business-id>")
    .replace(/\b(?:[A-Za-z0-9-]+\.)+(?:com|cn|net|org|io|internal|local|corp)(?::\d+)?(?:\/[^\s"'<>]*)?/gi, "<redacted-host>")
    .replace(/(?<![\w:])\/(?:private\/)?(?:Users|home|tmp|var|opt|Volumes)\/[^\s"'<>]+|[A-Za-z]:\\Users\\[^\s"'<>]+/g, "<redacted-path>");
  const codePoints = Array.from(redacted);
  if (codePoints.length <= maxChars) return redacted;
  return `${codePoints.slice(0, maxChars).join("")}…`;
}

function* walkJsonl(root) {
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const target = path.join(root, entry.name);
    if (entry.isDirectory()) yield* walkJsonl(target);
    else if (entry.isFile() && entry.name.endsWith(".jsonl")) yield target;
  }
}

function printHelp() {
  process.stdout.write(`Usage:
  node extract-session-evidence.mjs [options]

Options:
  --root <path>          Scan a session root; repeat for multiple roots.
  --all-user-messages   Emit every user message instead of correction candidates.
  --include-realtime    Include realtime voice sessions.
  --include-subagents   Include child sessions (both metadata layouts).
  --tool-errors-only    Emit call-linked error categories and script names, no message/output text.
  --format json|jsonl   Output format; default json.
  --max-chars <number>  Per text field limit; default 1200.
  --help                Show this help.

The output is evidence discovery only. A matched message is not a confirmed skill defect
until its preceding action, task scope, and actual runtime evidence are reviewed.
`);
}
