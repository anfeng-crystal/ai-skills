---
name: delivery-check
description: "Use before commit, push, merge, package, release, publish, skill sync, or when asked 能不能交付/能不能发版/发布前检查. Not for code review, implementation, cleanup, or install/apply actions."
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [delivery, release, readiness, git, package, verification]
---

# Delivery Check

> Cross-platform Agent Skill: evidence-based readiness only, preserve unrelated worktree changes, and avoid destructive git actions.

## When To Use
- Use before commit, push, merge, package, release, publish, skill sync, or when asked whether work can ship.
- Do not review code quality, implement fixes, clean files, install/apply links, or publish unless the user explicitly asks for that follow-through.

## Contract
- Output one decision: `ready`, `blocked`, or `ready with risks`.
- Base the decision on current evidence: worktree, diff, tests/build/lint, doctor, version/manifest/package/release state, and dry-runs.
- Missing verification is a risk or blocker, never a pass.
- Dry-run is evidence of a plan, not proof that an action happened.

## Workflow
1. Identify delivery target: commit, push, merge, package, release, publish, PR, skill sync, or readiness only.
2. Read `git status --short --branch -uall`; separate intended, unrelated, untracked, staged, and generated files.
3. Match every target file or artifact to the delivery goal. Exclude unclear files from the ready scope.
4. Run or inspect project-local validators: diff check, tests, lint/build/doctor, package contents, version/manifest, release/tag/origin/CI, and relevant dry-runs.
5. Decide in order: blockers first, then risks, then verified evidence.
6. Follow through with stage, commit, push, tag, release, publish, install, or apply only after explicit user request and only if the decision allows it.

## Active Skills Hints
- In `/Users/anfeng/AI/skills/active`, useful validators are `git diff --check -- <target-files>`, `node scripts/doctor.mjs --json`, `node scripts/validate-cross-platform.mjs`, and `node skills/meta/skill-installer/bin/skill-installer.mjs --json`.
- Outside that repo, use the local project rules and verification commands instead of hard-coding these.

## Hard Gates
- No stash, reset, checkout, clean, hiding user files, or destructive git setup.
- No cleanup here; route deletion to `cleanup-guard`.
- No dry-run treated as execution.
- No subagent-only verification.
- No "verified", "released", or "synced" claim without current command output.

## Output
交付判断 -> 阻塞项 -> 已验证证据 -> 未覆盖/风险 -> 下一步。
