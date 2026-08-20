# Testcase Completeness

Use this card before generating tests and again before reporting coverage.

## Build the inventory

For each public behavior, list the observable contract, inputs, collaborators, state, branches, outputs, side effects, and failure modes. Mark every case as `required`, `risk-based`, or `excluded` with a reason.

Cover applicable dimensions:

| Dimension | Minimum cases |
| --- | --- |
| Nominal | One representative successful path with meaningful assertions |
| Null/empty | `null`, empty string, empty collection, missing DynamicObject field |
| Boundary | Zero, one, maximum/minimum, equality boundary, before/at/after date |
| Collection | Zero/one/many, duplicate entries, stable order when contractual |
| Branch | Every business predicate outcome and early return |
| Exception | Collaborator error, invalid input, retry/fallback, exception propagation |
| Side effect | Expected call and absence of forbidden calls on rejected paths |
| State | Every allowed transition and at least one rejected transition |
| Context | User, tenant/account, locale, time, and permission variants actually read by source |
| Metadata | Confirmed field/form/entry variants only; block invented keys |
| Idempotency | Repeat execution when the behavior promises idempotency or deduplication |

## Trace cases to source

Maintain a compact matrix:

```text
behavior -> source branch -> testcase -> assertion/verify -> execution result
```

Line and branch coverage are supporting evidence, not proof of behavioral completeness. Keep the existing 90% line and 80% branch targets when the project uses this gate, but report uncovered business scenarios separately.

## Reject weak coverage

- Do not count getters, setters, constructors, or pure delegation solely to raise coverage.
- Do not count a test that swallows an exception, exits before assertions, or only verifies mock setup.
- Do not copy the current defective output into an assertion when the intended contract is known.
- Do not broaden production or runtime scope to fill a local coverage gap.

## Completion report

List required cases passed, required cases blocked, risk-based cases deferred, justified exclusions, and whether evidence is static, local-executed, or runtime-verified.
