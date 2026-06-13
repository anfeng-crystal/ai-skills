# Claude Code Adapter

## Host
- Host id: `claude-code`
- Alias: `claude`
- Distribution owner: `skills/meta/skill-installer`
- Install mode: managed symlink or host-specific method selected by `skill-installer`
- Target directory: `~/.claude/skills`

## Behavior
- Do not create Claude Code links directly from Kingdee-local scripts.
- Preview distribution with `skill-installer` before applying.
- Existing host-owned content is not replaced by the installer.
