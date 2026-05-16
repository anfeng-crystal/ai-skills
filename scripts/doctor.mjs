#!/usr/bin/env node

/**
 * Repo-level doctor that validates host wiring and optional runtime prerequisites
 * without mutating tracked files. It combines the per-skill dry-run checks into
 * one migration-friendly report for shared macOS/Linux environments.
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const FALLBACK_SOURCE_ROOT = path.join(SCRIPT_DIR, "..");

main();

function main() {
  try {
    const options = parseArgs(process.argv.slice(2));
    loadDotEnv(path.join(options.sourceRoot, ".env"));
    const loadedOptions = parseArgs(process.argv.slice(2));
    loadedOptions.envFile = path.join(loadedOptions.sourceRoot, ".env");
    const report = buildReport(loadedOptions);

    if (loadedOptions.json) {
      console.log(JSON.stringify(report, null, 2));
    } else {
      printText(report);
    }

    if (!report.ok) {
      process.exitCode = 2;
    }
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

function parseArgs(argv) {
  const parsed = {
    sourceRoot: path.resolve(process.env.AI_SKILLS_HOME || FALLBACK_SOURCE_ROOT),
    home: path.resolve(process.env.AI_HOST_HOME || os.homedir()),
    json: false,
    strictOptional: false,
    requireKingdeeKnowledge: false,
    requireYtDlp: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    switch (token) {
      case "--source-root":
        parsed.sourceRoot = path.resolve(argv[++index]);
        break;
      case "--home":
        parsed.home = path.resolve(argv[++index]);
        break;
      case "--json":
        parsed.json = true;
        break;
      case "--strict-optional":
        parsed.strictOptional = true;
        break;
      case "--require-kingdee-knowledge":
        parsed.requireKingdeeKnowledge = true;
        break;
      case "--require-yt-dlp":
        parsed.requireYtDlp = true;
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
  node scripts/doctor.mjs [options]

Options:
  --source-root <path>   Override skills source root
  --home <path>          Override target host home
  --json                 Emit JSON output
  --strict-optional      Treat optional skill prerequisites as errors
  --require-kingdee-knowledge
                         Require AI_KNOWLEDGE_ROOT for Kingdee workflows
  --require-yt-dlp       Require yt-dlp for union-search download workflows
  --help                 Show this help
`);
}

function buildReport(opts) {
  const commandChecks = {
    node: {
      available: true,
      version: process.version,
      major: Number(process.versions.node.split(".")[0]),
      minimumMajor: 22,
      ok: Number(process.versions.node.split(".")[0]) >= 22,
    },
    npx: inspectCommand("npx"),
    python3: (() => {
      const primary = inspectCommand("python3");
      if (primary.available) return primary;
      if (process.platform === "win32") return inspectCommand("python");
      return primary;
    })(),
    ytDlp: inspectCommand("yt-dlp"),
  };

  const linkAudit = inspectLinkAudit(opts.sourceRoot, opts.home);
  const npmDeps = inspectNpmDeps(opts.sourceRoot);
  const webAccess = inspectWebAccess(opts.sourceRoot);
  const knowledgeRoot = inspectKnowledgeRoot();
  const unionSearch = inspectUnionSearch(opts.sourceRoot);

  const errors = [];
  const warnings = [];

  if (!commandChecks.node.ok) {
    errors.push(`Node.js major version must be >= ${commandChecks.node.minimumMajor}`);
  }
  if (!commandChecks.npx.available) {
    errors.push("npx is required for playwright skill workflows");
  }
  if (!commandChecks.python3.available) {
    errors.push("python3 (or python on Windows) is required for Kingdee and multi-search workflows");
  }
  if (!knowledgeRoot.ok && (opts.strictOptional || opts.requireKingdeeKnowledge)) {
    errors.push(knowledgeRoot.message);
  }
  if (!linkAudit.ok) {
    warnings.push("host link audit reported conflicts");
  }
  if (!npmDeps.ok) {
    warnings.push('local npm dependencies are incomplete; run "node scripts/npm-deps.mjs install" while online');
  }
  if (!knowledgeRoot.ok && !(opts.strictOptional || opts.requireKingdeeKnowledge)) {
    warnings.push(`${knowledgeRoot.message} Kingdee knowledge-backed skills are optional.`);
  }
  if (!commandChecks.ytDlp.available && (opts.strictOptional || opts.requireYtDlp)) {
    errors.push("yt-dlp is required when union-search download flows are enabled");
  }
  if (!commandChecks.ytDlp.available && !(opts.strictOptional || opts.requireYtDlp)) {
    warnings.push("yt-dlp is optional and only required for union-search download flows");
  }
  if (!webAccess.ok) {
    warnings.push("web-access dry-run reported degraded prerequisites");
  }
  if (unionSearch.cookies.configured && !unionSearch.cookies.exists) {
    warnings.push("YTDLP_COOKIES_FILE is configured but does not exist");
  }

  return {
    scannedAt: new Date().toISOString(),
    sourceRoot: opts.sourceRoot,
    home: opts.home,
    envFile: opts.envFile,
    strictOptional: opts.strictOptional,
    ok: errors.length === 0,
    errors,
    warnings,
    checks: {
      commands: commandChecks,
      linkAudit,
      npmDeps,
      webAccess,
      knowledgeRoot,
      unionSearch,
    },
  };
}

function inspectCommand(command) {
  const resolvedPath = resolveCommand(command);
  const available = Boolean(resolvedPath);
  let version = null;

  if (available) {
    const versionResult = spawnSync(resolvedPath, ["--version"], { encoding: "utf8" });
    version = ((versionResult.stdout || versionResult.stderr || "").split(/\r?\n/)[0] || "").trim() || null;
  }

  return {
    available,
    path: resolvedPath || null,
    version,
  };
}

function resolveCommand(command) {
  if (command.includes("/") || command.includes("\\")) {
    return isExecutable(command) ? path.resolve(command) : null;
  }

  const pathEntries = String(process.env.PATH || "")
    .split(path.delimiter)
    .filter(Boolean);
  const extensions = process.platform === "win32"
    ? String(process.env.PATHEXT || ".COM;.EXE;.BAT;.CMD")
        .split(";")
        .filter(Boolean)
    : [""];
  const names = process.platform === "win32" && path.extname(command)
    ? [command]
    : extensions.map((extension) => `${command}${extension.toLowerCase()}`).concat(
        extensions.map((extension) => `${command}${extension.toUpperCase()}`),
      );

  for (const entry of pathEntries) {
    for (const name of names) {
      const candidate = path.join(entry, name);
      if (isExecutable(candidate)) {
        return candidate;
      }
    }
  }
  return null;
}

function isExecutable(filePath) {
  try {
    fs.accessSync(filePath, fs.constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function loadDotEnv(filePath) {
  if (!fs.existsSync(filePath)) {
    return;
  }

  const content = fs.readFileSync(filePath, "utf8");
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const match = trimmed.match(/^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) {
      continue;
    }

    const [, key, rawValue] = match;
    if (process.env[key] !== undefined) {
      continue;
    }

    process.env[key] = normalizeEnvValue(rawValue);
  }
}

function normalizeEnvValue(value) {
  const trimmed = String(value).trim();
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function inspectLinkAudit(sourceRoot, home) {
  const scriptPath = path.join(sourceRoot, "skills/meta/skill-installer/scripts/sync-links.mjs");
  const result = spawnSync(process.execPath, [scriptPath, "--source-root", sourceRoot, "--home", home, "--json"], {
    encoding: "utf8",
  });

  if (!result.stdout) {
    return {
      ok: false,
      exitCode: result.status ?? 1,
      error: (result.stderr || "link audit did not produce JSON output").trim(),
    };
  }

  try {
    const payload = JSON.parse(result.stdout);
    const conflicts = payload.records.filter((record) =>
      [
        "real_path_conflict",
        "external_symlink_conflict",
        "hermes_local_shadow_conflict",
        "missing_target_root",
      ].includes(record.status),
    );

    return {
      ok: Boolean(payload.ok),
      exitCode: result.status ?? 0,
      summary: payload.summary,
      conflicts: conflicts.map((record) => ({
        tool: record.tool,
        skill: record.skill,
        status: record.status,
        reason: record.reason,
        targetPath: record.targetPath,
      })),
    };
  } catch (error) {
    return {
      ok: false,
      exitCode: result.status ?? 1,
      error: error instanceof Error ? error.message : String(error),
      rawStdout: result.stdout.trim(),
      rawStderr: (result.stderr || "").trim(),
    };
  }
}

function inspectWebAccess(sourceRoot) {
  const scriptPath = path.join(sourceRoot, "skills/automation/web-access/scripts/check-deps.mjs");
  const result = spawnSync(process.execPath, [scriptPath, "--dry-run", "--json"], { encoding: "utf8" });
  if (!result.stdout) {
    return {
      ok: false,
      exitCode: result.status ?? 1,
      error: (result.stderr || "web-access dry-run did not produce JSON output").trim(),
    };
  }

  try {
    const payload = JSON.parse(result.stdout);
    return {
      ok: Boolean(payload.ok),
      exitCode: result.status ?? 0,
      dryRun: true,
      plan: payload.plan,
    };
  } catch (error) {
    return {
      ok: false,
      exitCode: result.status ?? 1,
      error: error instanceof Error ? error.message : String(error),
      rawStdout: result.stdout.trim(),
      rawStderr: (result.stderr || "").trim(),
    };
  }
}

function inspectKnowledgeRoot() {
  const configuredPath = (process.env.AI_KNOWLEDGE_ROOT || "").trim();
  if (!configuredPath) {
    return {
      ok: false,
      configured: false,
      path: null,
      expectedConfigTable: "AI_KNOWLEDGE_ROOT/kingdee/cosmic/projects/config-table.md",
      requiredBy: ["kingdee-cosmic", "kingdee-metadata-analyzer"],
      message: "AI_KNOWLEDGE_ROOT is not configured; Kingdee knowledge-backed skills will fail early.",
    };
  }

  const resolvedPath = path.resolve(configuredPath);
  const configTablePath = path.join(resolvedPath, "kingdee/cosmic/projects/config-table.md");
  const exists = fs.existsSync(configTablePath);

  return {
    ok: exists,
    configured: true,
    path: resolvedPath,
    expectedConfigTable: configTablePath,
    requiredBy: ["kingdee-cosmic", "kingdee-metadata-analyzer"],
    message: exists
      ? "AI_KNOWLEDGE_ROOT looks valid."
      : `AI_KNOWLEDGE_ROOT is set but missing ${configTablePath}.`,
  };
}

function inspectUnionSearch(sourceRoot) {
  const unionRoot = path.join(sourceRoot, "skills/meta/multi-search");
  const cookiesPath = (process.env.YTDLP_COOKIES_FILE || "").trim();
  const nestedGitDir = path.join(unionRoot, ".git");

  return {
    root: unionRoot,
    nestedGitRepo: fs.existsSync(nestedGitDir),
    requirementsFile: fs.existsSync(path.join(unionRoot, "requirements.txt")),
    packageJson: fs.existsSync(path.join(unionRoot, "package.json")),
    cookies: {
      configured: Boolean(cookiesPath),
      path: cookiesPath || null,
      exists: cookiesPath ? fs.existsSync(path.resolve(cookiesPath)) : false,
    },
  };
}

function inspectNpmDeps(sourceRoot) {
  const script = path.join(sourceRoot, "scripts/npm-deps.mjs");
  if (!fs.existsSync(script)) {
    return {
      ok: true,
      available: false,
      exitCode: 0,
      message: "npm dependency checker is not available.",
    };
  }

  const result = spawnSync(process.execPath, [script, "check"], {
    cwd: sourceRoot,
    encoding: "utf8",
  });

  return {
    ok: result.status === 0,
    available: true,
    exitCode: result.status,
    stdout: (result.stdout || "").trim(),
    stderr: (result.stderr || "").trim(),
  };
}

function printText(report) {
  console.log(`Source root: ${report.sourceRoot}`);
  console.log(`Host home: ${report.home}`);
  console.log(`Overall: ${report.ok ? "ok" : "needs_attention"}`);
  console.log("");
  console.log("Commands:");
  console.log(`- node: ${report.checks.commands.node.version} (ok=${report.checks.commands.node.ok ? "yes" : "no"})`);
  console.log(`- npx: ${report.checks.commands.npx.available ? report.checks.commands.npx.path : "missing"}`);
  console.log(`- python3: ${report.checks.commands.python3.available ? report.checks.commands.python3.path : "missing"}`);
  console.log(`- yt-dlp: ${report.checks.commands.ytDlp.available ? report.checks.commands.ytDlp.path : "missing"}`);
  console.log("");
  console.log("Link audit:");
  if (report.checks.linkAudit.summary) {
    console.log(`- ok: ${report.checks.linkAudit.ok ? "yes" : "no"}`);
    console.log(`- summary: ${JSON.stringify(report.checks.linkAudit.summary)}`);
    console.log(`- conflicts: ${report.checks.linkAudit.conflicts.length}`);
  } else {
    console.log(`- error: ${report.checks.linkAudit.error}`);
  }
  console.log("");
  console.log("Npm dependencies:");
  console.log(`- ok: ${report.checks.npmDeps.ok ? "yes" : "no"}`);
  if (report.checks.npmDeps.stdout) {
    console.log(report.checks.npmDeps.stdout);
  }
  console.log("");
  console.log("Web access:");
  if (report.checks.webAccess.plan) {
    console.log(`- ok: ${report.checks.webAccess.ok ? "yes" : "no"}`);
    console.log(`- planned host: ${report.checks.webAccess.plan.host}:${report.checks.webAccess.plan.port}`);
  } else {
    console.log(`- error: ${report.checks.webAccess.error}`);
  }
  console.log("");
  console.log("Knowledge root:");
  console.log(`- configured: ${report.checks.knowledgeRoot.configured ? "yes" : "no"}`);
  console.log(`- message: ${report.checks.knowledgeRoot.message}`);
  console.log("");
  console.log("Union search:");
  console.log(`- nested git repo: ${report.checks.unionSearch.nestedGitRepo ? "yes" : "no"}`);
  console.log(`- YTDLP_COOKIES_FILE: ${report.checks.unionSearch.cookies.configured ? report.checks.unionSearch.cookies.path : "not_set"}`);

  if (report.errors.length > 0) {
    console.log("");
    console.log("Errors:");
    for (const error of report.errors) {
      console.log(`- ${error}`);
    }
  }

  if (report.warnings.length > 0) {
    console.log("");
    console.log("Warnings:");
    for (const warning of report.warnings) {
      console.log(`- ${warning}`);
    }
  }
}
