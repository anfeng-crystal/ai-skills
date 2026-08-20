# Runtime Evidence Model

## Normalized fields

The analyzer recognizes common variants of timestamp, trace/span IDs, parent span ID, service, logger, thread, level, duration, message, exception, SQL, and bind parameters. Missing fields remain unknown; do not infer them from array position except for deterministic display order.

## Categories

| Category | Evidence rule | Interpretation limit |
| --- | --- | --- |
| Exception | Exception field, stack marker, or error/fatal level | Error level alone does not prove an exception type |
| Slow SQL | SQL evidence with duration at or above threshold, or explicit slow-SQL marker | Report normalized SQL only |
| Possible N+1 | Same normalized SQL signature repeats in one trace at or above threshold | Repetition is a candidate, not proof of ORM behavior |
| Thread | Blocking, deadlock, rejection, saturation, or thread-pool marker | Correlate with timestamps and pool metrics |
| GC | Full GC, GC pause, allocation failure, or overhead marker | Correlate with latency; do not equate every pause with root cause |

Defaults are 1000 ms for slow SQL and 3 repeats for possible N+1. Override only when the task defines a different threshold and report the chosen value.

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
