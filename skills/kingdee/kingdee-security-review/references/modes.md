# Modes

## `audit`

Static, local, read-only review.

- Inputs: repo path, file path, endpoint path, class/method, diff, or report draft.
- Allowed: read files, grep, trace data flow, inspect config, produce report.
- Not allowed by default: HTTP calls, payload execution, login, destructive checks, brute force, fuzzing.
- Output verification state: `statically confirmed`, `unverified`, or `needs manual confirmation`.

## `verify`

Dynamic confirmation of an existing finding against a known non-prod target.

- Required inputs: target URL, declared scope, finding or POC spec.
- Required gate: `scripts/scope_check.py --mode verify --target-url <url> --scope <dev|test|staging|local>`.
- Default allowed scopes: `dev`, `test`, `staging`, `local`.
- Default blocked scopes: `prod`, `unknown`.
- Run `poc_runner.py` without `--execute` first and review the generated request plan.

## `redteam-lite`

Limited active validation inside a specific boundary. This is not broad red teaming.

- Required inputs: target URL, declared scope, allowed endpoints, max request count, auth assumptions, and stop conditions.
- Required gate: `scripts/scope_check.py --mode redteam-lite --target-url <url> --scope <dev|test|staging|local>`.
- Allowed only for narrow payload families relevant to the finding.
- Stop immediately on auth failure, unexpected 5xx spikes, rate-limit responses, sensitive data exposure, or user cancellation.

## Mode Selection

| User intent | Mode |
| --- | --- |
| "审计这段代码" | `audit` |
| "查这个 OpenAPI 有没有漏洞" | `audit` unless a live target is requested |
| "对 dev 接口跑 POC 验证" | `verify` |
| "确认报告里的漏洞是否真实可利用" | `verify` |
| "在测试环境做轻量攻击面验证" | `redteam-lite` |

If the user gives a live target but no mode, choose `verify` only when the target is clearly dev/test/staging/local; otherwise ask for scope confirmation before any active request.
