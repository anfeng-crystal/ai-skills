---
name: kingdee-ui-testing
description: "生成或执行金蝶云苍穹表单/列表、F7、分录和业务操作的 UI 测试，按任务授权验证结果并清理测试数据。"
---

# Kingdee UI Testing
> Cross-platform Agent Skill: use UTF-8, host-neutral paths, and an existing supported browser executor when executing UI cases.

## 触发与路由

Act as the Kingdee UI domain orchestrator. For browser execution, reuse the currently available supported browser skill/tool, such as `playwright`; keep this skill responsible for the case, page identity, authorization and evidence contracts. Do not copy browser executors, binaries or authentication state. If no equivalent supported runtime is available, report browser execution as blocked; case generation and contract preparation can continue. `generate` mode does not load or require a browser runtime.

## 模式与契约

| Mode | Allowed behavior |
| --- | --- |
| `generate` | Parse requirements and normalize cases; no browser action |
| `safe-smoke` | Dev/test navigation, rendering, list/detail, read-only F7/subtable inspection, assertions, screenshots |
| `approved-crud` | Exact dev/test create/update/delete actions listed in an approved contract |
| `prod-safe-smoke` | Explicitly approved production navigation and read-only assertions; no data entry or business operation |
| `approved-prod-e2e` | Exact production E2E actions already authorized with test-data scope, rollback, cleanup, and limits |

Validate the task contract before browser execution. One approved contract authorizes all listed steps; do not repeat confirmation per click or case. Stop before any target, case, action, selector intent, data record, operation, or cleanup outside the contract.

Read `references/execution-contract.md` before browser execution and `references/case-schema.md` when generating or importing cases.

## 工作流

1. Map confirmed requirements to case IDs, expected fields, rules, operations, and evidence; do not invent form keys or F7 semantics.
2. Normalize JSON/CSV with `scripts/normalize_cases.py`; keep source order and reject credentials or bundled browser state.
3. For browser modes, validate the execution contract with `scripts/validate_execution_contract.py`; `generate` completes with normalized cases and requirement coverage.
4. Capture every contract-level before assertion before the first write.
5. For each page-specific assertion, declare the confirmed expected `step.page` and capture actual route, `formId`, `pageType` (list/detail/edit/dialog), and relevant `pageElement` in `result.page`, following [case-schema](references/case-schema.md). A detail page cannot satisfy a list-layout/list-plugin case. Ordinary navigation and non-page steps do not require `page`; never invent an ID to fill the contract.
6. Execute normalized steps through the selected browser executor. Within the contract, continue without per-step confirmation; outside it, stop and request a revised contract.
7. For approved writes, require the test-data prefix on every created/updated record, record identifiers immediately, and verify after assertions.
8. Run contract cleanup and rollback. If either fails, stop further writes and report exact residual records without broad deletion.
9. Build step evidence with `scripts/build_evidence_report.py`; declared page assertions with missing or mismatched proof cannot remain passed. Preserve `rawStatus` and `pageCheck`; report `pagePassedCount` separately from all passed steps. Matching supplied identity is not proof of actual UI behavior.

## 门禁与失败

- Resolve F7, subtable, operation button, save, submit, audit, and attachment behavior from the current page/metadata; do not reuse tenant-specific snapshots.
- `safe-smoke` and `prod-safe-smoke` forbid input, select-value changes, upload, save, create, update, delete, submit, audit, unaudit, enable/disable, workflow action, and cleanup.
- Treat a click as read-only only when its declared effect is navigation, tab/dialog open/close, pagination, or inspection and no business state changes.
- Assert before and after state by stable business identifiers; do not rely only on toast text.
- 动态表单回填测试从真实父页打开：按变更影响验证缺必录不关闭且不新增/改行、补齐后回填、再次编辑回显、取消不改原行。固定值/隐藏字段、布尔 `false`、基础资料和金额分别按字段合同断言；只测独立预览或只测成功路径不能覆盖回填与必录门禁。
- 布局修改检查空/短内容与必要的换行内容，覆盖整页相邻字段、上下段及按钮；只证明 DOM 存在或查看局部截图不能证明布局协调。隐藏元素可能仍在 DOM，应断言不可见而非不存在。
- 用户同时操作或已在当前弹窗录入时，先识别最新可见状态，保留其内容；改用已授权独立测试页或停止冲突动作，不覆盖用户输入。未执行场景明确记录，不将其写成通过。
- Do not infer page identity from a shared physical table, entity name, window title, or similar-looking fields. A reported pass on the wrong page becomes `status=blocked` with `blockReason=blocked_wrong_page`.
- Never force-overwrite user testcases. Write only the requested output path.

## Deterministic helpers

- `scripts/normalize_cases.py`: normalize UTF-8 JSON or CSV cases.
- `scripts/validate_execution_contract.py`: enforce mode, environment, action, prefix, rollback, cleanup, and credential-free contracts.
- `scripts/build_evidence_report.py`: join normalized steps with redacted results and expose coverage gaps.

The scripts use `pathlib`, accept paths with spaces and Windows/POSIX separators, require no non-standard package, do not install anything, and never delete inputs.

## 输出

Use Chinese. Lead with mode and pass/fail/blocked result, then give requirement coverage, executed case/step counts, before/after assertions, created identifiers, cleanup/rollback result, evidence paths, missing steps, and residual risk.
