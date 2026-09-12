# Cosmic Runtime Harness

## Purpose

The harness is a local scaffold for testing Kingdee Cosmic Java business logic without mutating online metadata or production configuration.

## Safe Boundaries

- The harness may create files under a user-specified output directory.
- It must not edit business repository build files unless the user explicitly asks.
- It must not write online metadata, production config, or database data.
- It may contain fake context, mock collaborators, and example test classes.

## Recommended Use

```bash
python3 <skill-root>/scripts/create_test_harness.py --output /tmp/kingdee-test-harness
```

Then copy only the relevant template pieces into the business repository after review.

## Harness Contents

- `FakeRequestContext.java`: tiny placeholder for user/org/tenant context values.
- `CosmicTestHarness.java`: deterministic helpers for arranging context and asserting no accidental production endpoint is used.
- `ExampleCosmicHarnessTest.java`: JUnit 5 smoke example.

These templates are intentionally platform-light; real Kingdee SDK objects should be mocked or wrapped by project-specific adapters.

骨架/mock 测试只验证本地安排的业务行为，不证明某个苍穹 API 在目标版本可用。涉及平台签名时先核对与任务目标一致的实际 SDK/声明；例如目标 7.0 不能用 8.0 索引或手写桩补出的类代替兼容证据。继续允许生成标明用途的本地骨架，不为证明兼容自动下载 SDK 或连接业务环境。
