---
name: kingdee-security-review
description: "Use when reviewing Kingdee Cosmic security issues, auditing OpenAPI endpoints, verifying community/external findings against target evidence, performing authorized production read-only checks, or running scoped POC/redteam-lite validation."
license: MIT
metadata:
  author: "anfeng"
  version: "1.1.0"
  tags: "kingdee, cosmic, security, audit, openapi, poc"
---

# Kingdee Security Review
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## Trigger and routing

- Use this skill for Kingdee Cosmic security audit, OpenAPI endpoint review, vulnerability verification, scoped POC checks, and redteam-lite validation.
- Use `kingdee-cosmic` for ordinary plugin implementation or troubleshooting, `kingdee-metadata-analyzer` for metadata evidence, and `kingdee-sdk-helper` for SDK signatures.
- This skill never submits DMP bugs or writes external audit systems automatically. Generate material only; the user decides submission.
- Do not migrate, invoke, or depend on the old graph setup component from the source bundle.

## Modes

Choose one mode before acting:

| Mode | Purpose | Network / POC |
| --- | --- | --- |
| `audit` | Static source review, endpoint discovery, report writing | No network |
| `audit-readonly` | Bounded HEAD/GET or metadata/status evidence against a known target | Requires target, known scope and authorization reference; production read-only is allowed |
| `verify` | Confirm reported findings against a known dev/test target | Requires target scope check |
| `redteam-lite` | Limited active payload checks inside an approved boundary | Requires explicit target and boundary |

Read `references/modes.md` when the user asks for verification, active testing, or any request that could touch a running service.

## Safety gates and failure

1. For `audit`, stay local. For `audit-readonly`, require exact target, declared non-unknown scope, authorization reference, endpoint allowlist, request bound and timeout; contract complete后无需重复确认。
2. For `verify` or `redteam-lite`, run `scripts/scope_check.py` first with mode, target URL, and declared scope.
3. Production read-only checks may run in `audit-readonly`; active production POC remains default-deny and only continues when the command records target URL, scope, time window, allowed payload types, forbidden actions and explicit production authorization.
4. Use `scripts/poc_runner.py` in dry-run mode first. Add `--execute` only after scope is allowed and the request spec is reviewed.
5. Use `scripts/network_probe.py` only for bounded reachability checks; default is dry-run.
6. Redact credentials, cookies, tokens, tenant ids, and session identifiers in chat summaries and reports unless the user explicitly requests raw values.
7. Do not read browser state, shell history, env, or project config for Cookie/token/account material unless the user explicitly names that source and purpose.
8. Never print credentials or sensitive response headers; dry-run plans and execution summaries must redact Authorization, Cookie, Set-Cookie, tokens and password-like values.

## Workflow

1. Identify mode, target repo/path, endpoint or finding list, and whether network access is requested.
2. For API endpoint work, read `references/openapi-audit.md`; confirm endpoint location, handler method, request parameters, and auth/filter chain before rating severity.
3. When a claim comes from a community article, project snippet, external report or old POC, read `references/evidence-sources.md` and treat it as a candidate until target-version evidence confirms it.
4. For vulnerability classes and static checks, read `references/security-controls.md`; cite sink, taint source, sanitizer, kill switch, and missing control.
5. For verification and payload handling, read `references/poc-policy.md` and `references/target-scope.md`.
6. For page, operation, OpenAPI, or plugin-entry scope, read `references/metadata-security-scope.md` and prefer a `kingdee-metadata-analyzer` metadata contract before active verification.
7. Write findings with `scripts/report_writer.py` when a structured report is requested. Reports default to redacted targets, tenants, sessions, and raw evidence; raw evidence requires an explicit destination and user approval.

## Script Commands

Run from this skill directory or pass absolute script paths:

```bash
python3 scripts/scope_check.py --help
python3 scripts/poc_runner.py --help
python3 scripts/network_probe.py --help
python3 scripts/report_writer.py --help
```

Common guarded flow:

```bash
python3 scripts/scope_check.py --mode verify --target-url https://dev.example/ierp --scope dev
python3 scripts/network_probe.py --mode audit-readonly --target-url https://prod.example/ierp --scope prod --reason "<authorization-ref>" --connect
python3 scripts/poc_runner.py --mode verify --target-url https://dev.example/ierp --scope dev --poc-file poc.json
python3 scripts/poc_runner.py --mode verify --target-url https://dev.example/ierp --scope dev --poc-file poc.json --execute
```

## Output

Use Chinese by default. Report:

- conclusion first;
- evidence: files, endpoints, call chain, auth boundary, sanitizer status;
- mode and target scope;
- findings ordered by severity;
- verification state: unverified, statically confirmed, dynamically verified, blocked by scope, or needs manual confirmation;
- residual risk and next action.
- evidence source state: source-only candidate, statically confirmed, dynamically verified, not reproduced, or blocked by scope.
