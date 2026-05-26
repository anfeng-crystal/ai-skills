---
name: kingdee-testing
description: "Kingdee Cosmic testing: unit tests, Gradle test runs, local Java harness generation, dev runtime probes, and runtime evidence collection for Kingdee Cosmic Java plugins and services."
metadata:
  author: anfeng
  version: "0.1.0"
  license: MIT
  tags: [kingdee, cosmic, java, testing, gradle, runtime]
---

# Kingdee Testing
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## Scope
- Use this skill for Kingdee Cosmic Java unit tests, testability refactoring checks, Gradle test execution, dev runtime verification, and runtime evidence collection.
- For entity metadata, field definitions, form bindings, or production/dev metadata facts, use `kingdee-metadata-analyzer` first.
- For SDK signatures, API ownership, or Javadoc facts, use `kingdee-sdk-helper` first.
- For implementation changes to plugins or services, coordinate with `kingdee-cosmic`; this skill owns the testing and evidence workflow.

## Guardrails
- Do not automatically commit, stage, push, or create pull requests.
- Do not automatically modify production configuration, online metadata, form configuration, business rules, or database data.
- If a test or probe requires production or metadata changes, output the proposed change, evidence, risk, and verification plan for user approval.
- Prefer read-only probes and local test harnesses. Network probes must target explicit dev/test URLs or user-approved targets.
- Keep changes minimal and limited to requested test files, harness files, or reports.

## Workflow
1. Classify the request: unit test generation, Gradle verification, runtime probe, evidence collection, regression guard, or testability refactor check.
2. Load only the needed reference:
   - Test strategy: `references/test-strategy.md`
   - Runtime harness: `references/cosmic-runtime-harness.md`
   - Dev probe: `references/dev-runtime-verification.md`
   - Metadata-driven testing: `references/metadata-driven-testing.md`
   - Regression cases: `references/regression-playbook.md`
   - Deprecated API rules: `references/deprecated-api-blacklist.md`
   - Cross-module whitelist: `references/cross-module-allowed.json`
3. Use bundled scripts when possible:
   - `scripts/create_test_harness.py` creates a local Java test harness from `assets/java-test-harness`.
   - `scripts/run_gradle_tests.py` prechecks and runs Gradle test tasks.
   - `scripts/run_dev_probe.py` performs explicit read-only HTTP probes against dev/test URLs.
   - `scripts/collect_runtime_evidence.py` collects read-only runtime evidence into a report directory.
4. Verify with the narrowest runnable command first, then broaden only when needed.
5. Report changed files, commands run, output summary, unverified items, and risks.

## Quality Gates
- Reject fake assertions such as `assertTrue(true)` or `assertEquals(x, x)`.
- Avoid wildcard static Mockito imports; import only the methods used.
- Close `MockedStatic` resources with try-with-resources or teardown.
- Do not replace constants or enums with operation-code string literals.
- Check deprecated APIs before generating or approving test support code.
- Flag cross-product-line utility imports unless they match `cross-module-allowed.json`.
- For field, form, and plugin-entry tests, consume `kingdee-metadata-analyzer` metadata contract first; do not invent field keys or mobile/PC entry points by source-path guesswork.

## Output
Use Chinese by default. Start with conclusion, then provide evidence, changes, verification, risks, and pending decisions.
