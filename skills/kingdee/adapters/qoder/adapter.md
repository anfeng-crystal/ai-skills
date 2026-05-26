# qoder Adapter

## Host
- Host id: `qoder`
- Default: optional
- Install mode: symlink
- Target directory: `~/.qoder/skills`

## Behavior
- qoder is skipped in default all-host runs when the target directory is not present.
- Explicit `--host qoder` requires the target directory to exist before symlinks are planned or created.
- Only the normal POSIX path `~/.qoder/skills` is used. Legacy paths containing backslash characters are intentionally not migrated.
- Existing host-owned content is reported as a conflict and is not replaced.
