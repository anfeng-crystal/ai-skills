#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_SOURCE_ROOT = path.resolve(SCRIPT_DIR, "../../..");
const CANONICAL_RESULT_FIELDS = [
  "timestamp",
  "commit",
  "skill",
  "prompt_id",
  "baseline_score",
  "old_score",
  "new_score",
  "avg_skill_delta",
  "eval_mode",
  "model_set",
  "status",
  "notes",
];
const LEGACY_RESULT_FIELDS = [
  "timestamp",
  "commit",
  "skill",
  "baseline_score",
  "old_score",
  "new_score",
  "status",
  "dimension",
  "note",
  "eval_mode",
  "model_set",
  "avg_skill_delta",
];
const PROMPT_FIELDS = ["id", "prompt", "expected", "eval_focus", "baseline_risk"];
const TEXT_EXTENSIONS = new Set([
  ".css",
  ".html",
  ".ini",
  ".java",
  ".js",
  ".json",
  ".jsx",
  ".md",
  ".mjs",
  ".properties",
  ".py",
  ".sh",
  ".ts",
  ".tsx",
  ".tsv",
  ".txt",
  ".xml",
  ".yaml",
  ".yml",
]);

main();

function main() {
  const options = parseArgs(process.argv.slice(2));
  const report = buildReport(options);

  if (options.json) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    printReport(report);
  }

  if (!report.ok) {
    process.exitCode = 1;
  }
}

function parseArgs(argv) {
  const parsed = {
    sourceRoot: path.resolve(process.env.AI_SKILLS_HOME || DEFAULT_SOURCE_ROOT),
    json: false,
    strictResults: false,
    includeIncoming: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    switch (token) {
      case "--source-root":
        parsed.sourceRoot = path.resolve(argv[++index]);
        break;
      case "--json":
        parsed.json = true;
        break;
      case "--strict-results":
        parsed.strictResults = true;
        break;
      case "--include-incoming":
        parsed.includeIncoming = true;
        break;
      case "--help":
      case "-h":
        printHelp();
        process.exit(0);
      default:
        throw new Error(`Unknown argument: ${token}`);
    }
  }

  return parsed;
}

function printHelp() {
  console.log(`Usage:
  node skills/meta/darwin-skill/scripts/validate-skill-assets.mjs [options]

Options:
  --source-root <path>   Skills source root. Defaults to AI_SKILLS_HOME or the current source tree.
  --json                 Emit JSON.
  --strict-results       Treat legacy results.tsv headers as errors.
  --include-incoming     Include incoming/ skills in the scan.
  --help                 Show this help.
`);
}

function buildReport(options) {
  const errors = [];
  const warnings = [];
  const skills = findSkills(options.sourceRoot, options.includeIncoming);

  if (skills.length === 0) {
    errors.push({
      code: "no_skills_found",
      message: `No SKILL.md files found under ${options.sourceRoot}`,
    });
  }

  for (const skill of skills) {
    checkPromptAsset(skill, errors);
    checkResultAsset(skill, options.strictResults, errors, warnings);
  }

  checkPortableText(options.sourceRoot, errors);

  return {
    ok: errors.length === 0,
    sourceRoot: options.sourceRoot,
    strictResults: options.strictResults,
    summary: {
      skills: skills.length,
      errors: errors.length,
      warnings: warnings.length,
    },
    errors,
    warnings,
  };
}

function findSkills(sourceRoot, includeIncoming) {
  if (!fs.existsSync(sourceRoot)) return [];

  const skills = [];
  for (const category of fs.readdirSync(sourceRoot).sort()) {
    if (category.startsWith(".")) continue;
    if (!includeIncoming && category === "incoming") continue;

    const categoryDir = path.join(sourceRoot, category);
    if (!isDirectory(categoryDir)) continue;

    for (const name of fs.readdirSync(categoryDir).sort()) {
      const dir = path.join(categoryDir, name);
      const skillPath = path.join(dir, "SKILL.md");
      if (isDirectory(dir) && fs.existsSync(skillPath)) {
        skills.push({ category, name, dir, skillPath });
      }
    }
  }
  return skills;
}

