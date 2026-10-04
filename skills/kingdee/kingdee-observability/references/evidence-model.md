# Runtime Evidence Model

异常、SQL 签名及已知漏检的复核依据见[云端知识](https://chatgpt.com/space/page_ef4ccf12b8c881919ccc548f277fa6e4)；来源字段与未验证边界继续按本文保留。

## Normalized fields

The analyzer recognizes common variants of timestamp, trace/span IDs, parent span ID, service, logger, thread, level, duration, message, exception, SQL, and bind parameters. Missing fields remain unknown; do not infer them from array position except for deterministic display order.

Duration values must be finite and non-negative after conversion to milliseconds: numeric fields use milliseconds, and a complete decimal string may have an `ms` or `s` suffix; invalid values (including booleans) remain unknown unless an explicit `duration`/`elapsed`/`cost`/`took` message marker supplies a valid duration. The slow-SQL threshold must also be finite and non-negative.

## Categories

| Category | Evidence rule | Interpretation limit |
| --- | --- | --- |
| Exception | Exception field, text marker, Java stack, or ERROR/FATAL/SEVERE level | Collection membership alone does not prove an exception type |
| Slow SQL | SQL evidence with duration at or above threshold, or explicit slow-SQL marker | Report normalized SQL only |
| Possible N+1 | Same normalized SQL signature repeats in one trace at or above threshold | Repetition is a candidate, not proof of ORM behavior |
| Thread | Blocking, deadlock, rejection, saturation, or thread-pool marker | Correlate with timestamps and pool metrics |
| GC | Full GC, GC pause, allocation failure, or overhead marker | Correlate with latency; do not equate every pause with root cause |

This local analyzer defaults to 1000 ms for slow SQL and 3 repeats for possible N+1; these are diagnostic heuristics, not Kingdee product logging thresholds. Override only when the task defines a different threshold and report the chosen value.

Exception items retain the source level, redacted message and any explicit exception value. `classificationReasons` lists all matching collection rules: `error_level`, `exception_field`, `text_marker`, and `java_stack`; none invents an exception field or proves a root cause. `text_marker` retains the existing broad keyword heuristic. `java_stack` requires an Exception/Error/Throwable class header immediately followed by an indented Java `at` frame inside the same message (Java source line, Native Method or Unknown Source; optional JVM module/class-loader prefix). Preserve only its boolean match before redaction, since SQL redaction can flatten stack lines; emit only redacted text. A class-name mention, isolated frame or incomplete stack alone does not meet this new rule. Other stack formats remain unverified. Plain-text files still produce one event per nonempty line; adjacent records are never joined to infer a stack or Trace.

## OpenAPI log source boundaries

For evidence from the OpenAPI API 日志 UI, first establish target version, logging level, retention and truncation from available task evidence. This source covers URLs containing `kapi`, not page login calls such as `api/login.do`; an absent login record here is not evidence that login never occurred. API duration and operation duration are separate millisecond fields; a recorded TraceId alone does not provide parent/child spans.

UI column labels are not a machine-export schema. Before using `analyze_logs.py`, map only verified export fields to supported names such as `traceId` and `durationMs`, preserve the original input, and state which duration was selected; do not assume every localized column name is a built-in alias.

The current official manual describes configurable retention (default 30 days) and a default 10000-character cutoff for large request/response text. V7.0.13 adds full text recording for private-cloud tenants through `api_fullPayloadLog`; do not assume older targets or existing exports contain complete payloads. Log gaps or truncation remain evidence limits. Read authorization does not authorize changing logging settings, retention, MC parameters, exporting additional sensitive data, or running cleanup.

Source: [API日志介绍](https://developer.kingdee.com/knowledge/specialDetail/226337046514476288?category=226337544983020032&id=263990262375226880&type=Knowledge&productLineId=29&lang=zh-CN), updated 2025-12-19 10:06; initial V5.0.001, full text option V7.0.13. Do not apply these OpenAPI defaults to all runtime, monitor, GC or ISC logs.

## Trace topology

- Build nodes from span IDs and parent span IDs.
- Mark a node with an absent parent as `missingParent`.
- Break cycles deterministically and report a warning.
- When span IDs are absent, retain ordered evidence but do not fabricate a causal tree.

## Confidence

- `confirmed`: directly present in source evidence.
- `correlated`: multiple independent observations align in one trace/time window.
- `hypothesis`: plausible explanation requiring another read-only check.

Always state data truncation, invalid lines, missing timestamps, missing parents, and timezone ambiguity.
