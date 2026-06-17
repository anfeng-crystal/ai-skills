# Playwright CLI Reference

Use the Node wrapper. It resolves `@playwright/cli` through `npx` on Windows, macOS, and Linux, then falls back to the local install when npm package resolution fails:

```bash
node <active-root>/scripts/npm-deps.mjs install
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs --help
```

User-scoped skills usually install under the host skills directory such as `.codex/skills`; prefer `AI_SKILLS_HOME` or `<active-root>` when calling the source tree directly.

Optional convenience alias:

```bash
alias pwcli='node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs'
```

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
pwcli screenshot
pwcli screenshot e5
pwcli pdf
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

## DevTools

```bash
pwcli console
pwcli console warning
pwcli network
pwcli run-code "await page.waitForTimeout(1000)"
pwcli tracing-start
pwcli tracing-stop
```

## Sessions

Use a named session to isolate work:

```bash
pwcli --session todo open https://demo.playwright.dev/todomvc
pwcli --session todo snapshot
```

Or set an environment variable once:

```bash
export PLAYWRIGHT_CLI_SESSION=todo
pwcli open https://demo.playwright.dev/todomvc
```
