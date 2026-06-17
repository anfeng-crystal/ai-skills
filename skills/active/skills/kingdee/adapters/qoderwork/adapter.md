# qoderwork Adapter

## Host
- Host id: `qoderwork`
- Alias: `qoder-work`
- Default: optional
- Install mode: symlink
- Target directory: `~/.qoderwork/skills`

## Behavior
- qoderwork is skipped in default all-host runs when the target directory is not present.
- Explicit `--tool qoderwork` requires the target directory to exist before links are planned or created.
- Existing host-owned content is reported as a conflict and is not replaced.
