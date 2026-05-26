# Waza Skill Optimization Absorption Plan

Date: 2026-05-26

## Goal

Absorb the useful workflow mechanics from `tw93/Waza` into the existing local skill system without replacing the current active skills or changing host distribution rules.

The optimization target is not "make local skills look like Waza". The target is to make existing local skills more reliable in the areas where Waza is stronger:

- Explicit outcome and evidence contracts.
- Hard stop conditions when diagnosis or review is not grounded.
- Safer web-reading boundaries for untrusted content and proxy use.
- Clearer plan-execution behavior after a user-approved plan.
- Screenshot-driven visual review and handoff checks.
- Darwin-style measurable regression prompts.
- Dedicated local health, plan-decision, and delivery-readiness skills for Waza capabilities that are stronger as separate triggers.

## Non-Goals

- Do not install Waza globally into Claude Code or Codex.
- Do not replace local `web-access`, `review-code`, `fix-bug`, `implement-feature`, `frontend-design`, or `design-review`.
- Do not copy Waza personality markers such as the ninja prefix.
- Do not touch existing Kingdee skill changes in the dirty worktree.
- Do not modify host symlink distribution or `skill-installer` in this pass.
- Do not absorb Waza `learn` or `write` in this pass; keep them as later optional candidates.

## Target Skills

| Skill | Absorb from Waza | Local decision |
|---|---|---|
| `fix-bug` | `hunt` root-cause sentence, repeated-fix hard stop, 3-hypothesis handoff, blast check | Keep local minimal-fix style, strengthen diagnosis gates |
| `web-access` | `read` untrusted-content rule, privacy tiers, paywall/login-page detection | Keep local curl/CDP/search tooling, strengthen safety boundaries |
| `neat-freak` | host-specific memory handling clarity | Keep doc sync role, clarify Codex memory write policy |
| `implement-feature` | `think` approval handoff and plan drift check | Keep local implementation flow, strengthen approved-plan execution |
| `review-code` | `check` review-base and worktree preflight | Keep read-only review boundary, add scope/base gates |
| `design-review` | `design` screenshot iteration and real-rendered evidence gate | Keep HTML artifact gate, add screenshot complaint mode |
| `agent-health` | `health` config drift, verifier surface, skill distribution audit | New local meta skill, read-only, no install/apply/write actions |
| `plan-decision` | `think` decision-complete recommendation, evaluation mode, handoff | New local core skill, separates planning from implementation |
| `delivery-check` | `check` release/readiness matrix, delivery gate, worktree safety | New local core skill, separates shipping readiness from code review |

## Second-Stage Decision

Waza skills split into three buckets:

| Waza skill | Decision | Reason |
|---|---|---|
| `health` | Create `agent-health` | Local system lacks a dedicated Codex/Claude/skills health audit trigger. |
| `think` | Create `plan-decision` | The user's recurring "出方案，我来审核" flow deserves a planning-only skill. |
| `check` | Create `delivery-check` | Release, push, package, and readiness gates should not dilute read-only code review. |
| `hunt` | Keep absorbed in `fix-bug` | Root-cause hard stops already landed; no separate skill needed now. |
| `read` | Keep absorbed in `web-access` | Local fetch/CDP/search tooling is stronger; only privacy boundaries matter. |
| `design` | Keep absorbed in `design-review` | Local frontend system is stronger; only screenshot iteration mode matters. |
| `learn` | Defer | Useful only if multi-source research/reporting becomes a frequent standalone workflow. |
| `write` | Defer | Useful for prose polish, but not a coding/agent-maintenance priority. |

## Multi-Agent Coordination Plan

Host mode: real delegation for read-only/explorer subtasks, local integration by main agent.

Reason: the target files are small but conceptually independent. Subagents can audit independent slices while the main agent writes the plan and performs controlled edits in the live workspace. This avoids overlapping writes in a dirty repository.

Ownership locks:

- Main agent owns all writes.
- Explorer A owns advisory output for `fix-bug` and `implement-feature`.
- Explorer B owns advisory output for `web-access` and `neat-freak`.
- Explorer C owns advisory output for `review-code` and `design-review`.
- Explorer D owns advisory output for `agent-health`.
- Explorer E owns advisory output for `plan-decision`.
- Explorer F owns advisory output for `delivery-check`.

Shared constraints:

- Do not edit files outside the target `SKILL.md` files, `config/skills-manifest.json`, and this plan document.
- Do not write process history into long-term skill prose.
- Keep edits scoped, concrete, and host-neutral unless the rule is explicitly host-specific.
- Preserve existing Chinese-first style and local output formats.
- Do not claim Darwin verification unless test prompts and results are produced.

## Implementation Steps

