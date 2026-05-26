# OpenClaw Adapter

## Host
- Host id: `openclaw`
- Default: optional
- Install mode: symlink
- Target directory: `~/.openclaw/workspace/skills`

## Behavior
- OpenClaw is skipped in default all-host runs when the target directory is not present.
- Explicit `--host openclaw` requires the target directory to exist before symlinks are planned or created.
- Existing host-owned content is reported as a conflict and is not replaced.
