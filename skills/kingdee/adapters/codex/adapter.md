# Codex Adapter

## Host
- Host id: `codex`
- Distribution owner: `skills/meta/skill-installer`
- Install mode: managed symlink or host-specific method selected by `skill-installer`
- Target directory: `~/.codex/skills`

## Behavior
- Do not create Codex links directly from Kingdee-local scripts.
- Preview distribution with `skill-installer` before applying.
- Existing files, real directories, or symlinks pointing to another source are left untouched and reported as conflicts.
