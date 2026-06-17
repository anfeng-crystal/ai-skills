# Antigravity Adapter

## Host
- Host id: `antigravity`
- Alias: `antigravity-cli`
- Default: optional
- Install mode: symlink
- Target directory: `~/.gemini/antigravity-cli/skills`

## Behavior
- Antigravity is skipped in default all-host runs when the target directory is not present.
- Explicit `--host antigravity` requires the target directory to exist before symlinks are planned or created.
- Existing host-owned content is reported as a conflict and is not replaced.
