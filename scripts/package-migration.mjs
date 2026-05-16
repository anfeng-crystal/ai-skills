#!/usr/bin/env node

/**
 * Cross-platform migration archive creator.
 * Replaces package-migration.sh with pure Node.js + crypto checksum.
 *
 * Usage:
 *   node scripts/package-migration.mjs [--output-dir PATH] [--name NAME] [--include-submodules]
 */

import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(SCRIPT_DIR, "..");

const args = process.argv.slice(2);
if (args.includes("--help") || args.includes("-h")) {
  printHelp();
  process.exit(0);
}

let outputDir = path.join(ROOT_DIR, "dist");
let archiveName = `skills-active-migration-${dateStamp()}`;
let includeSubmodules = false;

for (let i = 0; i < args.length; i++) {
  switch (args[i]) {
    case "--output-dir":
      outputDir = path.resolve(args[++i]);
      break;
    case "--name":
      archiveName = args[++i];
      break;
    case "--include-submodules":
      includeSubmodules = true;
      break;
    default:
      console.error(`Unknown argument: ${args[i]}`);
      printHelp();
      process.exit(1);
  }
}

mkdirSync(outputDir, { recursive: true });

const parentDir = path.dirname(ROOT_DIR);
const rootName = path.basename(ROOT_DIR);
const archivePath = path.join(outputDir, `${archiveName}.tar.gz`);
const checksumPath = `${archivePath}.sha256`;

const excludes = [
  "--exclude=*/.git",
  "--exclude=*/.git/*",
  "--exclude=*/.DS_Store",
  "--exclude=*/__pycache__",
  "--exclude=*/__pycache__/*",
  "--exclude=*.pyc",
  "--exclude=*.pyo",
  "--exclude=*/dist",
  "--exclude=*/dist/*",
  "--exclude=*/.env",
  "--exclude=*/.env.local",
  "--exclude=*/.env.*.local",
  "--exclude=*/.venv",
  "--exclude=*/.venv/*",
  "--exclude=*/node_modules",
  "--exclude=*/node_modules/*",
  "--exclude=*/responses",
  "--exclude=*/responses/*",
  "--exclude=*/downloads",
  "--exclude=*/downloads/*",
  "--exclude=*/doctor-report*.json",
];

if (!includeSubmodules) {
  excludes.push(`--exclude=${rootName}/skills/meta/multi-search`);
  excludes.push(`--exclude=${rootName}/skills/meta/multi-search/*`);
}

// Create archive
const tarResult = spawnSync("tar", [
  "-czf",
  archivePath,
  ...excludes,
  "-C",
  parentDir,
  rootName,
], { stdio: "inherit" });

if (tarResult.status !== 0) {
  console.error("tar failed");
  process.exit(tarResult.status ?? 1);
}

// Create checksum using crypto (cross-platform, no shasum/sha256sum dependency)
const archiveData = readFileSync(archivePath);
const hash = createHash("sha256").update(archiveData).digest("hex");
writeFileSync(checksumPath, `${hash}  ${path.basename(archivePath)}\n`);

console.log(`Archive created: ${archivePath}`);
console.log(`Checksum written: ${checksumPath}`);

function dateStamp() {
  const d = new Date();
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
}

function printHelp() {
  console.log(`Usage:
  node scripts/package-migration.mjs [options]

Create a clean migration archive for the active skills repo.

Options:
  --output-dir PATH     Directory that will receive the archive and checksum
  --name NAME           Archive basename without extension
  --include-submodules  Include optional submodule working trees such as multi-search
  --help                Show this help text`);
}
