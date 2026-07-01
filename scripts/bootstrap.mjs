#!/usr/bin/env node

/**
 * Cross-platform bootstrap for auditing and materializing active skill links.
 */

import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPT_DIR, "..");
const DEFAULT_SOURCE_ROOT = path.join(REPO_ROOT, "skills");

const options = parseArgs(process.argv.slice(2));

if (options.help) {
  printHelp();
  process.exit(0);
}

const syncArgs = [
  path.join(REPO_ROOT, "skills/meta/skill-installer/bin/skill-installer.mjs"),
  "--source-root",
  options.sourceRoot,
  "--home",
  options.home,
];
for (const tool of options.tools) {
  syncArgs.push("--tool", tool);
}
for (const skill of options.skills) {
  syncArgs.push("--skill", skill);
}
if (options.apply) {
  syncArgs.push("--apply");
}

console.log("== Link audit ==");
const syncResult = spawnSync(process.execPath, syncArgs, { stdio: "inherit" });
if (syncResult.status) {
  process.exit(syncResult.status);
}

if (!options.runDoctor) {
  process.exit(0);
}

const doctorArgs = [
  path.join(REPO_ROOT, "scripts/doctor.mjs"),
  "--source-root",
  REPO_ROOT,
  "--home",
  options.home,
];
if (options.doctorJson) {
  doctorArgs.push("--json");
}

console.log("");
console.log("== Doctor ==");
const doctorResult = spawnSync(process.execPath, doctorArgs, { stdio: "inherit" });
if (doctorResult.status) {
  process.exit(doctorResult.status);
}

function parseArgs(argv) {
  const parsed = {
    apply: false,
    sourceRoot: path.resolve(process.env.AI_SKILLS_HOME || DEFAULT_SOURCE_ROOT),
    home: path.resolve(process.env.AI_HOST_HOME || os.homedir()),
    runDoctor: true,
    doctorJson: false,
    tools: [],
    skills: [],
    help: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    switch (token) {
      case "--apply":
        parsed.apply = true;
        break;
      case "--home":
        parsed.home = path.resolve(requiredValue(argv, ++index, token));
        break;
      case "--source-root":
        parsed.sourceRoot = path.resolve(requiredValue(argv, ++index, token));
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
      case "--doctor-json":
        parsed.doctorJson = true;
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

function requiredValue(argv, index, token) {
  const value = argv[index];
  if (!value || value.startsWith("--")) {
    throw new Error(`${token} requires a value`);
  }
  return value;
}

function printHelp() {
  console.log(`Usage:
  node scripts/bootstrap.mjs [options]

Options:
  --apply            Materialize planned links after dry-run review
  --source-root <path>
                     Skills source root (default: checkout skills/ or AI_SKILLS_HOME)
  --home <path>      Override host home (default: AI_HOST_HOME or OS home)
  --tool <name>      Limit to a host tool; repeatable
  --skill <name>     Limit to a skill; repeatable
  --skip-doctor      Skip the repo-level doctor pass
  --doctor-json      Emit doctor results as JSON
  --help             Show this help
`);
}
