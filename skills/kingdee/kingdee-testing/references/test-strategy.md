# Test Strategy

## Intent Routing

| User intent | Mode | Verification |
|---|---|---|
| Write tests for helper or pure logic | Pure unit test | Targeted Gradle test task |
| Write tests for service, manager, or plugin logic | Mockito unit test | Static gate, then Gradle test |
| Verify a plugin against dev runtime | Runtime probe | Explicit read-only HTTP probe and evidence collection |
| Check existing tests | Test rot scan | Identify fake assertions, wildcard imports, and resource leaks |
| Guard a refactor | Regression guard | Replay `regression-playbook.md` rules |

## Unit Test Rules

- Prefer pure logic tests when platform I/O can be separated from business logic.
- Use Mockito only for external platform services, request context, static helpers, or collaborators.
- Do not generate tests for getters, setters, `toString`, `equals`, `hashCode`, `main`, Spring configuration, pure delegation methods, or methods with no meaningful branch/output.
- Assertions must inspect real output, side effects, thrown exceptions, or collaborator interactions.
- Static mocks must be closed by try-with-resources or deterministic teardown.
- Avoid `import static org.mockito.Mockito.*` and `import static org.mockito.ArgumentMatchers.*`; import only used methods.

## Testability Refactor Checks

- If a new BizLogic class is introduced, verify the original Flow method was replaced by a thin shell in the same diff.
- Keep `ResManager.loadKDString` in Flow/plugin layers. BizLogic should return codes or result objects, not localized platform messages.
- Preserve constants and enums. Do not replace `OperationConst.AUDIT` or similar constants with `"audit"` literals.
- Before choosing a common utility from another product line, check `cross-module-allowed.json`; otherwise recommend an equivalent utility from the same product line.
- Before using platform helpers or internal utilities, check `deprecated-api-blacklist.md`.

## Gradle Verification

1. Locate `gradlew` in the project root or an ancestor directory.
2. Prefer module-level test tasks when the module is known.
3. Run targeted tests before full test suites.
4. If dependencies or biz jars are unavailable, report the precheck failure and suggest IDE or environment verification instead of fabricating success.
