# Minimal Change Card

## Trigger

Use this card before changing any Kingdee skill, script, template, metadata helper, or generated artifact.

## Rules

- Read the closest existing implementation before editing.
- Change only the files required by the current request or approved plan.
- Do not reformat, rename, reorganize, or "improve" adjacent code while solving a different problem.
- Do not add a new abstraction for a single use case.
- Do not add new dependencies, public interfaces, file layout changes, or host assumptions unless the approved plan explicitly requires them.
- Clean up only unused code or files created by the current change.

## Traceability Check

Before finishing, every changed line must answer one question: "Which explicit requirement or approved plan item needs this line?"

If a line only exists because it might be useful later, remove it.

## Output

Report:

- changed files
- why each file changed
- validation performed
- unrelated issues observed but not changed
