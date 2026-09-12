---
name: kingdee-testing
description: "为金蝶云苍穹 Java 插件/服务设计与执行测试、诊断测试失败，或按任务范围验证运行行为；UI 测试交 kingdee-ui-testing。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.0.0"
  tags: "kingdee, cosmic, java, testing, gradle, runtime"
---

# Kingdee Testing
> Cross-platform Agent Skill: use UTF-8, host-neutral paths, and current project commands.

## Routing

- Use an existing confirmed `kingdee-metadata-analyzer` inventory/cache for tests that depend on entity fields, forms, operations, or plugin mount points; invoke the analyzer only when that evidence is missing, stale, or incomplete.
- Use `kingdee-sdk-helper` before asserting an SDK signature.
- Select test base classes, Java toolchain and assertion style from the target project's actual contract. The `SvcUnitTest*` examples are a conditional project profile, not a universal Kingdee SDK requirement; an unsourced API blacklist cannot establish deprecation.
- 生成或验证平台相关测试前，复用任务已确认的产品/运行版本并核对实际测试依赖。目标 7.0 不能用 8.0 索引、mock 或另一版本 SDK 的编译通过来证明兼容；具体补丁从项目证据确认，不默认取最新补丁，也不为让测试通过升级依赖。目标与类路径版本冲突时先查原因，只暂停依赖该冲突的实现/兼容结论，继续独立检查。
- Coordinate source fixes with `kingdee-cosmic`; keep this skill responsible for test design, execution, and evidence.
- Use `kingdee-observability` for multi-log Trace, slow SQL, N+1, thread, or GC analysis.

## Modes and contract

| Mode | Allowed work | Required contract |
| --- | --- | --- |
| `local` | Static checks, unit tests, Gradle, local harness | Project and narrow test target |
| `dev-test` | Read-only runtime verification in a named dev/test target | Target alias, URL, method, scope id, expected evidence |
| `prod-readonly` | Bounded read-only verification in an explicitly authorized production target | Approval reference, target alias, URL, time/scope limit, redaction plan |
| `approved-write` | Only the named write operation already authorized for this task | Approval reference, exact method/path, payload source, rollback, verification, request limit |

Treat an approved task contract as authorization for every action inside its exact bounds; do not ask again per step. Stop before any method, target, path, payload, record, or time window outside the contract. Use configured task credentials only in memory; never echo, persist, or copy them into reports.

Assemble the contract from the current request, project configuration, and configured connector. The user does not need to restate a URL, route, or alias that can be resolved read-only after environment, object, action, and scope authorization are clear. Credentials alone never supply those authorization fields; complete the contract before the first runtime request.

Read `references/execution-contract.md` before any runtime request or approved write.

## Workflow

1. Define the requested behavior and evidence needed to finish. For a failure, capture the command, assertion, stack and source location; for new coverage, identify the relevant source paths and expected outcomes.
2. For failures, classify the cause as compile, test logic, product defect, environment/dependency, metadata, or runtime.
3. Verify with the narrowest deterministic check that exercises the behavior; distinguish observed evidence from inference.
4. If a fix is authorized, make the smallest source or test change. Preserve a product-defect regression as `formal` only when the approved fix scope and repository test policy make it a deliverable; otherwise keep the reproducer `task-local` and report that no formal regression was delivered.
5. Run the targeted test. Add module regression when the change affects shared behavior, the targeted check leaves a material gap, or repository requirements call for it; do not hide existing failures. Once relevant checks pass, finish the authorized delivery rather than repeat or broaden tests without new evidence.
6. Perform runtime verification only when the selected mode and contract require it.
7. Report diagnosis, changed files, commands, results, unverified items, and residual risk.

## Load only required detail

- Unit tests and platform traps: `references/unit-test-generation.md`
- Testcase inventory and completeness gate: `references/testcase-completeness.md`
- Strategy and testability refactors: `references/test-strategy.md`
- Runtime execution contract: `references/execution-contract.md`
- Local harness: `references/cosmic-runtime-harness.md`
- Runtime evidence: `references/dev-runtime-verification.md`
- Build, generated-test, package, deployment, and Git handoff evidence: `references/delivery-evidence.md`
- Metadata-driven tests: `references/metadata-driven-testing.md`
- Regression rules: `references/regression-playbook.md`
- API and module gates: `references/deprecated-api-blacklist.md`, `references/cross-module-allowed.json`

## Use deterministic helpers

- Run `scripts/run_gradle_tests.py` for targeted Gradle tasks; start with `--dry-run` when resolution is uncertain.
- Run `scripts/run_dev_probe.py --dry-run` to validate a runtime contract before network access.
- Run `scripts/collect_runtime_evidence.py` only into an explicit report directory.
- Run `scripts/create_test_harness.py` only into an explicit local output directory.

## Guardrails

- Reject fake/self-comparison assertions, swallowed exceptions, wildcard Mockito imports, leaked `MockedStatic`, and tests that never reach an assertion or verification.
- Preserve constants and enums; do not replace missing platform symbols with string literals.
- Select meaningful normal, boundary, empty/null, exception, branch, state-transition and side-effect cases according to the changed behavior; report material coverage gaps. This is a coverage guide, not a requirement to create every category for each small change.
- Do not invent metadata keys, entry points, runtime success, or dependency availability.
- 报告编译/类型检查所用 SDK 来源与目标关系；业务逻辑 mock 测试、骨架和静态规则通过不能单独证明平台 API 存在或运行行为兼容。已有目标依赖足以确认本次 API 时不重复索要版本信息；缺少目标依赖时记录未验证项，不以桩类补出不存在的兼容证明。
- Gradle `test=NO-SOURCE` only proves that no test source was executed; report it separately from passed tests. An upload/restart request also is not deployment completion: wait for the target service state/count and restart timestamp required by the project, then verify the real business entry.
- Classify newly generated tests as `task-local` or `formal` before writing them. A test is `formal` only when the user explicitly requests test source, or an authorized product fix requires a durable regression and the repository test policy supports it; probes, one-off reproducers, harnesses and fixtures created only for this task are `task-local`. Task-local assets stay outside the deliverable and must be removed by exact attribution before any Git handoff; never delete or rewrite pre-existing tracked tests.
- Do not stage, commit, push, modify online metadata/configuration, or broaden a runtime contract.
- Redact credentials, sessions, tenant/account/person identifiers, internal hosts, database connections, SQL parameters, and business sample values from evidence.

## Output

Use Chinese. Lead with the verified result, then list diagnosis, changes, test matrix, commands, runtime mode/contract, evidence, existing failures, and risk.
