# Task Splitting

## Decision First

Before assigning agents, make a split decision and state the reason. Multi-agent work is useful only when the work has clear boundaries, transferable context, and independent verification.

## No Split

Use `No split` when any of these are true:
- The task is a single-file or small local change.
- The next step depends on immediate judgment from the main agent.
- Implementation and verification cannot be explained through a compact handoff.
- Most changes hit one shared schema, DTO, contract, helper, fixture, or config.
- Splitting would create more coordination cost than execution value.

When choosing `No split`, the main agent does the work locally and may still use a checklist before final delivery.

## Explorer-only

Use `Explorer-only` when the root cause is unknown or evidence can be gathered independently without writes.

Good Explorer splits:
- Trace backend auth failure paths.
- Inspect frontend state flow.
- Check config, logs, schema, or metadata.
- Compare existing helper/wrapper usage across modules.

Explorers must stay read-only and return cited evidence.

## Single Worker

Use `Single Worker` when one owner must control the implementation:
- Shared schema, DTO, API contract, public type, or migration.
- Public helper/wrapper used by multiple consumers.
- One core module where partial parallel edits would conflict.

Other agents may be Reviewers, Testers, or downstream consumer adapters, but they must not modify the shared owner files.

## Staged Pipeline

Use `Staged pipeline` when testing or review depends on implementation details:
1. Explorer or main agent clarifies scope.
2. Worker implements within an ownership lock.
3. Main agent relays Worker handoff + diff summary + acceptance criteria.
4. Reviewer/Tester evaluates the actual change.
5. Main agent integrates feedback and verifies.

Do not ask a Tester to validate a Worker change without the Worker handoff.

## Parallel Workers

Use `Parallel Workers` only when all are true:
- Each Worker has a non-overlapping write scope.
- Each Worker has its own verification path.
- Shared contract files have a single owner.
- Expected outputs can be merged by evidence, not by guessing intent.

Good splits:
- Frontend form owner + backend validation owner after API contract is fixed.
- Parser module owner + renderer module owner with stable interface.
- Implementation owner + independent test owner only after test owner receives the implementation handoff.

## Shared Contract Files

Shared DTO, schema, API contract, public constants, test fixtures, migrations, and cross-platform types must have one write owner.

Process:
1. Assign one owner for the shared file.
2. Convert other Workers to consumers, Explorers, or Reviewers.
3. Relay the owner handoff to consumer agents before they adapt downstream code.
4. Never let two Workers independently modify the same shared contract.

## Ownership Template

```text
Role: Worker
Goal: {specific goal}
Model profile: {fast_probe | deep_research | code_worker | reviewer | integrator}
Owned scope: {files, directories, modules, or behavior}
Do not touch: {forbidden scope}
Shared contract owner: {yes/no; file if yes}
Expected output: {patch/report/handoff}
Verification: {required or recommended command/evidence}
```
