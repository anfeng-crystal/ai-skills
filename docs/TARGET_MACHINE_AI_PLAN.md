# Target Machine AI Execution Plan

本文件是交给其它机器上的 AI 执行的固定计划。目标机器包括：

- MacBook Air: macOS
- Honor MagicBook Pro 14: Windows 11 native
- Honor MagicBook Pro 14: WSL Ubuntu 24

执行 AI 必须按本计划操作，不要把宿主历史、登录态、token、cookie、浏览器 profile、缓存目录或运行日志从任何机器复制到另一台机器。

## 0. Rules Before Acting

1. 先确认当前运行环境：macOS、Windows PowerShell、或 WSL Ubuntu 24。
2. Windows native 与 WSL Ubuntu 是两个独立宿主，必须各自 clone、各自安装、各自迁移全局规则。
3. WSL 不得使用 `/mnt/c/Users/...` 下的 Windows checkout；WSL 必须 clone 到 Linux home 下的 `~/AI/skills/active`。
4. 如果目标规则文件已存在，必须先备份，再覆盖为本仓库的规范副本。
5. 不迁移以下内容：
   - `~/.codex/auth.json`
   - `~/.codex/*sqlite*`
   - `~/.codex/sessions/`
   - `~/.codex/archived_sessions/`
   - `~/.claude/history.jsonl`
   - `~/.claude/settings.local.json`
   - `~/.claude/file-history/`
   - `~/.claude/sessions/`
   - `~/.gemini/antigravity*/conversations/`
   - `~/.gemini/antigravity*/cache/`
   - `~/.gemini/antigravity*/log/`
   - `.env`、cookies、downloads、responses、browser profiles、`node_modules/`
6. 本计划只迁移稳定规则和 skill 仓库；本机私有文件例如 `~/.claude/RTK.md` 不在默认迁移范围内。

## 1. Bootstrap Repository

### macOS and WSL Ubuntu

```bash
mkdir -p ~/AI/skills
if [ -d ~/AI/skills/active/.git ]; then
  cd ~/AI/skills/active
  git pull --ff-only origin main
else
  git clone https://github.com/anfeng-crystal/ai-skills.git ~/AI/skills/active
  cd ~/AI/skills/active
fi
```

### Windows 11 PowerShell

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\AI\skills" | Out-Null
if (Test-Path "$env:USERPROFILE\AI\skills\active\.git") {
  Set-Location "$env:USERPROFILE\AI\skills\active"
  git pull --ff-only origin main
} else {
  git clone https://github.com/anfeng-crystal/ai-skills.git "$env:USERPROFILE\AI\skills\active"
  Set-Location "$env:USERPROFILE\AI\skills\active"
}
```

## 2. Migrate Global Rules

Use the canonical files from this repository:

- Codex: `docs/global-rules/codex/AGENTS.md`
- Claude Code: `docs/global-rules/claude/CLAUDE.md`
- Antigravity / Gemini: `docs/global-rules/antigravity/GEMINI.md`

### macOS and WSL Ubuntu

```bash
cd ~/AI/skills/active
ts="$(date +%Y%m%d-%H%M%S)"

mkdir -p ~/.codex ~/.claude ~/.gemini

[ -f ~/.codex/AGENTS.md ] && cp ~/.codex/AGENTS.md ~/.codex/AGENTS.md.backup-$ts
[ -f ~/.claude/CLAUDE.md ] && cp ~/.claude/CLAUDE.md ~/.claude/CLAUDE.md.backup-$ts
[ -f ~/.gemini/GEMINI.md ] && cp ~/.gemini/GEMINI.md ~/.gemini/GEMINI.md.backup-$ts

cp docs/global-rules/codex/AGENTS.md ~/.codex/AGENTS.md
cp docs/global-rules/claude/CLAUDE.md ~/.claude/CLAUDE.md
cp docs/global-rules/antigravity/GEMINI.md ~/.gemini/GEMINI.md
```

### Windows 11 PowerShell

```powershell
Set-Location "$env:USERPROFILE\AI\skills\active"
$ts = Get-Date -Format "yyyyMMdd-HHmmss"

New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex" | Out-Null
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude" | Out-Null
New-Item -ItemType Directory -Force "$env:USERPROFILE\.gemini" | Out-Null

