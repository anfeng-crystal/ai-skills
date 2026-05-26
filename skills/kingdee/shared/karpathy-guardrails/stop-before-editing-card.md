# Stop Before Editing Card

## Stop Conditions

Pause and ask for clarification before editing when any of these are true:

- the requested write scope is unclear or conflicts with an existing worker's scope
- the change would modify files outside the approved directories
- the task requires deleting source material or existing active skills
- the task would introduce host-specific paths into shared skill logic
- the implementation requires credentials, production access, or live metadata changes not already approved
- multiple plausible interpretations would lead to different files or behavior

## Allowed Conservative Assumptions

Proceed without another question only when the change is local, reversible, and directly implied by the approved plan.

Examples:

- creating a missing documentation directory inside the approved write scope
- summarizing a source skill into a guardrail card without copying host-specific setup
- recording skipped sources in a cleanup manifest instead of deleting them

## Handoff Note

When stopping, report:

- the exact ambiguity
- the files that would be affected
- the safest narrow option
- the risk of proceeding without confirmation
