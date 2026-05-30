# AI Skills Active / AI 活跃技能集

`skills/active` is the shared source tree for the active skill set used by Codex, Claude, Junie, Agents, and Hermes on Windows, macOS, and Linux.

`skills/active` 是 Codex、Claude、Junie、Agents 和 Hermes 在 Windows、macOS、Linux 上共用的活跃技能源目录。

## What Is Included / 包含内容

- Default install scope: every directory in this repo root that contains `SKILL.md`
- 默认安装范围：本仓库根目录下所有包含 `SKILL.md` 的目录
- Excluded from default distribution: `legacy/` and `incoming/` outside this repo
- 默认分发排除：本仓库外的 `legacy/` 和 `incoming/`
- Hermes integration model: `skills.external_dirs`
- Hermes 接入模型：`skills.external_dirs`
- Link-based integration model: Codex, Claude, Junie, Agents
- 链接式接入模型：Codex、Claude、Junie、Agents

## Quick Start / 快速开始

macOS and WSL Ubuntu / macOS 与 WSL Ubuntu：

```bash
git clone https://github.com/anfeng-crystal/ai-skills.git ~/AI/skills/active
cd ~/AI/skills/active
node install.mjs
```

Windows PowerShell / Windows PowerShell：

```powershell
git clone https://github.com/anfeng-crystal/ai-skills.git "$env:USERPROFILE\AI\skills\active"
Set-Location "$env:USERPROFILE\AI\skills\active"
node .\install.mjs --home "$env:USERPROFILE"
```

More install controls / 更多安装控制：

```bash
node install.mjs --dry-run          # preview first / 先预览
node install.mjs --tool claude       # Claude Code only / 仅安装到 Claude Code
node install.mjs --skill fix-bug     # one skill / 只安装一个技能
node install.mjs --list              # list available skills / 列出可用技能
```

`install.mjs` calls `bootstrap.mjs --apply` by default. `bootstrap.mjs` performs a link audit and materializes the planned links when `--apply` is present.

`install.mjs` 默认调用 `bootstrap.mjs --apply`。`bootstrap.mjs` 会先审计链接计划，并在带有 `--apply` 时写入目标宿主链接。

`npm-deps.mjs install` prefetches npm packages used by skill scripts into local `node_modules` with a repo-local `.npm-cache`. Runtime wrappers still try `npx` first; when npm registry access is poor, they fall back to the local install.

`npm-deps.mjs install` 会把技能脚本使用的 npm 包预取到本地 `node_modules`，缓存放在仓库内的 `.npm-cache`。运行时包装器仍会优先尝试 `npx`，当 npm registry 访问不稳定时再回退到本地安装。

## Environment / 环境变量

Copy `.env.example` to a local `.env`, or export the variables in your shell profile.

可以把 `.env.example` 复制为本机 `.env`，也可以在 shell profile 中导出环境变量。

- `AI_HOST_HOME`: target home used to derive `.codex/.claude/.junie/.agents/.hermes`
- `AI_HOST_HOME`：目标宿主 home，用于推导 `.codex/.claude/.junie/.agents/.hermes`
- `AI_KNOWLEDGE_ROOT`: required by `kingdee-cosmic` and `kingdee-metadata-analyzer`
- `AI_KNOWLEDGE_ROOT`：`kingdee-cosmic` 和 `kingdee-metadata-analyzer` 需要的知识库根目录
- `DARWIN_PLAYWRIGHT_CANDIDATES`: optional fallback module/path list for `darwin-skill`
- `DARWIN_PLAYWRIGHT_CANDIDATES`：`darwin-skill` 可选的 Playwright 模块或路径候选列表
- `YTDLP_COOKIES_FILE`: explicit cookie file for `multi-search` download commands
- `YTDLP_COOKIES_FILE`：`multi-search` 下载命令使用的显式 cookie 文件

## Install And Update Flow / 安装与更新流程

1. Clone this repo to the target machine.
2. Run `node install.mjs` to install all skills and check dependencies.
3. For later updates, use `node scripts/sync-and-install.mjs`.

1. 把本仓库 clone 到目标机器。
2. 运行 `node install.mjs` 安装全部技能并检查依赖。
3. 以后更新时，运行 `node scripts/sync-and-install.mjs`。

