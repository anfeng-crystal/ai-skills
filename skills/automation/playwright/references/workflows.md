# Playwright CLI Workflows

Use the cross-platform `pwcli` function from `cli.md`, or call the complete
Node wrapper directly:

```text
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs <command> [args]
```

POSIX:

```sh
pwcli() { node "<active-root>/skills/automation/playwright/scripts/playwright_cli.mjs" "$@"; }
```

PowerShell:

```powershell
function pwcli { node "<active-root>\skills\automation\playwright\scripts\playwright_cli.mjs" @args }
```

In this repo, run commands from `output/playwright/<label>/` to keep artifacts contained.

## Standard interaction loop

```bash
pwcli open https://example.com
pwcli snapshot
pwcli click e3
pwcli snapshot
```

## Form submission

Only click the final submit control when the current request or approved contract covers the submission, target, and scope; do not ask again when it already does. Filling fields is allowed when it does not
trigger that final write.

```bash
pwcli open https://example.com/form --headed
pwcli snapshot
pwcli fill e1 "user@example.com"
pwcli fill e2 "password123"
# The existing task authorization must cover this final business action:
pwcli click e3
pwcli snapshot
pwcli screenshot  # confirm local path/privacy before saving
```

## Data extraction

For a known interactive page, use this CLI workflow. Pure content retrieval,
latest facts, or URL verification still routes to `web-access`.

```bash
pwcli open https://example.com
pwcli snapshot
pwcli eval "document.title"
pwcli eval "el => el.textContent" e12
```

## Multiple tabs

Keep the session and selected tab explicit, and snapshot after switching:

```bash
pwcli --session research open https://example.com/app
pwcli tab-new https://example.com/help
pwcli tab-list
pwcli tab-select 1
pwcli snapshot
pwcli tab-select 0
pwcli snapshot
```

## Wait for an element

Use the current CLI's `run-code` with Playwright's locator API:

```bash
pwcli open https://example.com/results
pwcli run-code "await page.locator('[data-testid=results]').waitFor({ state: 'visible', timeout: 10000 })"
pwcli snapshot
```

## Debugging and inspection

Capture console messages and network activity after reproducing an issue:

```bash
pwcli console warning
pwcli network
```

Record a trace around a suspicious flow:

```bash
pwcli tracing-start
# reproduce the issue
pwcli tracing-stop  # confirm local path/privacy and sensitive data scope
pwcli screenshot    # confirm local path/privacy before saving
```

## Sessions

Use sessions to isolate work across projects:

```bash
pwcli --session marketing open https://example.com
pwcli --session marketing snapshot
pwcli --session checkout open https://example.com/checkout
```

Or set the session once:

```sh
export PLAYWRIGHT_CLI_SESSION=checkout
pwcli open https://example.com/checkout
```

```powershell
$env:PLAYWRIGHT_CLI_SESSION = "checkout"
pwcli open https://example.com/checkout
```

Prefer `--session checkout` when the shell environment differs across
platforms; Windows usage must not depend on bash, `export`, `rm`, `find`, or a
POSIX alias.

## Reuse existing repo assets

- If the user asks for Playwright code, first inspect `playwright.config.*`, existing fixtures, auth setup, wrappers, helpers, page objects, shared selectors, and test utils.
- Prefer extending the repo's existing auth/session helpers, fixtures, and page objects over adding a second helper layer.
- Only create a new spec helper or wrapper when the current repo assets clearly cannot cover the scenario.

## Configuration file

By default, the CLI reads `playwright-cli.json` from the current directory. Use `--config` to point at a specific file.

Minimal example:

```json
{
  "browser": {
    "launchOptions": {
      "headless": false
    },
    "contextOptions": {
      "viewport": { "width": 1280, "height": 720 }
    }
  }
}
```

## Troubleshooting

- If an element ref fails, run `pwcli snapshot` again and retry.
- If the page looks wrong, re-open with `--headed` and resize the window.
- If a flow depends on prior state, use a named `--session`.
