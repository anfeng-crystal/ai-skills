# opencode Adapter

## Host
- Host id: `opencode`
- Default: optional
- Install mode: symlink
- Target directory: `~/.opencode/skills`

## Behavior
- opencode is skipped in default all-host runs when the target directory is not present.
- Explicit `--host opencode` requires the target directory to exist before symlinks are planned or created.
- Existing host-owned content is reported as a conflict and is not replaced.
