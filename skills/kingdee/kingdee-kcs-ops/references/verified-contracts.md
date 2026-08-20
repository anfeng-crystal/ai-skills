# Verified KCS Contracts

## Evidence Boundary

The 2026-07-26 gate found a version-controlled local implementation that performs these two calls and checks their responses. No public official KCS contract was available in the gate, so treat both as `local-observed`, not as a cross-version product guarantee. Re-inspect the target environment before the first write in a different KCS version.

Do not import endpoint lists from the downloaded `console_api` package. Any endpoint not listed below needs `official-primary` or `current-session-capture` evidence in the task plan.

## `service-status`

- Phase: `inspect` or `verify`
- Method/path: `GET /kcs/ajax/service/list_by_ids`
- Query: `zid=<zone-id>`, `cid=<cluster-id>`, `ids=[<service-id>]` encoded as a query value
- Success: HTTP `200`, JSON `errcode == 0`, service record at `data[0]`
- Observed verification fields: `status`, `run_count`, `desired_count`, `lstime`
- Running criterion: `status == 2`, `run_count >= desired_count`, and `desired_count > 0`
- Restart freshness criterion: capture the pre-change `lstime`, put it as the literal right-hand value of a final-plan `json_relations` check, then require a later `lstime` after at least one poll interval

## `service-restart`

- Phase: `apply`
- Method/path: `POST /kcs/ajax/service/restart`
- Encoding: `application/x-www-form-urlencoded`
- Body: `id=<service-id>`, `name=<service-name>`, `zid=<zone-id>`, `strategy=<verified-strategy>`
- Success: HTTP `200`, JSON `errcode == 0`
- Required verify action: `service-status` using the same target identifiers
- Rollback: none. A restart cannot restore the previous process instance; set `irreversible_reason` to that fact and include it in the approved summary rather than inventing a compensating request.

Authentication headers and cookies are environment-specific. Reference their environment-variable names through `headers_from_env`; never store their values in a contract or plan.
