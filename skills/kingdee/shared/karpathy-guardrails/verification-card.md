# Verification Card

## Trigger

Use this card after changing Kingdee skill files, scripts, routing rules, platform adapters, or cleanup manifests.

## Define Success Before Editing

For each task, write the concrete pass condition before implementation:

- documentation change: target files exist, scope is correct, excluded sources are listed
- script change: syntax checks pass and help/dry-run paths work
- migration change: source, absorbed content, and skipped content are recorded
- cleanup change: no source directory or active skill is deleted unless separately approved

## Default Checks

Run the narrowest useful checks for the changed surface. For shared guardrails and cleanup files, use:

```bash
cd /Users/anfeng/AI/skills/active
git ls-files | rg '\\' || true
find skills/kingdee -name '.DS_Store' -print
rg -n "kdcodetrigger|ClaudeCodeKDSkills|~/.claude|~/.codex|\\.qoder" skills/kingdee
```

## Interpreting Expected Hits

The keyword scan may find intentionally documented exclusions in cleanup or adapter documentation. Treat those hits as acceptable only when they are descriptive records and no executable route, copied skill, or host-specific bad path was introduced.

## Report

Summarize command outcomes instead of pasting full noisy output. Include any command that could not run, any non-empty risk signal, and whether the signal is expected or needs follow-up.