if (Test-Path "$env:USERPROFILE\.codex\AGENTS.md") {
  Copy-Item "$env:USERPROFILE\.codex\AGENTS.md" "$env:USERPROFILE\.codex\AGENTS.md.backup-$ts"
}
if (Test-Path "$env:USERPROFILE\.claude\CLAUDE.md") {
  Copy-Item "$env:USERPROFILE\.claude\CLAUDE.md" "$env:USERPROFILE\.claude\CLAUDE.md.backup-$ts"
}
if (Test-Path "$env:USERPROFILE\.gemini\GEMINI.md") {
  Copy-Item "$env:USERPROFILE\.gemini\GEMINI.md" "$env:USERPROFILE\.gemini\GEMINI.md.backup-$ts"
}

Copy-Item .\docs\global-rules\codex\AGENTS.md "$env:USERPROFILE\.codex\AGENTS.md"
Copy-Item .\docs\global-rules\claude\CLAUDE.md "$env:USERPROFILE\.claude\CLAUDE.md"
Copy-Item .\docs\global-rules\antigravity\GEMINI.md "$env:USERPROFILE\.gemini\GEMINI.md"
```

## 3. Install Skills

### macOS and WSL Ubuntu

```bash
cd ~/AI/skills/active
node scripts/sync-and-install.mjs
```

### Windows 11 PowerShell

```powershell
Set-Location "$env:USERPROFILE\AI\skills\active"
node .\scripts\sync-and-install.mjs --home "$env:USERPROFILE"
```

## 4. Configure Local-Only Environment

The target machine owner must configure local paths and secrets. Do not infer or copy them from another machine.

Required only when the target machine needs the related workflows:

- `AI_KNOWLEDGE_ROOT`: required for Kingdee knowledge-backed workflows.
- `YTDLP_COOKIES_FILE`: optional cookie file for download workflows.
- Tool logins, API keys, browser profiles, and cookies: configure manually in each host tool.

If `AI_KNOWLEDGE_ROOT` is not configured, Kingdee knowledge-backed skills may be installed but must be treated as degraded until `doctor` passes with a valid knowledge root.

## 5. Verify

Run the verification commands in the active repo.

### macOS and WSL Ubuntu

```bash
cd ~/AI/skills/active
npm test
node scripts/validate-cross-platform.mjs
node scripts/doctor.mjs --source-root "$HOME/AI/skills/active" --home "$HOME"
```

### Windows 11 PowerShell

```powershell
Set-Location "$env:USERPROFILE\AI\skills\active"
npm test
node .\scripts\validate-cross-platform.mjs
node .\scripts\doctor.mjs --source-root "$env:USERPROFILE\AI\skills\active" --home "$env:USERPROFILE"
```

Expected result:

- `npm test`: all tests pass.
- `validate-cross-platform`: all skills pass.
- `doctor`: `Overall: ok`.

Warnings about optional tools are acceptable only when the target machine owner confirms those workflows are not needed on that machine.

## 6. Report Back

The executing AI must report:

1. OS and shell used.
2. Active repo path.
3. Current commit: `git rev-parse --short HEAD`.
4. Whether Codex, Claude Code, and Antigravity global rules were backed up and replaced.
5. `npm test` result.
6. `validate-cross-platform` result.
7. `doctor` result and warnings.
8. Any local-only environment variables still missing.

## 7. Rollback

If the target machine has problems after migration:

### macOS and WSL Ubuntu

```bash
cd ~/AI/skills/active
git checkout <known-good-ref>
node install.mjs
node scripts/doctor.mjs --source-root "$HOME/AI/skills/active" --home "$HOME"
```

Restore backed-up global rules if needed:

```bash
cp ~/.codex/AGENTS.md.backup-<timestamp> ~/.codex/AGENTS.md
cp ~/.claude/CLAUDE.md.backup-<timestamp> ~/.claude/CLAUDE.md
cp ~/.gemini/GEMINI.md.backup-<timestamp> ~/.gemini/GEMINI.md
```

### Windows 11 PowerShell

```powershell
Set-Location "$env:USERPROFILE\AI\skills\active"
git checkout <known-good-ref>
node .\install.mjs --home "$env:USERPROFILE"
node .\scripts\doctor.mjs --source-root "$env:USERPROFILE\AI\skills\active" --home "$env:USERPROFILE"
```

Restore backed-up global rules if needed:

```powershell
Copy-Item "$env:USERPROFILE\.codex\AGENTS.md.backup-<timestamp>" "$env:USERPROFILE\.codex\AGENTS.md"
Copy-Item "$env:USERPROFILE\.claude\CLAUDE.md.backup-<timestamp>" "$env:USERPROFILE\.claude\CLAUDE.md"
Copy-Item "$env:USERPROFILE\.gemini\GEMINI.md.backup-<timestamp>" "$env:USERPROFILE\.gemini\GEMINI.md"
```
