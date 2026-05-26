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
