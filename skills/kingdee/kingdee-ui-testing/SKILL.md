---
name: kingdee-ui-testing
description: "Orchestrate requirement-driven Kingdee Cosmic UI test generation, safe smoke checks, explicitly approved CRUD, production-safe smoke, and approved production E2E verification over the existing automation/playwright executor. Use for form/list rendering, F7 and subtable interaction, validation rules, requirement coverage, normalized JSON/CSV cases, cleanup/rollback, and step-level evidence reports."
---

# Kingdee UI Testing
> Cross-platform Agent Skill: use UTF-8, host-neutral paths, and the existing Playwright execution skill.

## 触发与路由

Act as the Kingdee UI domain orchestrator. Load and use `automation/playwright` for browser control; do not copy its CLI, selectors, browser binaries, or authentication state. If its supported runtime is unavailable, report the execution as blocked instead of installing dependencies.

## 模式与契约

| Mode | Allowed behavior |
| --- | --- |
| `generate` | Parse requirements and normalize cases; no browser action |
| `safe-smoke` | Dev/test navigation, rendering, list/detail, read-only F7/subtable inspection, assertions, screenshots |
| `approved-crud` | Exact dev/test create/update/delete actions listed in an approved contract |
| `prod-safe-smoke` | Explicitly approved production navigation and read-only assertions; no data entry or business operation |
| `approved-prod-e2e` | Exact production E2E actions already authorized with test-data scope, rollback, cleanup, and limits |

Validate the task contract before browser execution. One approved contract authorizes all listed steps; do not repeat confirmation per click or case. Stop before any target, case, action, selector intent, data record, operation, or cleanup outside the contract.

Read `references/execution-contract.md` for action gates and `references/case-schema.md` when generating or importing cases.

## 工作流

1. Map confirmed requirements to case IDs, expected fields, rules, operations, and evidence; do not invent form keys or F7 semantics.
2. Normalize JSON/CSV with `scripts/normalize_cases.py`; keep source order and reject credentials or bundled browser state.
3. Validate the execution contract with `scripts/validate_execution_contract.py`.
4. Capture every contract-level before assertion before the first write.
5. Before each page-specific assertion, capture the actual route, `formId`, `pageType` (list/detail/edit/dialog), and relevant `pageElement`; a detail page cannot satisfy a list-layout/list-plugin case, even if both expose the same entity fields.
6. Execute normalized steps through `automation/playwright`. Within the contract, continue without per-step confirmation; outside it, stop and request a revised contract.
7. For approved writes, require the test-data prefix on every created/updated record, record identifiers immediately, and verify after assertions.
8. Run contract cleanup and rollback. If either fails, stop further writes and report exact residual records without broad deletion.
9. Build step evidence with `scripts/build_evidence_report.py`; keep missing, blocked, and not-run distinct from passed.

## 门禁与失败

- Resolve F7, subtable, operation button, save, submit, audit, and attachment behavior from the current page/metadata; do not reuse tenant-specific snapshots.
- `safe-smoke` and `prod-safe-smoke` forbid input, select-value changes, upload, save, create, update, delete, submit, audit, unaudit, enable/disable, workflow action, and cleanup.
- Treat a click as read-only only when its declared effect is navigation, tab/dialog open/close, pagination, or inspection and no business state changes.
- Assert before and after state by stable business identifiers; do not rely only on toast text.
- Do not infer page identity from a shared physical table, entity name, window title, or similar-looking fields. Evidence from the wrong `formId`/`pageType` is `blocked_wrong_page`, not passed.
- Never force-overwrite user testcases. Write only the requested output path.

## Deterministic helpers

- `scripts/normalize_cases.py`: normalize UTF-8 JSON or CSV cases.
- `scripts/validate_execution_contract.py`: enforce mode, environment, action, prefix, rollback, cleanup, and credential-free contracts.
- `scripts/build_evidence_report.py`: join normalized steps with redacted results and expose coverage gaps.

The scripts use `pathlib`, accept paths with spaces and Windows/POSIX separators, require no non-standard package, do not install anything, and never delete inputs.

## 输出

Use Chinese. Lead with mode and pass/fail/blocked result, then give requirement coverage, executed case/step counts, before/after assertions, created identifiers, cleanup/rollback result, evidence paths, missing steps, and residual risk.
