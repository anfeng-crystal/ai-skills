# Test Strategy

## Intent Routing

| User intent | Mode | Verification |
|---|---|---|
| Write tests for helper or pure logic | Pure unit test | Targeted Gradle test task |
| Write tests for service, manager, or plugin logic | Mockito unit test | Static gate, then Gradle test |
| Verify a plugin against dev runtime | Runtime probe | Explicit read-only HTTP probe and evidence collection |
| Check existing tests | Test rot scan | Identify fake assertions, wildcard imports, and resource leaks |
| Guard a refactor | Regression guard | Replay `regression-playbook.md` rules |
| Diagnose a failing test or runtime check | Diagnose/fix/verify loop | Preserve failure evidence, apply an authorized fix, rerun the affected check; broaden when impact or evidence requires it |

## Unit Test Rules

- Prefer pure logic tests when platform I/O can be separated from business logic.
- Use Mockito only for external platform services, request context, static helpers, or collaborators.
- Do not generate tests for getters, setters, `toString`, `equals`, `hashCode`, `main`, Spring configuration, pure delegation methods, or methods with no meaningful branch/output.
- Assertions must inspect real output, side effects, thrown exceptions, or collaborator interactions.
- Static mocks must be closed by try-with-resources or deterministic teardown.
- Avoid `import static org.mockito.Mockito.*` and `import static org.mockito.ArgumentMatchers.*`; import only used methods.
- Read `testcase-completeness.md` before generation; trace every required scenario to a source branch and meaningful assertion.

## Testability Refactor Checks

- If a new BizLogic class is introduced, verify the original Flow method was replaced by a thin shell in the same diff.
- Keep `ResManager.loadKDString` in Flow/plugin layers. BizLogic should return codes or result objects, not localized platform messages.
- Preserve constants and enums. Do not replace `OperationConst.AUDIT` or similar constants with `"audit"` literals.
- Before choosing a common utility from another product line, check `cross-module-allowed.json`; otherwise recommend an equivalent utility from the same product line.
- Before using platform helpers or internal utilities, follow the evidence checks in `deprecated-api-blacklist.md`; a legacy candidate entry alone cannot label an API deprecated or trigger automatic replacement.
- 新增或改动平台调用/测试基类前，确认该 API 在目标实际依赖或适用目标的官方证据中存在；新版本参考卡命中只作候选。mock 的定义不构成目标版本证据，不升级 SDK 来迎合生成的测试。

## Gradle Verification

1. Locate `gradlew` in the project root or an ancestor directory; verify that the resolved SDK/test classpath matches the task's target product/version. A successful build against another version does not establish target compatibility.
2. Prefer module-level test tasks when the module is known.
3. Run targeted tests. Use a full suite only when shared impact, remaining uncertainty, or project requirements warrant it; passing relevant checks completes verification for the current scope.
4. If dependencies or biz jars are unavailable, report the precheck failure and suggest IDE or environment verification instead of fabricating success.

## 批量补测与变更范围

用户要求按 diff 或一组类补测时，先沿用指定的比较基线、模块和文件范围；未指定基线则从当前任务的改动记录确定，无法归因的工作区改动单独列出，不纳入本轮或覆盖他人文件。

把本轮变更映射为 `业务行为 → 变更分支/受影响调用方 → 已有用例与断言 → 缺口`。已有 Test 类不代表覆盖新增行为，也不能因类名存在就跳过；优先补充现有有意义的用例。根据真实共享影响决定是否扩大回归，范围外覆盖率偏低本身不授权批量改写。

最终报告新增/补充用例、复用的已有证据、未覆盖行为和范围排除理由。测试归属仍按入口的 `task-local` / `formal` 合同处理，不因批量生成自动提交或保留临时测试。
