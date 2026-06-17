# WorkBuddy Adapter

## Host
- Host id: `workbuddy`
- Default: optional
- Install mode: symlink
- Target directory: `~/.workbuddy/skills`

## Behavior
- WorkBuddy is skipped in default all-host runs when the target directory is not present.
- Explicit `--tool workbuddy` requires the target directory to exist before links are planned or created.
- Existing host-owned content is reported as a conflict and is not replaced.
