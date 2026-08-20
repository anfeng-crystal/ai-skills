# Runtime Verification

Use this card after selecting a mode in `SKILL.md`; read `execution-contract.md` before sending a request.

## Procedure

1. Record the mode, scope id, target alias, exact URL/method, expected evidence, and request limit.
2. For `prod-readonly` or `approved-write`, record the approval reference. For writes, also record path prefix, payload source, rollback, and before/after assertions.
3. Validate the request without network:

```text
python scripts/run_dev_probe.py --mode MODE --scope-id SCOPE --target-alias TARGET --url URL --method METHOD --expected-evidence EXPECTATION --dry-run
```

4. Supply configured credentials through `--header-env Header=ENV_NAME`; never place credential values in arguments.
5. Execute once, inspect the redacted evidence, and stop on auth, CSRF, redirect, permission, scope, or assertion failure.
6. Compare runtime evidence with local test results. Keep “local passed” and “runtime verified” as separate states.

## Evidence

Keep only the sanitized target, method, mode, scope id, status, elapsed time, selected response headers, capped redacted preview, expected assertion, and result. Do not persist request credentials or payloads.
