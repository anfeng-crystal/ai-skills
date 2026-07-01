# Trae Adapter

## Host
- Host id: `trae`
- Alias: `trae-ide`
- Default: optional
- Install mode: symlink
- Default target directory: `~/.trae/skills`

## Behavior
- Trae is skipped in default all-host runs when the target directory is not present.
- Explicit `--tool trae` requires the target directory to exist before links are planned or created.
- If the target machine's Trae installation uses a different skills directory, configure `targetDirs.trae` in the skill-installer config file.
- Existing host-owned content is reported as a conflict and is not replaced.
