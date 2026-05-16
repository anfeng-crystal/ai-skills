# Skill Linker

Distribute local AI skills to Codex, Claude Code, Junie, Agents, and Hermes.

Skill Linker audits the source skill tree first, then creates only safe symlinks for supported tools. It refuses real-path conflicts, external symlink conflicts, and duplicate source names that would map to the same target skill.

## Install

```bash
npx @anfeng1314/skill-installer --help
```

Or install globally:

```bash
npm install -g @anfeng1314/skill-installer
skill-installer --help
```

## Quick Start

Run commands from your active skills root, set `AI_SKILLS_HOME`, or create a config file.

```bash
cd ~/AI/skills/active

# Preview all link changes.
npx @anfeng1314/skill-installer --json

# Apply after reviewing the dry-run output.
npx @anfeng1314/skill-installer --apply
```

Sync one skill:

```bash
npx @anfeng1314/skill-installer --skill web-access --apply
```

Sync to selected tools:

```bash
npx @anfeng1314/skill-installer --skill web-access --tool codex --tool claude --apply
```

## Install Skills

Install skills into the active source tree first, then let Skill Linker distribute them. Do not install directly into host tool directories such as `~/.codex/skills` or `%USERPROFILE%\.codex\skills`.

```bash
# Dry-run
npx @anfeng1314/skill-installer install ./my-skill --category meta --json

# Apply after reviewing the target path and sync plan
npx @anfeng1314/skill-installer install ./my-skill --category meta --apply
```

Auto-classify a skill:

```bash
npx @anfeng1314/skill-installer install ./my-skill --category auto --json
```

If auto classification is uncertain, the skill goes to `skills/incoming/<name>` and is not distributed by default.

## Remove and Restore

Soft removal deletes only managed symlinks. The source skill directory stays in the active tree.

```bash
npx @anfeng1314/skill-installer remove neat-freak --apply
```

Restore a soft-removed skill by syncing it again:

```bash
npx @anfeng1314/skill-installer --skill neat-freak --apply
```

Restore only one tool:

```bash
npx @anfeng1314/skill-installer --skill neat-freak --tool codex --apply
```

`remove --purge` deletes the source directory after unlinking. After a purge, restore the source from Git or its upstream repository first, then run sync again.

## Hermes

Hermes should discover skills through `skills.external_dirs`. On macOS/Linux this is usually `~/.hermes/config.yaml`:

```yaml
skills:
  external_dirs:
    - /Users/you/AI/skills/active
```

Skill Linker checks Hermes `external_dirs` and reports local shadow conflicts. It does not create new directory-level symlinks for Hermes. In the default all-tool audit, an unconfigured Hermes host is treated as an optional skipped host. When `--tool hermes` is specified explicitly, missing `external_dirs` is reported as a configuration issue.

## Cross-Platform Configuration

Configuration priority is:

1. CLI flags
2. Environment variables
3. Config file
4. Auto-detection

Supported environment variables:

| Variable | Description |
| --- | --- |
| `AI_SKILLS_HOME` | Active skills root. |
| `AI_HOST_HOME` | Home directory used to derive host tool skill directories. |

Config file locations:

| Platform | Path |
| --- | --- |
| macOS/Linux | `$XDG_CONFIG_HOME/skill-installer/config.json` or `~/.config/skill-installer/config.json` |
| Windows | `%APPDATA%\skill-installer\config.json` |

Example config:

```json
{
  "sourceRoot": "/Users/you/AI/skills/active",
  "home": "/Users/you",
  "targetDirs": {
    "codex": "/Users/you/.codex/skills"
  },
  "hermesConfigPath": "/Users/you/.hermes/config.yaml"
}
```

PowerShell example:

```powershell
$env:AI_SKILLS_HOME = "$env:USERPROFILE\AI\skills\active"
npx @anfeng1314/skill-installer install .\my-skill --category meta --json
```

## Publishing

This package is published as `@anfeng1314/skill-installer`.

Release flow:

```bash
cd <repo>/skills/active/skills/meta/skill-installer
npm version patch
git push origin main --tags
```

Tags matching `skill-installer-v*` are published by GitHub Actions from `skills/active/skills/meta/skill-installer`. Configure npm Trusted Publishing once for repository `anfeng-crystal/ai-workspace` and workflow `publish-skill-installer.yml`.

## Commands

```bash
skill-installer [options]
skill-installer install <local-path-or-git-url> --category <category> [options]
skill-installer remove <skill> [options]
skill-installer diff <skill> [options]
skill-installer update <skill|--all> [options]
skill-installer history [options]
```

Key options:

| Option | Description |
| --- | --- |
| `--source-root <path>` | Source skills root. Defaults to `AI_SKILLS_HOME` or the current active tree. |
| `--home <path>` | Host home. Defaults to `AI_HOST_HOME` or `$HOME`. |
| `--skill <name>` | Skill name or relative path. Repeat or use comma-separated values. |
| `--tool <name>` | `codex`, `claude`, `junie`, `agents`, or `hermes`. |
| `--category <name>` | `core`, `automation`, `kingdee`, `meta`, `incoming`, or `auto`. |
| `--name <name>` | Override installed skill directory name. |
| `--path <subdir>` | Use a subdirectory inside a Git source. |
| `--apply` | Apply planned changes. Default is dry-run. |
| `--json` | Print JSON output. |
| `--purge` | Delete source directory after unlinking during `remove`. |

## License

MIT
