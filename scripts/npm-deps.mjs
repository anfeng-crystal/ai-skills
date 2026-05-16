#!/usr/bin/env node

/**
 * Install or check npm dependencies used by active skill scripts.
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPT_DIR, "..");
const CACHE_DIR = process.env.ACTIVE_SKILLS_NPM_CACHE || path.join(REPO_ROOT, ".npm-cache");

const packageDirs = [
  REPO_ROOT,
  path.join(REPO_ROOT, "skills/meta/multi-search"),
  path.join(REPO_ROOT, "skills/meta/multi-search/scripts/url_to_markdown/engines/defuddle-node"),
].filter((dir) => fs.existsSync(path.join(dir, "package.json")));

const command = process.argv[2] || "check";
if (command === "--help" || command === "-h" || command === "help") {
  printHelp();
  process.exit(0);
}

if (!["check", "install"].includes(command)) {
  console.error(`Unknown command: ${command}`);
  printHelp();
  process.exit(2);
}

let failed = false;
for (const dir of packageDirs) {
  const pkg = readPackage(dir);
  const deps = dependencyNames(pkg);
  if (deps.length === 0) {
    console.log(`OK ${relative(dir)} has no runtime npm dependencies`);
    continue;
  }

  const missing = deps.filter((name) => !dependencyInstalled(dir, name));
  if (command === "check") {
    if (missing.length > 0) {
      failed = true;
      console.log(`MISSING ${relative(dir)}: ${missing.join(", ")}`);
    } else {
      console.log(`OK ${relative(dir)}: ${deps.length} dependencies installed`);
    }
    continue;
  }

  if (missing.length === 0) {
    console.log(`OK ${relative(dir)}: dependencies already installed`);
    continue;
  }

  console.log(`INSTALL ${relative(dir)}: ${missing.join(", ")}`);
  fs.mkdirSync(CACHE_DIR, { recursive: true });
  const npm = process.platform === "win32" ? "npm.cmd" : "npm";
  const hasLock = fs.existsSync(path.join(dir, "package-lock.json"));
  const args = [hasLock ? "ci" : "install", "--prefer-offline", "--no-audit", "--no-fund"];
  const result = spawnSync(npm, args, {
    cwd: dir,
    env: {
      ...process.env,
      npm_config_cache: process.env.npm_config_cache || CACHE_DIR,
      npm_config_update_notifier: process.env.npm_config_update_notifier || "false",
    },
    stdio: "inherit",
  });
  if (result.status) {
    failed = true;
  }
}

process.exit(failed ? 1 : 0);

function readPackage(dir) {
  return JSON.parse(fs.readFileSync(path.join(dir, "package.json"), "utf8"));
}

function dependencyNames(pkg) {
  return [
    ...Object.keys(pkg.dependencies || {}),
    ...Object.keys(pkg.optionalDependencies || {}),
  ].sort();
}

function dependencyInstalled(packageDir, name) {
  const parts = name.startsWith("@") ? name.split("/") : [name];
  return fs.existsSync(path.join(packageDir, "node_modules", ...parts));
}

function relative(dir) {
  const rel = path.relative(REPO_ROOT, dir);
  return rel || ".";
}

function printHelp() {
  console.log(`Usage:
  node scripts/npm-deps.mjs check
  node scripts/npm-deps.mjs install

Installs npm dependencies into each package's node_modules using a local cache:
  ${CACHE_DIR.replace(os.homedir(), "~")}
`);
}