function checkPromptAsset(skill, errors) {
  const file = path.join(skill.dir, "test-prompts.json");
  if (!fs.existsSync(file)) {
    errors.push(issue(skill, "missing_test_prompts", "Missing test-prompts.json"));
    return;
  }

  let prompts;
  try {
    prompts = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (error) {
    errors.push(issue(skill, "invalid_test_prompts_json", `Invalid JSON: ${error.message}`));
    return;
  }

  if (!Array.isArray(prompts) || prompts.length === 0) {
    errors.push(issue(skill, "empty_test_prompts", "test-prompts.json must be a non-empty array"));
    return;
  }

  const seenIds = new Set();
  prompts.forEach((prompt, index) => {
    if (!prompt || typeof prompt !== "object" || Array.isArray(prompt)) {
      errors.push(issue(skill, "invalid_prompt_entry", `Prompt #${index + 1} must be an object`));
      return;
    }

    for (const field of PROMPT_FIELDS) {
      if (typeof prompt[field] !== "string" || prompt[field].trim() === "") {
        errors.push(issue(skill, "missing_prompt_field", `Prompt #${index + 1} missing ${field}`));
      }
    }

    if (typeof prompt.id === "string") {
      if (seenIds.has(prompt.id)) {
        errors.push(issue(skill, "duplicate_prompt_id", `Duplicate prompt id: ${prompt.id}`));
      }
      seenIds.add(prompt.id);
    }
  });
}

function checkResultAsset(skill, strictResults, errors, warnings) {
  const file = path.join(skill.dir, "results.tsv");
  if (!fs.existsSync(file)) {
    errors.push(issue(skill, "missing_results", "Missing results.tsv"));
    return;
  }

  const lines = fs.readFileSync(file, "utf8").split(/\r?\n/).filter((line) => line.trim() !== "");
  if (lines.length < 2) {
    errors.push(issue(skill, "empty_results", "results.tsv must contain a header and at least one data row"));
    return;
  }

  const headers = lines[0].split("\t");
  const resultMode = classifyResultHeader(headers);
  if (resultMode === "unknown") {
    errors.push(issue(skill, "unsupported_results_header", `Unsupported results.tsv header: ${lines[0]}`));
    return;
  }

  if (resultMode !== "canonical") {
    const target = strictResults ? errors : warnings;
    target.push(issue(skill, "legacy_results_header", `Non-canonical results.tsv header: ${resultMode}`));
  }

  const evalModeIndex = headers.indexOf("eval_mode");
  for (let index = 1; index < lines.length; index += 1) {
    const values = lines[index].split("\t");
    if (values.length !== headers.length) {
      errors.push(issue(skill, "results_column_mismatch", `Row ${index + 1} has ${values.length} columns; expected ${headers.length}`));
      continue;
    }

    if (resultMode === "canonical") {
      for (const field of CANONICAL_RESULT_FIELDS) {
        const fieldIndex = headers.indexOf(field);
        if (fieldIndex < 0 || values[fieldIndex].trim() === "") {
          errors.push(issue(skill, "empty_result_field", `Row ${index + 1} missing ${field}`));
        }
      }
    }

    if (evalModeIndex >= 0 && !["dry_run", "full_test"].includes(values[evalModeIndex])) {
      errors.push(issue(skill, "invalid_eval_mode", `Row ${index + 1} eval_mode must be dry_run or full_test`));
    }
  }
}

function classifyResultHeader(headers) {
  if (containsAll(headers, CANONICAL_RESULT_FIELDS)) return "canonical";
  if (containsAll(headers, LEGACY_RESULT_FIELDS)) return "legacy";
  if (headers.includes("skill") && headers.includes("eval_mode") && (headers.includes("notes") || headers.includes("note"))) {
    return "custom";
  }
  return "unknown";
}

function checkPortableText(sourceRoot, errors) {
  const forbidden = buildForbiddenPatterns();
  for (const file of walkTextFiles(sourceRoot)) {
    const text = fs.readFileSync(file, "utf8");
    for (const pattern of forbidden) {
      const match = text.match(pattern.re);
      if (match) {
        errors.push({
          skill: null,
          path: file,
          code: "non_portable_text",
          message: `Matched ${pattern.name}: ${match[0]}`,
        });
      }
    }
  }
}

function buildForbiddenPatterns() {
  const patterns = [
    { name: "example_user_home", re: /\/Users\/(?:anfeng|you)\b/g },
    { name: "linux_home_literal", re: /\/home\/[^/\s]+/g },
    { name: "windows_user_home_literal", re: /C:\\Users\\/gi },
    { name: "tilde_ai_skills", re: /~[\\/]+AI[\\/]+skills/g },
    { name: "old_active_root", re: /AI[\\/]+skills[\\/]+active|skills[\\/]+active/g },
    { name: "old_active_words", re: new RegExp(["active" + " skills", "active " + "目录", "active " + "源"].join("|"), "gi") },
  ];

  const home = process.env.HOME || process.env.USERPROFILE;
  if (home) {
    patterns.push({ name: "current_host_home", re: new RegExp(escapeRegExp(path.normalize(home)), "g") });
  }

  return patterns;
}

function* walkTextFiles(root) {
  if (!fs.existsSync(root)) return;
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    if (entry.name.startsWith(".") || entry.name === "node_modules") continue;

    const fullPath = path.join(root, entry.name);
    if (entry.isDirectory()) {
      yield* walkTextFiles(fullPath);
    } else if (entry.isFile() && TEXT_EXTENSIONS.has(path.extname(entry.name))) {
      yield fullPath;
    }
  }
}

function containsAll(values, required) {
  return required.every((field) => values.includes(field));
}

function isDirectory(target) {
  try {
    return fs.statSync(target).isDirectory();
  } catch {
    return false;
  }
}

function issue(skill, code, message) {
  return {
    skill: `${skill.category}/${skill.name}`,
    path: skill.dir,
    code,
    message,
  };
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function printReport(report) {
  console.log(`Skill asset validation: ${report.ok ? "PASS" : "FAIL"}`);
  console.log(`Source root: ${report.sourceRoot}`);
  console.log(`Skills: ${report.summary.skills}  Errors: ${report.summary.errors}  Warnings: ${report.summary.warnings}`);

  if (report.errors.length > 0) {
    console.log("\nErrors:");
    for (const item of report.errors) {
      console.log(`  - ${formatIssue(item)}`);
    }
  }

  if (report.warnings.length > 0) {
    console.log("\nWarnings:");
    for (const item of report.warnings) {
      console.log(`  - ${formatIssue(item)}`);
    }
  }
}

function formatIssue(item) {
  const scope = item.skill || item.path;
  return `${scope}: ${item.code}: ${item.message}`;
}
