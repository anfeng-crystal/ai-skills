#!/usr/bin/env node

/**
 * Pull the skills repository, install active skills into the host home, and
 * run the repo doctor. This is the routine update entrypoint for other hosts.
 */

import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const ACTIVE_ROOT = path.resolve(SCRIPT_DIR, "..");

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}

export function parseArgs(argv, env = process.env) {
  const parsed = {
    home: path.resolve(env.AI_HOST_HOME || os.homedir()),
    tools: [],
    skills: [],
    runDoctor: true,
    pull: true,
    dryRun: false,
    help: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    switch (token) {
      case "--home":
        parsed.home = path.resolve(requiredValue(argv, ++index, token));
        break;
      case "--tool":
        parsed.tools.push(requiredValue(argv, ++index, token));
        break;
      case "--skill":
        parsed.skills.push(requiredValue(argv, ++index, token));
        break;
      case "--skip-doctor":
        parsed.runDoctor = false;
        break;
      case "--no-pull":
        parsed.pull = false;
        break;
      case "--dry-run":
        parsed.dryRun = true;
        break;
      case "--help":
      case "-h":
        parsed.help = true;
        break;
      default:
        throw new Error(`Unknown argument: ${token}`);
    }
  }

  return parsed;
}

export function buildPlan(options) {
  const commands = [];

  if (options.pull) {
    commands.push({
      label: "Pull latest skills",
      command: "git",
      args: ["pull", "--ff-only"],
      cwd: options.gitRoot,
    });
  }

  commands.push({
    label: "Install skills",
    command: process.execPath,
    args: [
      path.join(options.activeRoot, "install.mjs"),
      "--home",
      options.home,
      ...repeatArgs("--tool", options.tools),
      ...repeatArgs("--skill", options.skills),
    ],
    cwd: options.activeRoot,
  });

  if (options.runDoctor) {
    commands.push({
      label: "Run doctor",
      command: process.execPath,
      args: [
        path.join(options.activeRoot, "scripts/doctor.mjs"),
        "--source-root",
        options.activeRoot,
        "--home",
        options.home,
      ],
      cwd: options.activeRoot,
    });
  }

  return {
    activeRoot: options.activeRoot,
    gitRoot: options.gitRoot,
    dryRun: Boolean(options.dryRun),
    commands,
  };
}

function main() {
  try {
    const options = parseArgs(process.argv.slice(2));
    if (options.help) {
      printHelp();
      process.exit(0);
    }

    const gitRoot = findGitRoot(ACTIVE_ROOT);
    if (options.pull && !gitRoot) {
      throw new Error(
        "sync-and-install requires a Git checkout. Use --no-pull for archive installs.",
      );
    }

    const plan = buildPlan({
      ...options,
      activeRoot: ACTIVE_ROOT,
      gitRoot: gitRoot || ACTIVE_ROOT,
    });

    printPlan(plan);
    if (plan.dryRun) {
      return;
    }

    for (const command of plan.commands) {
      runCommand(command);
    }

    printCurrentRevision(plan.gitRoot);
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

function requiredValue(argv, index, token) {
  const value = argv[index];
  if (!value || value.startsWith("--")) {
    throw new Error(`${token} requires a value`);
  }
  return value;
}

function repeatArgs(flag, values) {
  return values.flatMap((value) => [flag, value]);
}

function findGitRoot(startDir) {
  const result = spawnSync("git", ["-C", startDir, "rev-parse", "--show-toplevel"], {
    encoding: "utf8",
  });
  if (result.status !== 0) {
    return null;
  }
  return result.stdout.trim() || null;
}

function printPlan(plan) {
  console.log(`Active skills: ${plan.activeRoot}`);
  console.log(`Git root: ${plan.gitRoot}`);
  console.log(plan.dryRun ? "Mode: dry-run" : "Mode: apply");
  console.log("");
  for (const command of plan.commands) {
    console.log(`== ${command.label} ==`);
    console.log(formatCommand(command));
    console.log("");
  }
}

function runCommand(command) {
  const result = spawnSync(command.command, command.args, {
    cwd: command.cwd,
    stdio: "inherit",
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function printCurrentRevision(gitRoot) {
  const result = spawnSync("git", ["-C", gitRoot, "rev-parse", "--short", "HEAD"], {
    encoding: "utf8",
  });
  if (result.status === 0) {
    console.log(`Current skills revision: ${result.stdout.trim()}`);
  }
}

function formatCommand(command) {
  return [`cd ${quoteArg(command.cwd)}`, [command.command, ...command.args].map(quoteArg).join(" ")].join(
    " && ",
  );
}

function quoteArg(value) {
  if (/^[A-Za-z0-9_./:=@+-]+$/.test(value)) {
    return value;
  }
  return JSON.stringify(value);
}

function printHelp() {
  console.log(`Usage:
  node scripts/sync-and-install.mjs [options]

Pull the Git checkout, install active skills into the host home, and run doctor.

Options:
  --home <path>      Target host home. Defaults to AI_HOST_HOME or OS home.
  --tool <name>      Limit install to a host tool; repeatable.
  --skill <name>     Limit install to a skill; repeatable.
  --skip-doctor      Skip the post-install doctor check.
  --no-pull          Do not run git pull; useful for archive installs.
  --dry-run          Print planned commands without running them.
  --help             Show this help.

Examples:
  node scripts/sync-and-install.mjs
  node scripts/sync-and-install.mjs --dry-run
  node scripts/sync-and-install.mjs --home "$HOME" --tool codex
`);
}
