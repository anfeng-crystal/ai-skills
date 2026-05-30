# Migration Guide

## Goal

Move the active skills set to another Windows, macOS, or Linux machine without copying any existing host skill directories from the source machine.

If an AI agent on the target machine performs the migration, use `docs/TARGET_MACHINE_AI_PLAN.md` as the authoritative execution plan. It covers skill installation, validation, and migration of Codex, Claude Code, and Antigravity global rules.

## Pre-migration checklist

1. Clone this repository to the target machine.
2. Decide the target account home path.
3. Prepare `AI_KNOWLEDGE_ROOT` if the target machine needs Kingdee skills.
4. Prepare local secrets separately; do not copy `.env`, cookies, caches, or host-specific runtime folders.

## First-time setup

```bash
cd /path/to/skills/active
cp .env.example .env
node ./scripts/npm-deps.mjs install
node ./scripts/bootstrap.mjs
node ./scripts/bootstrap.mjs --apply
node ./scripts/doctor.mjs --json
```

If you need to hand-carry the repo to another machine before a remote is available, create a clean transfer package from the source machine first:

```bash
./scripts/package-migration.sh
```

## Host integration model

- Codex / Claude / Junie / Agents: link each skill directory into the host `skills` directory. Windows uses junctions; macOS/Linux use directory symlinks.
- Hermes: do not create new per-skill symlinks. Configure `~/.hermes/config.yaml` so `skills.external_dirs` includes this repo root.

## Validation checklist

- `rg -n '/Users/[^/ ]+' .` returns no migration-relevant hardcoded paths in active code and docs.
- `node ./scripts/npm-deps.mjs check` reports all local npm dependencies installed.
- `node ./skills/meta/skill-installer/bin/skill-installer.mjs --json` reports the expected host state.
- `node ./skills/automation/web-access/scripts/check-deps.mjs --dry-run --json` succeeds.
- `node ./skills/automation/playwright/scripts/playwright_cli.mjs --help` succeeds.
- `python3 ./multi-search/union_search_cli.py doctor` runs on machines that install the optional union-search dependencies.
- `AI_KNOWLEDGE_ROOT` is configured and points to a tree containing `kingdee/cosmic/projects/config-table.md` before using Kingdee analysis flows.

## Update workflow

```bash
git pull
node ./scripts/npm-deps.mjs install
node ./scripts/bootstrap.mjs
node ./scripts/doctor.mjs
```

Re-run with `--apply` only if the dry-run shows new or changed link targets that you want to materialize.

## Rollback workflow

```bash
git checkout <known-good-ref>
node ./scripts/bootstrap.mjs --apply
node ./scripts/doctor.mjs
```

## Security and packaging rules

- Do not distribute `.env`, cookies, `responses/`, downloads, or browser profiles.
- Keep `legacy/` and `incoming/` out of the default bootstrap flow.
- Review local modifications in nested repos such as `multi-search/` separately from the outer active repo.
- Run `node ./skills/meta/skill-vetter/scripts/inspect-skill.mjs --path . --json` or targeted per-skill checks before publishing changes to a shared remote.
