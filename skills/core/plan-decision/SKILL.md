---
name: plan-decision
description: "Use when users ask 出方案、给方案、分析一下、怎么设计、有没有必要、值不值得、我来审核, or ask for a plan, architecture choice, decision, or execution handoff before implementation."
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [planning, decision, design, architecture, handoff]
---

# Plan Decision

> Cross-platform Agent Skill: ground recommendations in current evidence, avoid host-specific assumptions, and do not write files during planning.

## When To Use
- Use for方案、架构、取舍、价值判断、执行计划、handoff, or "我来审核" requests.
- Route bugs and failing tests to `fix-bug`, code review to `review-code`, direct implementation to `implement-feature`, and delivery readiness to `delivery-check`.

## Contract
- Goal: output one reviewable, executable recommendation or verdict.
- Evidence: current repo constraints, AGENTS/CLAUDE/docs, similar implementations, config, official docs when relevant, and live facts for anything unstable.
- Done: goal, non-goals, constraints, recommendation, rejected option, validation, risk, rollback, and handoff are clear.
- No write: planning does not edit files, create directories, or claim implementation is complete.

## Workflow
1. Choose mode: lightweight fix direction, evaluation, or full plan.
2. Confirm cwd and read the nearest rules, docs, config, prior plan, and relevant existing implementation.
3. Surface hard conflicts. Ask only if the conflict cannot be resolved from local evidence.
4. Give one recommendation. Add at most one alternative when the tradeoff is genuinely close.
5. Attack the recommendation for dependency failure, scale, rollback cost, permissions, data migration, and external state.
6. Produce handoff: files/modules, behavior change, validation commands, acceptance criteria, rollback, and next skill.
7. If the user later says to execute an approved plan, route to `implement-feature`; it should only do drift check before editing.

## Hard Rules
- Evaluation questions start with `Keep`, `Kill`, or `Pivot`.
- No `TBD`, `TODO`, `后续补齐`, or `类似上一步` in an approved plan.
- Every phase must be independently verifiable; otherwise write a single-phase plan.
- If an approved plan drifted from current facts, name the drift and narrow or stop.
- Do not store project-private paths, release commands, or local context as generic skill rules.
- Preserve user worktree changes and do not run destructive git commands.

## Output
结论 -> 依据 -> 推荐方案 -> 被拒绝方案 -> 验证/验收 -> 风险/脆弱假设 -> handoff。
