# Hermes Adapter

## Host
- Host id: `hermes`
- Default: optional
- Install mode: `skills.external_dirs`
- Config file: `~/.hermes/config.yaml`

## Behavior
- Hermes should discover this active skills root through `skills.external_dirs`.
- The installer does not create new per-skill symlinks under `~/.hermes/skills`.
- Default all-host dry runs skip Hermes when the config is missing, unreadable, or does not list the active root.
- Explicit `--host hermes` treats missing `skills.external_dirs` configuration as a hard error.
