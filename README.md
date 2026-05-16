# AI Skills Active

`skills/active` is the shared source tree for the active skill set used by Codex, Claude, Junie, Agents, and Hermes on Windows, macOS, and Linux.

## What is included

- Default install scope: every directory in this repo root that contains `SKILL.md`
- Excluded from default distribution: `legacy/` and `incoming/` outside this repo
- Hermes integration model: `skills.external_dirs`
- Link-based integration model: Codex, Claude, Junie, Agents

## Quick start

```bash
git clone https://github.com/anfeng-crystal/ai-skills.git ~/AI/skills
node ~/AI/skills/install.mjs
```

Or with more control:

```bash
node ~/AI/skills/install.mjs --dry-run          # preview first
node ~/AI/skills/install.mjs --tool claude       # Claude Code only
node ~/AI/skills/install.mjs --skill fix-bug     # one skill
node ~/AI/skills/install.mjs --list              # list available skills
```

`install.mjs` calls `bootstrap.mjs --apply` by default. `bootstrap.mjs` performs a dry-run link audit; add `--apply` only after reviewing the planned link changes.

`npm-deps.mjs install` prefetches npm packages used by skill scripts into local `node_modules` with a repo-local `.npm-cache`. Runtime wrappers still try `npx` first; when npm registry access is poor, they fall back to the local install.

## Environment

Copy `.env.example` to a local `.env` or export the variables in your shell profile.

- `AI_HOST_HOME`: target home used to derive `.codex/.claude/.junie/.agents/.hermes`
- `AI_KNOWLEDGE_ROOT`: required by `kingdee-cosmic` and `kingdee-metadata-analyzer`
- `DARWIN_PLAYWRIGHT_CANDIDATES`: optional fallback module/path list for `darwin-skill`
- `YTDLP_COOKIES_FILE`: explicit cookie file for `multi-search` download commands

## Install and update flow

1. Clone this repo to the target machine.
2. Run `node install.mjs` to install all skills and check dependencies.
3. For later updates, use `git pull` and rerun `node install.mjs`.

For more control, use `bootstrap.mjs` directly (see below).

## Packaging for transfer

Use the repo root as the migration unit, not any single host-specific skills directory. `scripts/package-migration.mjs` creates a clean `tar.gz` transfer package with SHA256 checksum (cross-platform, uses Node.js crypto).

- Primary entry file: `README.md`
- Migration runbook: `MIGRATION.md`
- Install entry: `install.mjs`
- Validation entry: `scripts/doctor.mjs`
- Packaging entry: `scripts/package-migration.mjs`

```bash
node scripts/package-migration.mjs
```

The script writes a clean `tar.gz` snapshot under `dist/` and excludes `.git`, `.env`, caches, and other local-only runtime artifacts.

## Rollback

Rollback is operational rather than destructive:

1. Use `git checkout <known-good-ref>` in this repo.
2. Rerun `node ./scripts/bootstrap.mjs --apply` if link targets changed.
3. Rerun `node ./scripts/doctor.mjs` to confirm hosts and prerequisites still pass.

## Repository notes

- `multi-search/` is currently maintained as a nested Git checkout and remains ignored by the outer repo. Treat it as a separately versioned dependency until you intentionally consolidate it.
- Creating and wiring a remote Git host for this repo is still a manual setup step; this tree now assumes a Git-first distribution model but does not provision remotes for you.