If another machine's AI is doing the setup, give it `docs/TARGET_MACHINE_AI_PLAN.md` and require it to follow that plan. The plan also migrates Codex, Claude Code, and Antigravity global rules from `docs/global-rules/`.

如果由其它机器上的 AI 执行安装，请把 `docs/TARGET_MACHINE_AI_PLAN.md` 交给它，并要求它严格按计划执行。该计划也会从 `docs/global-rules/` 迁移 Codex、Claude Code 和 Antigravity 的全局规则。

`scripts/sync-and-install.mjs` is the routine update entrypoint for other machines. It runs `git pull --ff-only`, installs the active skills into the target host home, and then runs `scripts/doctor.mjs`.

`scripts/sync-and-install.mjs` 是其它机器的常规更新入口。它会依次执行 `git pull --ff-only`、把活跃技能安装到目标宿主 home，然后运行 `scripts/doctor.mjs`。

macOS and WSL Ubuntu / macOS 与 WSL Ubuntu：

```bash
cd ~/AI/skills/active
node scripts/sync-and-install.mjs
```

Windows PowerShell / Windows PowerShell：

```powershell
Set-Location "$env:USERPROFILE\AI\skills\active"
node .\scripts\sync-and-install.mjs --home "$env:USERPROFILE"
```

Windows and WSL are separate hosts. Use a separate WSL clone under `~/AI`; do not point WSL at the Windows checkout under `/mnt/c/Users/...`.

Windows 原生环境和 WSL 是两个独立宿主。WSL 请在 `~/AI` 下单独 clone，不要让 WSL 指向 `/mnt/c/Users/...` 下的 Windows checkout。

For more control, use `bootstrap.mjs` directly.

需要更细粒度控制时，可以直接使用 `bootstrap.mjs`。

## Packaging For Transfer / 打包迁移

Use the repo root as the migration unit, not any single host-specific skills directory. `scripts/package-migration.mjs` creates a clean `tar.gz` transfer package with SHA256 checksum.

迁移时以仓库根目录为单位，不要迁移某个宿主自己的 skills 目录。`scripts/package-migration.mjs` 会创建干净的 `tar.gz` 迁移包，并生成 SHA256 校验文件。

- Primary entry file: `README.md`
- 主入口文件：`README.md`
- Migration runbook: `MIGRATION.md`
- 迁移操作说明：`MIGRATION.md`
- Install entry: `install.mjs`
- 安装入口：`install.mjs`
- Validation entry: `scripts/doctor.mjs`
- 验证入口：`scripts/doctor.mjs`
- Packaging entry: `scripts/package-migration.mjs`
- 打包入口：`scripts/package-migration.mjs`

```bash
node scripts/package-migration.mjs
```

The script writes a clean `tar.gz` snapshot under `dist/` and excludes `.git`, `.env`, caches, and other local-only runtime artifacts.

该脚本会在 `dist/` 下写入干净的 `tar.gz` 快照，并排除 `.git`、`.env`、缓存以及其它本机运行产物。

## Rollback / 回滚

Rollback is operational rather than destructive:

回滚采用操作式回滚，不做破坏性清理：

1. Use `git checkout <known-good-ref>` in this repo.
2. Rerun `node ./scripts/bootstrap.mjs --apply` if link targets changed.
3. Rerun `node ./scripts/doctor.mjs` to confirm hosts and prerequisites still pass.

1. 在本仓库执行 `git checkout <known-good-ref>`。
2. 如果链接目标发生过变化，重新运行 `node ./scripts/bootstrap.mjs --apply`。
3. 重新运行 `node ./scripts/doctor.mjs`，确认宿主链接和前置依赖仍然通过。

## Repository Notes / 仓库说明

- `multi-search/` is currently maintained as a nested Git checkout and remains ignored by the outer repo. Treat it as a separately versioned dependency until you intentionally consolidate it.
- `multi-search/` 当前按嵌套 Git checkout 维护，并继续被外层仓库忽略。在明确合并前，把它视为单独版本管理的依赖。
- This tree assumes a Git-first distribution model but does not provision remotes for you.
- 本目录假设采用 Git 优先的分发模型，但不会自动为你创建或配置远端仓库。
