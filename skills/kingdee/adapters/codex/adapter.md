# Codex Adapter

## Host
- Host id: `codex`
- Default: enabled
- Install mode: symlink
- Target directory: `~/.codex/skills`

## Behavior
- Kingdee skills under `skills/kingdee/*/SKILL.md` are exposed as directory symlinks in the Codex skills directory.
- Existing files, real directories, or symlinks pointing to another source are left untouched and reported as conflicts.
- Dry-run mode is read-only and is the default validation path for review.
