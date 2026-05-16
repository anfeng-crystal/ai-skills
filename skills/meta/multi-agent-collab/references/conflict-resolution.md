# Conflict Resolution

## Overlapping Writes

When two agents touch the same file, shared contract, or behavior:
1. Stop assigning new work in that area.
2. Identify the ownership lock for the file or behavior.
3. Keep the owner result as the primary candidate.
4. Downgrade non-owner changes to `advisory` unless they are clearly independent.
5. Manually integrate only evidence-backed parts.
6. Re-run focused verification.

## Reassign

Use `reassign` when the main agent must take over or move work to a different agent:
1. Record why the original owner cannot continue.
2. Mark the old result as `keep`, `advisory`, or `discard`.
3. Create a new ownership lock.
4. Relay any still-useful findings to the new owner.
5. Verify that no stale patch is merged accidentally.

The main agent must not silently implement a Worker-owned scope. Reassign first.

## Out-of-Scope Changes

If a Worker edits outside its scope:
- Treat the result as unsafe by default.
- Inspect the out-of-scope diff.
- Accept only the parts needed for the user goal and supported by evidence.
- If the out-of-scope edit touches a shared contract, reroute through the shared contract owner.

## Contradictory Findings

When agents disagree:
1. Prefer direct evidence over confidence language.
2. Re-open cited files, logs, tests, or docs.
3. Reduce the disagreement to a smaller factual question.
4. Resolve locally if the evidence is available.
5. If still uncertain, report the uncertainty and the safest next verification step.

## Arbitration Order

When two results both look plausible, decide in this order:
1. Prefer the result from the assigned owner.
2. Prefer reproducible evidence.
3. Prefer the result that preserves the user's requested behavior.
4. Prefer the smaller blast radius.
5. Prefer stronger tests or verification.
6. If still tied, keep one owner and downgrade the other result to advisory notes.

## Failed or Blocked Agents

If a subagent fails, times out, or returns vague output:
- Do not wait repeatedly without a reason.
- Continue with local work when possible.
- Reassign only if the missing result materially blocks the goal.
- Record the blocked result in the final risk section if it affects confidence.

## User Direction Changes

If the user changes the goal, priority, or acceptance criteria while agents are active:
1. Pause new delegation.
2. Classify existing handoffs as `keep`, `advisory`, or `discard`.
3. Rebuild the Coordination Plan from the newest user request.
4. Reassign only the work that still matches the new goal.
5. Report discarded work only if it affects risk, cost, or verification.

Use `keep` only when the old result still directly satisfies the new scope. Use `advisory` for evidence that may inform the new plan. Use `discard` for stale implementation work.

## Integration Rule

Never merge by popularity. Merge by ownership, evidence, tests, and alignment with the user's requested outcome.
