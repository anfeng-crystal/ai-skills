---
name: kingdee-security-review
description: "Use when reviewing Kingdee Cosmic security issues, auditing OpenAPI endpoints, verifying findings in dev/test, or running scoped redteam-lite checks."
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [kingdee, cosmic, security, audit, openapi, poc]
---

# Kingdee Security Review
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## Routing

- Use this skill for Kingdee Cosmic security audit, OpenAPI endpoint review, vulnerability verification, scoped POC checks, and redteam-lite validation.
- Use `kingdee-cosmic` for ordinary plugin implementation or troubleshooting, `kingdee-metadata-analyzer` for metadata evidence, and `kingdee-sdk-helper` for SDK signatures.
- This skill never submits DMP bugs or writes external audit systems automatically. Generate material only; the user decides submission.
- Do not migrate, invoke, or depend on the old graph setup component from the source bundle.

## Modes

Choose one mode before acting:

| Mode | Purpose | Network / POC |
| --- | --- | --- |
| `audit` | Static source review, endpoint discovery, report writing | Not allowed by default |
| `verify` | Confirm reported findings against a known dev/test target | Requires target scope check |
| `redteam-lite` | Limited active payload checks inside an approved boundary | Requires explicit target and boundary |

Read `references/modes.md` when the user asks for verification, active testing, or any request that could touch a running service.

## Safety Gates

1. For `audit`, stay local and read-only unless the user explicitly asks for report output.
2. For `verify` or `redteam-lite`, run `scripts/scope_check.py` first with mode, target URL, and declared scope.
3. Default-deny production and unknown targets for active POC. Continue only when the user explicitly authorizes prod/unknown scope and the command records that authorization.
4. Use `scripts/poc_runner.py` in dry-run mode first. Add `--execute` only after scope is allowed and the request spec is reviewed.
5. Use `scripts/network_probe.py` only for bounded reachability checks; default is dry-run.
6. Redact credentials, cookies, tokens, tenant ids, and session identifiers in chat summaries and reports unless the user explicitly requests raw values.

## Workflow

1. Identify mode, target repo/path, endpoint or finding list, and whether network access is requested.
2. For API endpoint work, read `references/openapi-audit.md`; confirm endpoint location, handler method, request parameters, and auth/filter chain before rating severity.
3. For vulnerability classes and static checks, read `references/security-controls.md`; cite sink, taint source, sanitizer, kill switch, and missing control.
4. For verification and payload handling, read `references/poc-policy.md` and `references/target-scope.md`.
5. For page, operation, OpenAPI, or plugin-entry scope, read `references/metadata-security-scope.md` and prefer a `kingdee-metadata-analyzer` metadata contract before active verification.
6. Write findings with `scripts/report_writer.py` when a structured report is requested.

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
