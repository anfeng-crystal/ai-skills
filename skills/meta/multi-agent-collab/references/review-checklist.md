# Review Checklist

Use this before final delivery.

## Coordination

- A split decision exists, including why the work was or was not split.
- Host capabilities were considered before claiming real delegation.
- Each subagent had a bounded scope, clear output, verification, and `model_profile`.
- Worker scopes did not overlap.
- Shared contract files had one write owner.
- Explorer agents stayed read-only.
- Reviewer/Tester agents received Worker handoff + diff summary + acceptance criteria.
- Fallback or serial simulation still used the handoff contract.

## Integration

- Changed files were inspected by the main agent.
- The main agent did not implement a Worker-owned scope without reassigning it first.
- Unrelated user or agent changes were not reverted.
- Acceptance gates were checked before final delivery.
- Code-writing Workers checked existing helpers, wrappers, templates, SDKs, fixtures, scripts, and standard services before adding new methods.
- Any new helper or wrapper includes a clear reason why existing assets were insufficient.
- Contradictions were resolved or reported.
- New user direction changes rebuilt the Coordination Plan.
- Final behavior was validated with the strongest available command.
- Missing tests used the verification priority order or were reported as unverified.
- Remaining risks are explicit.

## Final Answer

- Start with the result.
- Mention split decision and execution mode only when useful.
- Summarize who did what only when it affects trust or risk.
- Mention verification commands and outcomes.
- Mention unverified areas.
- Keep the answer concise and actionable.
