# Handoff Contract

Every subagent must return a compact handoff. The main agent uses it to relay context to later Reviewers, Testers, or Integrators.

## Format

```text
Result: completed | partially_completed | blocked | no_change_needed
Scope: {actual scope handled}
Changed Files:
- {absolute or repository-relative path, or none}
Behavior Changed:
- {user-visible or internal behavior changed, or none}
Design Decisions:
- {decision and reason, or none}
How To Test:
- {command, manual check, or evidence needed}
Dependencies/Conflicts:
- {dependency on another worker, shared file, or none}
Key Findings:
- {fact the main agent needs}
Verification:
- {command/evidence}: {result}
Risks:
- {remaining risk, assumption, or unknown}
Next Step: {single recommended action}
```

## Requirements

- Use `none` under `Changed Files` when no files changed.
- State exact commands or evidence for verification; do not write “tested” without evidence.
- `Result: completed` requires a repeatable command, cited evidence, or explicit substitute verification.
- Separate facts from assumptions.
- Keep findings short enough for the main agent to scan.
- Mention any file touched outside the assigned ownership scope.
- For Worker handoffs, include enough `Behavior Changed` and `How To Test` detail for a Reviewer/Tester to understand the change without private context.

## Main-Agent Review

Before integrating a handoff:
1. Check that the result matches the assigned scope and ownership lock.
2. Inspect changed files or cited lines.
3. Confirm verification is relevant and not merely cosmetic.
4. Compare risks with the original user goal.
5. Relay Worker handoff + diff summary before asking Reviewer/Tester to evaluate.
6. Decide whether to accept, refine, reassign, rerun, or discard the result.
