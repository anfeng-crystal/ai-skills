# POC Policy

This skill uses POC only to validate a specific finding, not to discover broadly.

## Allowed By Mode

| Action | audit | verify | redteam-lite |
| --- | --- | --- | --- |
| Static payload sketch | allowed | allowed | allowed |
| Dry-run request plan | allowed | allowed | allowed |
| Single active request | blocked | allowed after scope check | allowed after scope check |
| Multi-payload retry | blocked | user-approved only | bounded and user-approved |
| Broad fuzzing / brute force | blocked | blocked | blocked |
| Destructive payload | blocked | blocked | blocked |

## POC Spec

Use a JSON file for POC requests:

```json
{
  "id": "KD-VERIFY-001",
  "method": "GET",
  "path": "/api/example.do",
  "params": {"q": "test"},
  "headers": {"Accept": "application/json"},
  "body": null,
  "content_type": "application/json",
  "expected": "response contains validation marker"
}
```

Rules:

- Use benign baseline values first.
- Keep payloads minimal and reversible.
- Redact secrets in saved request/response snippets.
- Never write or modify the verification config automatically.
- Temporary files must stay in the user's chosen work area, not inside this skill unless the user explicitly asks.

## Verdicts

- `CONFIRMED`: response behavior directly supports the finding.
- `NOT_REPRODUCED`: request executed but expected signal did not appear.
- `BLOCKED_BY_SCOPE`: scope check refused execution.
- `NEEDS_MANUAL`: auth, state, business precondition, or side effect risk prevents safe automation.
