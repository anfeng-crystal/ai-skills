---
name: kingdee-observability
description: "通过离线日志或已授权的只读查询，诊断金蝶云苍穹/星瀚的 Trace、异常和性能问题。"
---

# Kingdee Observability
> Cross-platform Agent Skill: use UTF-8, host-neutral paths, and the current task's configured tools.

## 触发与路由

- Use this skill for runtime logs, Trace reconstruction, slow SQL/N+1, exception, thread, or GC evidence.
- Route Java source fixes to `kingdee-cosmic`, test execution to `kingdee-testing`, and ISC DSL or mapping changes to `iscb-script`; diagnose ISC execution logs here.

## 模式与契约

| Mode | Source | Gate |
| --- | --- | --- |
| `offline` | User-provided JSON, JSONL, NDJSON, or text | Default; do not query a runtime |
| `dev-query` | Named dev/test log or monitor target | Explicit target reference, bounded filters, read-only query |
| `prod-readonly` | Named production log or monitor target | Explicit approval reference, bounded time/filter/result count, read-only query |

An approved query plan authorizes every read inside its exact bounds; do not ask again per page or batch. Stop before expanding the target, time range, filters, record count, endpoint family, or credential source.

## 工作流

1. For `offline`, preserve the input and analyze it directly.
2. For query modes, read `references/query-contract.md`, validate a non-secret plan with `scripts/validate_query_plan.py`, then use only a currently configured connector or task-provided client. This skill contains no login or network client.
3. Keep configured task credentials in the active client/process only. Never echo, save, cache, or copy credentials, cookies, tokens, browser state, or internal URLs into plans or reports.
4. Analyze retrieved records with `scripts/analyze_logs.py`; never copy raw candidate scripts or disable TLS verification.
5. Distinguish source facts, derived evidence, and diagnostic inference. Complete the requested diagnosis with the narrowest supported conclusion, its evidence and remaining gaps; do not claim root cause from a single correlated symptom or require every diagnostic category for every request.

## Diagnose

- Reconstruct trace roots and parent/child spans when IDs exist; mark missing parents and cycles.
- Separate explicit exceptions from error-level messages.
- Report slow SQL with duration and normalized signature; never emit literal values or bind parameters.
- Detect possible N+1 only when the same normalized SQL signature repeats within one trace above the configured threshold.
- Report thread blocking/rejection and GC pause/allocation evidence separately.
- Correlate timestamps and services, then state the narrowest supported hypothesis and missing evidence.

Read `references/evidence-model.md` when interpreting fields, thresholds, trace topology, or confidence.

## Use deterministic helpers

- `scripts/redact.py`: recursively redact a JSON artifact or import its redaction functions.
- `scripts/validate_query_plan.py`: validate `dev-query` or `prod-readonly` scope without network access.
- `scripts/analyze_logs.py`: parse, redact, classify, and emit deterministic JSON evidence.

All scripts use UTF-8, `pathlib`, and explicit input/output paths; paths may contain spaces and use Windows or POSIX separators. If `--output` is omitted, print JSON to stdout. Never delete or overwrite the input.

## 门禁与失败

- Do not use fixed service URLs, bundled accounts, browser sessions, or persisted credentials.
- Do not query production without an explicit `prod-readonly` contract and approval reference.
- Do not emit tenant, account, person, email, phone, IP, internal host, database connection, SQL literal, or SQL parameter values.
- Do not turn read authorization into write, configuration, restart, deployment, DMP, database, or source-clone authorization.
- Treat truncated, reordered, timezone-ambiguous, or cross-trace evidence as incomplete.

## 输出

Use Chinese. Lead with the supported diagnosis, then list mode and query contract, evidence by category, trace topology, redactions applied, confidence, missing evidence, and next read-only check.
