# Read-only Query Contract

Use this card only for `dev-query` or `prod-readonly`.

## Plan shape

Create UTF-8 JSON with these fields:

| Field | Requirement |
| --- | --- |
| `mode` | `dev-query` or `prod-readonly` |
| `scopeId` | Current task/query scope identifier |
| `targetRef` | Configured environment alias; URLs are rejected |
| `queryType` | `trace`, `time-window`, `service`, `exception`, or `slow-sql` |
| `filters` | Exact `traceId`, or bounded ISO-8601 `start` and `end`; optional service/level/keyword |
| `maxRecords` | 1–5000; production maximum 1000 |
| `approvalRef` | Required for `prod-readonly` |
| `redaction` | Must be `true` |

Do not place credentials, cookies, tokens, sessions, storage state, request headers, internal URLs, or database connections in the plan.

## Execution

1. Run `scripts/validate_query_plan.py --input PLAN`.
2. Resolve `targetRef` through the connector or task configuration already authorized for the request.
3. Execute only a read API matching `queryType`; keep the validated record and time bounds.
4. Pass returned records to `scripts/analyze_logs.py --source-mode MODE`.
5. Stop on authentication, permission, redirect, unsupported version, or incomplete pagination. Do not switch accounts, URLs, or query semantics implicitly.

Production windows may not exceed 60 minutes. Prefer Trace ID queries or smaller windows before increasing result count.
