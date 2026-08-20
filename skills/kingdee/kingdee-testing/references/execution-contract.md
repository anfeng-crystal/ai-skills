# Runtime Execution Contract

Read this card before any HTTP/runtime verification.

## Contract fields

Record these fields in the task or a local non-secret plan:

Assemble them from the current user request, project configuration, and configured connector. A URL, route, or alias may be resolved through read-only configuration discovery after environment, object, action, and scope authorization are explicit; do not ask the user to repeat discoverable technical values. Credential availability is not authorization.

| Field | Requirement |
| --- | --- |
| `mode` | `local`, `dev-test`, `prod-readonly`, or `approved-write` |
| `scope_id` | Stable identifier for this task and target scope |
| `target_alias` | Non-secret environment name; do not persist an internal host if an alias suffices |
| `url` | Exact request URL supplied or configured for this task |
| `method` | Exact HTTP method; read-only modes allow only GET/HEAD/OPTIONS |
| `path_prefix` | Required for `approved-write`; request path must remain below it |
| `approval_ref` | Required for `prod-readonly` and `approved-write` |
| `payload_source` | Required for writes; explicit file or generated task payload, never an inferred payload |
| `request_limit` | Default 1; increase only when the approved task states a bound |
| `expected_evidence` | Status, response field, log marker, or business assertion to verify |
| `rollback` | Required for writes; exact compensating action or statement that the operation is inherently reversible |

## Mode gates

- `local`: keep network probes on loopback. Use Gradle or a harness for repository behavior.
- `dev-test`: require an explicit dev/test target and scope id. Keep requests read-only unless the task switches to `approved-write`.
- `prod-readonly`: require explicit production authorization and bounded evidence. Never infer write permission from read permission.
- `approved-write`: require an exact method and allowed path prefix. One approved contract covers its listed steps; do not ask again inside the contract.

Stop when redirects, discovered endpoints, authentication retries, generated payloads, or cleanup would leave the approved target, method, path, record set, or request limit.

## Credentials and evidence

- Prefer configured task credentials through environment-backed headers or the current approved connector.
- Keep credential values in process memory only. Do not place them in command output, JSON reports, screenshots, fixtures, source, or shell examples.
- Redact response headers and body previews before printing or saving.
- Record auth/permission failure as evidence; do not blindly retry with different accounts or sources.
