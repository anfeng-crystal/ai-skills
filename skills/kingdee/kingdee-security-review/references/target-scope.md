# Target Scope

## Scope Values

| Scope | Meaning | Active POC default |
| --- | --- | --- |
| `local` | localhost, loopback, local sandbox | allowed |
| `dev` | development environment | allowed |
| `test` | test or QA environment | allowed |
| `staging` | pre-production with explicit testing permission | allowed |
| `prod` | production, customer, or business live environment | read-only allowed by contract; active POC blocked by default |
| `unknown` | cannot prove scope | blocked |

## Required Checks

For `verify` and `redteam-lite`, collect:

- exact target URL;
- declared scope;
- authorization statement from user or ticket;
- endpoint allowlist or finding id;
- credential source, if any;
- maximum request count and stop condition for active checks.

Run:

```bash
python3 scripts/scope_check.py --mode verify --target-url <url> --scope <scope>
```

Production or unknown targets require explicit flags and a user-provided reason:

```bash
python3 scripts/scope_check.py --mode verify --target-url <url> --scope prod --allow-prod --reason "<authorization>"
```

For `audit-readonly`, collect the exact target, non-unknown declared scope, authorization reference, endpoint allowlist, request bound and timeout. Production read-only does not require `--allow-prod`; the authorization reference in `--reason` is required.

## Default Deny Rules

- Do not infer production safety from "internal" or VPN reachability.
- Do not run POC against unknown domains, public IPs, or customer tenants without explicit authorization.
- Do not use credentials found in code, logs, screenshots, or config files unless the user explicitly authorizes their use.
- Do not expand from one endpoint to broad fuzzing.
