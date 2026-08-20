# KCS Plan Contract

## Top Level

Draft and finalized plan fields:

| Field | Contract |
|---|---|
| `schema_version` | Integer `1` |
| `target` | `label`, origin-only `base_url`, `environment` (`dev`, `test`, `prod`, `unknown`) |
| `contract_evidence` | `kind` (`official-primary`, `local-observed`, `current-session-capture`), non-secret `reference`, optional `verified_at` |
| `actions` | Ordered unique action objects |
| `plan_sha256` | Added by `plan`; SHA-256 of canonical UTF-8 JSON excluding this field |

`https` is required except for loopback mock servers. URLs containing credentials, query strings, fragments, or a non-root base path are rejected.

## Action

Required fields:

- `id`: unique task-local identifier.
- `phase`: `inspect`, `apply`, `verify`, or `rollback`.
- `risk`: `read-only`, `write`, or `destructive`.
- `method`: `GET`/`HEAD` for read-only phases; `POST`/`PUT`/`PATCH`/`DELETE` for write phases.
- `path`: relative API path beginning `/kcs/`; no host, query, backslash, or parent traversal.
- `expect.http_status`: non-empty list of accepted HTTP statuses.

Optional fields:

- `description`: short action purpose.
- `query`: scalar or scalar-list query values.
- `headers`: non-secret fixed headers only.
- `headers_from_env`: `{header_name: environment_variable_name}`; values exist only in process memory.
- `encoding`: `none`, `json`, or `form`; `body` must match it.
- `expect.json_equals`: `{dot.path: value}`.
- `expect.json_relations`: `{left, op, right}` or `{left, op, right_path}`; `op` is `==`, `!=`, `>`, `>=`, `<`, or `<=`.
- `response_policy`: `sanitized-json` or `summary`.
- `verify_actions`: IDs of `verify` actions.
- `rollback_action`: ID of a `rollback` action.
- `irreversible_reason`: required for any apply action without rollback.

Every apply and rollback action must reference at least one `verify` action. Query/body fields that look like credentials are rejected; authentication values belong only in environment variables named by `headers_from_env`.

## Minimal Draft Shape

```json
{
  "schema_version": 1,
  "target": {
    "label": "approved-target-label",
    "base_url": "https://kcs.example.invalid",
    "environment": "test"
  },
  "contract_evidence": {
    "kind": "local-observed",
    "reference": "task evidence identifier",
    "verified_at": "2026-07-26T00:00:00Z"
  },
  "actions": [
    {
      "id": "status",
      "phase": "inspect",
      "risk": "read-only",
      "method": "GET",
      "path": "/kcs/ajax/service/list_by_ids",
      "query": {"zid": "2", "cid": "1685", "ids": "[3]"},
      "headers_from_env": {"Cookie": "KCS_TASK_COOKIE"},
      "expect": {"http_status": [200], "json_equals": {"errcode": 0}},
      "response_policy": "sanitized-json"
    }
  ]
}
```

Use placeholders only while drafting. Replace target and resource identifiers before generating the plan; the generated digest is the object the user approves.
