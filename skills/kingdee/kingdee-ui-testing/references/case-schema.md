# Normalized UI Test Cases

Use one case object per business scenario:

| Field | Meaning |
| --- | --- |
| `caseId` | Stable unique ID |
| `name` | Business scenario name |
| `priority` | `P0`, `P1`, `P2`, or `P3` |
| `requirements` | Requirement IDs covered by the case |
| `preconditions` | Observable setup facts, not credentials |
| `steps` | Ordered step objects |

Each step contains `stepId`, `order`, `action`, `target`, `data`, `expected`, `mutates`, and `effect`.

## Action vocabulary

Read-only actions: `navigate`, `inspect`, `assert`, `screenshot`, `wait`, `search`, `open`, `close`, `paginate`, `switch-tab`.

Write-capable actions: `input`, `select`, `upload`, `save`, `create`, `update`, `delete`, `submit`, `audit`, `unaudit`, `enable`, `disable`, `workflow`, `cleanup`, `rollback`.

Use `click` only with an explicit `effect`. Mark it `mutates=true` unless the effect is one of `navigation`, `open`, `close`, `paginate`, `switch-tab`, or `inspect`.

## CSV columns

Use one row per step. Supported columns are `case_id`, `case_name`, `priority`, `requirements`, `preconditions`, `step_id`, `step_order`, `action`, `target`, `data`, `expected`, `mutates`, and `effect`. Separate list values with `|`.

Never place authentication data, browser storage, tenant-specific URLs, or reusable session material in a testcase.
