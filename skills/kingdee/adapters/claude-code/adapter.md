# Claude Code Adapter

## Host
- Host id: `claude-code`
- Alias: `claude`
- Default: enabled
- Install mode: symlink
- Target directory: `~/.claude/skills`

## Behavior
- Kingdee skills under `skills/kingdee/*/SKILL.md` are exposed as directory symlinks in the Claude Code skills directory.
- Existing host-owned content is not replaced by the installer.
- Dry-run mode reports planned links and conflicts without writing to the host directory.
