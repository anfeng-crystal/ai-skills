#!/usr/bin/env node

/**
 * One-line installer for anfeng/skills.
 *
 * Usage:
 *   git clone <skills-repo-url> <checkout-dir>
 *   node <checkout-dir>/install.mjs                    # install all skills
 *   node <checkout-dir>/install.mjs --dry-run          # preview only
 *   node <checkout-dir>/install.mjs --tool claude       # install for Claude Code only
 *   node <checkout-dir>/install.mjs --skill fix-bug     # install one skill
 *   node <checkout-dir>/install.mjs --list              # list available skills
 */

import { spawnSync } from "node:child_process";
import { readdirSync, statSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const SKILLS_DIR = path.join(SCRIPT_DIR, "skills");
const BOOTSTRAP = path.join(SCRIPT_DIR, "scripts/bootstrap.mjs");

const args = process.argv.slice(2);

if (args.includes("--help") || args.includes("-h")) {
  printHelp();
  process.exit(0);
}

if (args.includes("--list")) {
  listSkills(resolveSourceRoot(args));
  process.exit(0);
}

// Default to --apply (this is an installer, not a dry-run tool)
// Unless --dry-run is explicitly passed
const dryRun = args.includes("--dry-run");
const bootstrapArgs = args.filter((a) => a !== "--dry-run");
if (!dryRun) {
  bootstrapArgs.push("--apply");
}

const result = spawnSync(process.execPath, [BOOTSTRAP, ...bootstrapArgs], {
  stdio: "inherit",
  cwd: SCRIPT_DIR,
});
process.exit(result.status ?? 1);

function resolveSourceRoot(argv) {
  const index = argv.indexOf("--source-root");
  if (index >= 0 && argv[index + 1] && !argv[index + 1].startsWith("--")) {
    return path.resolve(argv[index + 1]);
  }
  return path.resolve(process.env.AI_SKILLS_HOME || SKILLS_DIR);
}

function listSkills(skillsRoot) {
  const skills = [];
  for (const category of readdirSync(skillsRoot)) {
    const catDir = path.join(skillsRoot, category);
    if (!statSync(catDir).isDirectory() || category.startsWith(".")) continue;
    for (const name of readdirSync(catDir)) {
      const skillDir = path.join(catDir, name);
      const skillMd = path.join(skillDir, "SKILL.md");
      if (statSync(skillDir).isDirectory() && existsSync(skillMd)) {
        const hasScripts =
          existsSync(path.join(skillDir, "scripts")) ||
          existsSync(path.join(skillDir, "bin"));
        skills.push({ name, category, type: hasScripts ? "script" : "doc" });
      }
    }
  }

  console.log(`\nAvailable skills (${skills.length}):\n`);
  const byCat = {};
  for (const s of skills) {
    (byCat[s.category] ??= []).push(s);
  }
  for (const [cat, list] of Object.entries(byCat).sort()) {
    console.log(`  ${cat}/`);
    for (const s of list.sort((a, b) => a.name.localeCompare(b.name))) {
      const tag = s.type === "script" ? " [script]" : "";
      console.log(`    ${s.name}${tag}`);
    }
    console.log();
  }
}

function printHelp() {
  console.log(`Usage:
  node install.mjs [options]

Options:
  --apply            Install skills (default behavior)
  --dry-run          Preview changes without applying
  --source-root <path>
                     Skills source root (default: checkout skills/ or AI_SKILLS_HOME)
  --tool <name>      Install for a specific host tool; repeatable
                     (claude, claude-code, codex, junie, agents, hermes,
                      qoder, qoderwork, workbuddy, trae, openclaw, opencode,
                      antigravity, antigravity-cli, agy, antigravity-desktop)
  --skill <name>     Install a specific skill; repeatable
  --list             List all available skills
  --skip-doctor      Skip dependency checks
  --help             Show this help

Examples:
  node install.mjs                          # install all skills
  node install.mjs --dry-run                # preview only
  node install.mjs --tool claude            # Claude Code only
  node install.mjs --tool antigravity-cli   # Antigravity CLI only
  node install.mjs --skill fix-bug          # one skill
  node install.mjs --skill fix-bug --skill explain-code  # two skills
`);
}
