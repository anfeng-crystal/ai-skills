# UI Execution Contract

Validate this contract before browser execution.

## Required fields

| Field | Requirement |
| --- | --- |
| `taskId` | Current task identifier |
| `mode` | One of the five modes in `SKILL.md` |
| `environmentClass` | `none`, `local`, `dev-test`, or `prod` as allowed by mode |
| `targetRef` | Configured non-URL environment alias for execution modes |
| `caseIds` | Exact normalized cases permitted |
| `allowedActions` | Exact action names permitted across those cases |
| `maxCases` | Upper bound for executed cases |
| `maxWrites` | Zero for read-only modes; explicit positive bound for approved write modes |
| `approvalRef` | Required for approved writes and both production modes |

Do not store URLs, usernames, passwords, tokens, cookies, request headers, browser storage, or session files in the contract.

## Write-mode fields

`approved-crud` and `approved-prod-e2e` also require:

- `testDataPrefix`: at least six letters, digits, `_`, or `-`; apply it to every record identifier/name.
- `beforeAssertions`: non-empty stable checks captured before writes.
- `afterAssertions`: non-empty checks proving the intended result.
- `cleanup`: bounded strategy and steps operating only on recorded prefixed data.
- `rollback`: bounded strategy and steps for restoring the before state.

Approval of the complete contract removes repeated per-step confirmation inside these bounds. A discovered operation, different target, missing prefix, extra case, selector with a write effect, or failed before assertion requires stopping.

## Failure handling

- On an assertion failure, stop dependent writes and preserve evidence.
- On cleanup failure, stop all further writes and report residual identifiers.
- On rollback failure, do not retry broadly or search/delete by partial text.
- Never reinterpret `prod-safe-smoke` as write permission.