1. Add concise `Outcome Contract` sections where missing.
2. Add Waza-inspired hard-stop rules only where they improve local behavior.
3. Add host-specific memory boundary to `neat-freak` without disabling its doc sync function.
4. Add screenshot review mode to `design-review` rather than replacing existing HTML artifact review.
5. Add `test-prompts.json` for changed skills as temporary Darwin inputs.
6. Run Darwin-style dry-run scoring for changed skills and store temporary evidence outside permanent skill directories.
7. Run repository-level validation:
   - `node scripts/doctor.mjs --json`
   - `node scripts/validate-cross-platform.mjs`
8. Delete only this run's temporary Darwin output files after tests pass.

## Second-Stage Implementation Steps

1. Add `skills/meta/agent-health/SKILL.md` for read-only agent/config health audits.
2. Add `skills/core/plan-decision/SKILL.md` for planning, judgment, architecture, and executable handoff planning.
3. Add `skills/core/delivery-check/SKILL.md` for commit/push/package/release/readiness gates.
4. Update `config/skills-manifest.json` with the three new markdown skills.
5. Add minimal routing boundaries to `implement-feature` and `review-code` so planning and delivery checks do not collide with existing triggers.
6. Run Darwin-style temporary tests for the three new skills plus changed routing files.
7. Run repository validation and delete only this run's temporary Darwin files.

## Third-Stage AI-First Compression

The second-stage direction is correct, but the new `SKILL.md` files must stay optimized for agent runtime loading, not human review.

Compression rule:

- Keep in `SKILL.md`: trigger boundary, short outcome contract, ordered workflow, hard gates, output shape.
- Move or leave in this plan doc: Waza source analysis, historical rationale, long comparison tables, implementation narrative, and broad taxonomy.
- Descriptions must be trigger-focused. They should answer "load this skill now?" and avoid summarizing the full workflow.
- Replace repeated cross-skill tables with hard route rules where possible.
- Preserve behavior markers that affect execution: read-only boundaries, evidence requirements, drift checks, no destructive git actions, and no memory writes without authorization.

Third-stage target files:

| Skill | Runtime optimization |
|---|---|
| `agent-health` | Keep as a compact audit checklist; compress routing table and prose rationale. |
| `plan-decision` | Keep decision modes and handoff rules; remove planner-style explanation that repeats the plan document. |
| `delivery-check` | Keep readiness matrix and destructive-action gates; compress boundary table into route rules. |

Third-stage acceptance gates:

- Each target `SKILL.md` remains directly executable by an AI after one read.
- Each target description is trigger-focused and under 500 characters.
- No target skill contains Waza history, rollout history, or explanation aimed mainly at human reviewers.
- Darwin-style dry-run shows preserved or improved behavior markers after compression.

## Darwin Test Design

Each changed skill gets at least one pressure prompt focused on the absorbed mechanism:

- `fix-bug`: repeated failed fix must stop and rebuild hypothesis.
- `web-access`: public URL vs internal/logged-in URL must route privacy tiers differently.
- `neat-freak`: Codex memory update must be proposed unless user explicitly asks to write memory.
- `implement-feature`: approved plan should execute after drift check, not re-litigate.
- `review-code`: review must state base/scope before findings.
- `design-review`: screenshot complaint must identify visual defect and request/produce evidence.
- `agent-health`: health audit must stay read-only, layer findings, and route fixes to existing skills.
- `plan-decision`: planning prompt must produce a decision-complete handoff and avoid implementation.
- `delivery-check`: delivery prompt must classify worktree state, require evidence, and avoid commit/push/release unless explicitly requested.

Temporary files created by this pass:

- `docs/.tmp-waza-darwin-results.tsv`
- `docs/.tmp-waza-darwin-summary.md`
- `skills/**/.tmp-waza-test-prompts.json`

Cleanup rule: delete the above temporary files only after validation passes. Do not delete existing `test-prompts.json` or `results.tsv`.

## Acceptance Gates

- All target skills keep valid YAML frontmatter.
- No existing target skill loses its original trigger boundary.
- Added rules are specific enough to change agent behavior, not generic advice.
- `neat-freak` explicitly distinguishes Codex memory policy from project documentation sync.
- `web-access` clearly forbids third-party proxy use for sensitive or authenticated URLs.
- `fix-bug` clearly prevents repeated symptom patching.
- Darwin-style results show `new_score > old_score` for each changed skill.
- Repository validation passes or any failure is clearly unrelated to this pass.
- New skill descriptions are trigger-focused and do not summarize a hidden workflow so aggressively that the body becomes unnecessary.
- `agent-health`, `plan-decision`, and `delivery-check` keep clear boundaries with `skill-vetter`, `darwin-skill`, `implement-feature`, `review-code`, `cleanup-guard`, and `skill-installer`.
