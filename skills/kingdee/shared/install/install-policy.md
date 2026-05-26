# Kingdee Host Install Policy

## Scope
- Source root is the active skills repository root passed with `--root`.
- Source skills are directories under `skills/kingdee/*` that contain `SKILL.md`.
- Host writes are limited to host skill directories and only happen when `sync-hosts.py` is run without `--dry-run`.

## Default Host Semantics
- `codex` and `claude-code` are enabled by default.
- `hermes`, `openclaw`, `opencode`, `antigravity`, and `qoder` are optional by default.
- Default all-host dry runs skip missing optional hosts with `optional_host_unavailable`.
- Explicit `--host <id>` checks that host strictly. For Hermes, missing or incomplete `skills.external_dirs` returns `needs_external_dir_config` and a non-zero exit.

## Write Policy
- `sync-hosts.py --dry-run` is read-only.
- Non-dry-run sync only creates missing symlinks for symlink-based hosts.
- Existing real files, real directories, or symlinks pointing elsewhere are reported as conflicts and are not replaced.
- Hermes is managed through `~/.hermes/config.yaml` `skills.external_dirs`; this installer does not create new Hermes per-skill links.
- qoder uses `~/.qoder/skills`; legacy paths containing backslash characters are intentionally not migrated.

## Doctor Policy
- `doctor-hosts.py` is read-only.
- Enabled hosts must have available target roots.
- Optional hosts may be unavailable without failing the default doctor report.
