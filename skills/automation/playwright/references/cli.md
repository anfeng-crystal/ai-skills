# Playwright CLI Reference

Use this complete Node wrapper entry on Windows, macOS, and Linux. It resolves `@playwright/cli` through `npx` and falls back to the local install when npm package resolution fails:

```bash
node <active-root>/scripts/npm-deps.mjs install
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs --help
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs open https://example.com
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs snapshot
```

User-scoped skills usually install under the host skills directory such as `.codex/skills`; prefer `AI_SKILLS_HOME` or `<active-root>` when calling the source tree directly.

Optional cross-platform helpers (functions, not shell aliases):

```sh
pwcli() { node "<active-root>/skills/automation/playwright/scripts/playwright_cli.mjs" "$@"; }
pwcli open https://example.com
```

```powershell
function pwcli { node "<active-root>\skills\automation\playwright\scripts\playwright_cli.mjs" @args }
pwcli open https://example.com
```

Replace `<active-root>` with the active skill root. The Node wrapper already handles `npx.cmd` on Windows; the helper is optional.

## Core

```bash
pwcli open https://example.com
pwcli close
pwcli snapshot
pwcli click e3
pwcli dblclick e7
pwcli type "search terms"
pwcli press Enter
pwcli fill e5 "user@example.com"
pwcli drag e2 e8
pwcli hover e4
pwcli select e9 "option-value"
pwcli upload ./document.pdf
pwcli check e12
pwcli uncheck e12
pwcli eval "document.title"
pwcli eval "el => el.textContent" e5
pwcli dialog-accept
pwcli dialog-accept "confirmation text"
pwcli dialog-dismiss
pwcli resize 1920 1080
```

Use the Playwright CLI subcommand `pwcli find`, not the operating-system `find` command:

```bash
pwcli find "Sign in"
pwcli find --regex "Sign (in|up)"
pwcli find --regex "/sign (in|up)/i"
```

Video action annotations are available in the current Playwright CLI:

```bash
pwcli video-show-actions --duration=600 --position=top-right
pwcli video-hide-actions
```

## Navigation

```bash
pwcli go-back
pwcli go-forward
pwcli reload
```

## Keyboard

```bash
pwcli press Enter
pwcli press ArrowDown
pwcli keydown Shift
pwcli keyup Shift
```

## Mouse

```bash
pwcli mousemove 150 300
pwcli mousedown
pwcli mousedown right
pwcli mouseup
pwcli mouseup right
pwcli mousewheel 0 100
```

## Save as

```bash
pwcli screenshot                 # confirm local path/privacy before saving
pwcli screenshot e5              # confirm local path/privacy before saving
pwcli pdf                         # confirm local path/privacy before saving
```

## Tabs

```bash
pwcli tab-list
pwcli tab-new
pwcli tab-new https://example.com/page
pwcli tab-close
pwcli tab-close 2
pwcli tab-select 0
```

Keep the selected tab explicit when working across pages:

```bash
pwcli --session research open https://example.com
pwcli tab-new https://example.com/docs
pwcli tab-list
pwcli tab-select 1
pwcli snapshot
pwcli tab-select 0
pwcli snapshot
```

## DevTools

```bash
pwcli console
pwcli console warning
pwcli network
pwcli run-code "await page.waitForTimeout(1000)"
pwcli tracing-start
pwcli tracing-stop
```

Wait for an element with the current CLI's `run-code` command:

```bash
pwcli run-code "await page.locator('[data-testid=results]').waitFor({ state: 'visible', timeout: 10000 })"
pwcli snapshot
```

## Sessions

Prefer `--session` to isolate work:

```bash
pwcli --session todo open https://demo.playwright.dev/todomvc
pwcli --session todo snapshot
```

The session environment variable is also available in both shells:

```sh
export PLAYWRIGHT_CLI_SESSION=todo
pwcli open https://demo.playwright.dev/todomvc
```

```powershell
$env:PLAYWRIGHT_CLI_SESSION = "todo"
pwcli open https://demo.playwright.dev/todomvc
```

Equivalent explicit form:

```bash
pwcli --session todo open https://demo.playwright.dev/todomvc
```

Do not use POSIX `export` in PowerShell.
