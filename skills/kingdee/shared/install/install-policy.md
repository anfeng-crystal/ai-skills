# Kingdee Host Install Policy

## Scope
- Source root is the skills repository root passed with `--root`.
- Source skills are directories under `skills/kingdee/*` that contain `SKILL.md`.
- This Kingdee-local installer is read-only. Host installation and distribution must go through `skills/meta/skill-installer`.
- `sync-hosts.py` is kept for compatibility checks only and refuses non-dry-run writes.

## Default Host Semantics
- `doctor-hosts.py` and `sync-hosts.py --dry-run` may inspect host readiness.
- `codex`, `claude-code`, `hermes`, `openclaw`, `opencode`, `antigravity`, and `qoder` are distribution targets only when selected through `skills/meta/skill-installer`.
- Default all-host dry runs skip missing optional hosts with `optional_host_unavailable`.
- Explicit `--host <id>` checks that host strictly. For Hermes, missing or incomplete `skills.external_dirs` returns `needs_external_dir_config` and a non-zero exit.

## Write Policy
- `sync-hosts.py --dry-run` is read-only.
- `sync-hosts.py` without `--dry-run` returns `direct_sync_disabled` and does not write host directories.
- Use `node skills/meta/skill-installer/bin/skill-installer.mjs ...` for any apply operation.
- Existing real files, real directories, or symlinks pointing elsewhere must be reported by `skill-installer` and not replaced.
- Legacy paths containing backslash characters are intentionally not migrated.

## Doctor Policy
- `doctor-hosts.py` is read-only.
- Enabled hosts must have available target roots.
- Optional hosts may be unavailable without failing the default doctor report.
