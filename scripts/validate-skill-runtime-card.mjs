#!/usr/bin/env node

/**
 * Validate runtime-card semantics that generic frontmatter checks cannot cover.
 * The validator is host-neutral and accepts skill directories or SKILL.md files.
 */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const args = process.argv.slice(2);
const json = args.includes("--json");
const strict = args.includes("--strict");
const newSkill = args.includes("--new-skill");
const requested = [];

for (let index = 0; index < args.length; index += 1) {
  if (args[index] === "--path") {
    const value = args[index + 1];
    if (!value) failUsage("--path requires a file or directory");
    requested.push(value);
    index += 1;
  } else if (!["--json", "--strict", "--new-skill"].includes(args[index])) {
    failUsage(`unknown argument: ${args[index]}`);
  }
}

if (requested.length === 0) failUsage("provide at least one --path");

const results = requested.map(validatePath);
const errors = results.flatMap((result) => result.errors.map((message) => ({ path: result.path, message })));
const warnings = results.flatMap((result) => result.warnings.map((message) => ({ path: result.path, message })));

if (json) {
  process.stdout.write(`${JSON.stringify({ results, errors, warnings }, null, 2)}\n`);
} else {
  for (const result of results) {
    const status = result.errors.length === 0 && (!strict || result.warnings.length === 0) ? "PASS" : "FAIL";
    process.stdout.write(`${status} ${result.path}\n`);
    for (const message of result.errors) process.stdout.write(`  error: ${message}\n`);
    for (const message of result.warnings) process.stdout.write(`  warning: ${message}\n`);
  }
}

if (errors.length > 0 || (strict && warnings.length > 0)) process.exit(1);

function validatePath(input) {
  const absolute = path.resolve(input);
  const skillFile = fs.existsSync(absolute) && fs.statSync(absolute).isDirectory()
    ? path.join(absolute, "SKILL.md")
    : absolute;
  const result = { path: skillFile, errors: [], warnings: [] };

  if (!fs.existsSync(skillFile)) {
    result.errors.push("SKILL.md does not exist");
    return result;
  }

  const content = fs.readFileSync(skillFile, "utf8").replace(/\r\n/g, "\n");
  const frontmatter = content.match(/^---\n([\s\S]*?)\n---(?:\n|$)/);
  if (newSkill) {
    if (!frontmatter) {
      result.errors.push("new skill requires YAML frontmatter");
    } else {
      const keys = frontmatter[1]
        .split("\n")
        .map((line) => line.match(/^([A-Za-z][A-Za-z0-9_-]*):(?:\s|$)/)?.[1])
        .filter(Boolean);
      const unexpected = [...new Set(keys.filter((key) => !["name", "description"].includes(key)))];
      const missing = ["name", "description"].filter((key) => !keys.includes(key));
      if (unexpected.length > 0) result.errors.push(`new skill frontmatter has unsupported keys: ${unexpected.join(", ")}`);
      if (missing.length > 0) result.errors.push(`new skill frontmatter is missing keys: ${missing.join(", ")}`);
    }
  }
  const body = content.replace(/^---\n[\s\S]*?\n---\n?/, "");
  const headings = [...body.matchAll(/^##\s+(.+)$/gm)].map((match) => match[1].trim());

  requireHeading(headings, result, /触发|路由|when|trigger|rout(?:e|ing)/i, "trigger/routing");
  requireHeading(headings, result, /契约|模式|输入|contract|mode|input/i, "contract/modes");
  requireHeading(headings, result, /工作流|流程|workflow/i, "workflow");
  requireHeading(headings, result, /门禁|失败|guardrail|failure/i, "gates/failure");
  requireHeading(headings, result, /输出|output/i, "output");

  const manualHeadings = headings.filter((heading) => /背景|产品介绍|为什么|快速入门|教程|FAQ|常见问题|最佳实践|about|introduction|tutorial/i.test(heading));
  if (manualHeadings.length > 0) result.errors.push(`human-manual headings: ${manualHeadings.join(", ")}`);

  const placeholderPatterns = [/\bTODO\b/i, /\bTBD\b/i, /\[填写/, /步骤一|步骤二|步骤三/, /描述何时使用/, /关键约束条件/];
  for (const pattern of placeholderPatterns) {
    if (pattern.test(body)) result.errors.push(`unresolved placeholder: ${pattern}`);
  }

  const dangerousPatterns = [
    [/\/(?:Users|home)\/[^\s`]+/, "hard-coded user path"],
    [/[A-Za-z]:\\Users\\[^\s`]+/, "hard-coded Windows user path"],
    [/\brm\s+-rf\b/, "destructive rm -rf"],
    [/\bgit\s+reset\s+--hard\b/, "destructive git reset --hard"],
    [/\b(?:curl|wget)\b[^\n|]*\|\s*(?:sh|bash)\b/, "remote pipe execution"],
  ];
  for (const [pattern, label] of dangerousPatterns) {
    const unsafeLines = body.split("\n").filter((line) => {
      if (!pattern.test(line)) return false;
      return !/禁止|不得|不要|风险|信号|检测|命中|审查|破坏性|远程执行|block|拒绝|不使用/.test(line);
    });
    if (unsafeLines.length > 0) result.errors.push(label);
  }

  const vague = /视情况|酌情|谨慎处理|适当|根据需要|按需|必要时|尽量/;
  for (const [lineIndex, line] of body.split("\n").entries()) {
    if (!vague.test(line)) continue;
    if (!/当|如果|只有|除非|否则|前提|失败|缺少|出现|超过|低于|用于|读取/.test(line)) {
      result.warnings.push(`line ${lineIndex + 1}: vague instruction without an observable condition`);
    }
  }

  const markdownLinks = [...body.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)].map((match) => match[1]);
  const backtickRefs = [...body.matchAll(/`((?:references|scripts|assets)\/[^`\s]+)`/g)].map((match) => match[1]);
  for (const reference of [...markdownLinks, ...backtickRefs]) {
    if (/^(?:https?:|#)/.test(reference) || /[<>*]/.test(reference)) continue;
    const clean = reference.split("#", 1)[0];
    const target = path.resolve(path.dirname(skillFile), clean);
    if (!fs.existsSync(target)) result.errors.push(`missing local reference: ${reference}`);
  }

  if (body.split("\n").length > 500) result.errors.push("SKILL.md body exceeds 500 lines");
  return result;
}

function requireHeading(headings, result, pattern, label) {
  if (!headings.some((heading) => pattern.test(heading))) result.errors.push(`missing ${label} section`);
}

function failUsage(message) {
  process.stderr.write(`${message}\nusage: validate-skill-runtime-card.mjs --path <skill> [--path <skill> ...] [--new-skill] [--json] [--strict]\n`);
  process.exit(2);
}
