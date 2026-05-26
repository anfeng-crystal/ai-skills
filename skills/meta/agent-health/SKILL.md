---
name: agent-health
description: "Use for read-only health audits when Codex/Claude/agents ignore AGENTS/CLAUDE/skills, skill links or distribution look broken, hooks/MCP drift, or doctor/verifier checks fail."
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [agent, health, codex, claude, skills, config, verifier]
---

# Agent Health

> Cross-platform Agent Skill: read-only by default, redact secrets, and preserve user worktree changes.

## When To Use
- Use for Codex/Claude/agent config drift, ignored instructions, broken skill links, hooks/MCP issues, doctor/verifier failures, or multi-host skill distribution checks.
- Do not review code, fix bugs, optimize SKILL.md, vet third-party skills, sync docs/memory, install/apply links, or clean files here. Route those to the matching skill.

## Contract
- Outcome: health report by layer: config, instructions, runtime, distribution, verifiers, memory-docs.
- Done: each finding has severity, evidence, impact, and a next action or target skill.
- Evidence: current config/files, status, settings, hooks/MCP, symlinks, doctor/verifier output, and dry-run results.
- Output: Critical -> Structural -> Incremental -> Passing -> Residual risk.

## Workflow
1. Confirm scope: active skills source, one project, or global host config. Do not assume the shell cwd is the target.
2. Use summary budget first; go deep only when requested or when summary evidence exposes critical drift.
3. Collect read-only evidence. Start with `git status --short --branch -uall`, then inspect AGENTS/CLAUDE, settings, hooks/MCP, skill links, doctor, verifier, and distribution dry-runs as available.
4. Attribute each issue to one layer. Treat missing optional hosts or `(unavailable)` data as insufficient/optional unless project rules make them required.
5. Route fixes instead of doing them: third-party risk -> `skill-vetter`; SKILL.md quality -> `darwin-skill`; docs/memory drift -> `neat-freak`; link apply -> `skill-installer`; cleanup -> `cleanup-guard`.
6. Report blockers first. Missing scripts or inaccessible surfaces are evidence gaps, not proof of damage.

## Common Commands
```bash
git status --short --branch -uall
node scripts/doctor.mjs --json
node scripts/validate-cross-platform.mjs
node skills/meta/skill-installer/bin/skill-installer.mjs --json
```

Use project-local equivalents when these files do not exist.

## Hard Gates
- No `--apply`, install, symlink edits, memory writes, config edits, cleanup, or destructive git actions.
- Never print secrets, tokens, cookies, sessions, base URLs with credentials, or sensitive internal URLs.
- Codex memory stays to the current task-relevant index; do not enumerate global memory or write memory unless the user explicitly asks and the host allows it.
- Do not treat dry-run output as applied state.
