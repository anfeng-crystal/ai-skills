# Active Skill Value Audit — 2026-08-08

## Conclusion

- Scope: all 38 skills remaining after `multi-agent-collab` was removed.
- Result: remove 14 low-increment skills; retain 24 skills with exclusive executable, platform, or evidence paths.
- Runtime source and `config/skills-manifest.json` both contain 24 skills after cleanup.

## Method

Each skill was tested with three Chinese prompts: a typical task, a boundary case, and a counterexample. The same prompts were run in clean temporary Codex homes with and without the active skill set:

- Default model: 114 prompt pairs, producing 228 compared answers.
- Light model deletion veto: 42 prompt pairs for the 14 candidates, producing 84 compared answers.
- Scoring dimensions: routing, unique technical action/tool/API, safety, evidence, and truthful limits.
- Delete rule: average observable delta below 0.75, no reduction in critical mistakes, and no exclusive executable or knowledge path.
- A first contaminated baseline that could still see active-skill metadata was discarded and was not used for deletion decisions.

Batch token observations confirmed that loaded instructions are not free. For the automation/core batch, reported input tokens were 13,971 without skills and 116,479 with skills. For the meta batch they were 28,893 and 77,177. These are batch observations, not per-call guarantees.

## Removed

| Skill | Measured reason |
|---|---|
| `data-analyst` | Default analysis was already complete; the skill added arbitrary hard thresholds and could make the answer worse. |
| `delivery-check` | Added readiness labels, but no correctness, evidence, or safety gain. |
| `design-review` | Default output already required rendered evidence and mobile checks; no exclusive tool path. |
| `explain-code` | Outputs were effectively identical. |
| `fix-bug` | Default model already followed reproduce, root-cause, minimal-fix, regression workflow. |
| `frontend-design-principles` | Added naming structure, but not a material design-quality gain; assets duplicated the implementation skill. |
| `frontend-design` | Default model already covered component reuse, states, responsive behavior, and visual verification. |
| `implement-feature` | No material gain; skill sometimes re-opened confirmation after the task was already authorized. |
| `plan-decision` | Added `Keep/Kill/Pivot` labels without improving the decision. |
| `review-code` | Findings scope, evidence, and severity behavior were already present by default. |
| `agent-health` | Only a small wording improvement for optional hosts; no executable verifier or exclusive evidence path. |
| `cleanup-guard` | Default model already performed exact attribution and rejected unsafe wildcard deletion. |
| `neat-freak` | Default persistence and documentation boundaries were effectively identical. |
| `kingdee-isc-service` | Same diagnostic result as baseline, no scripts, and its claimed `dc_err/` and `dc_stage/` directories did not exist. |

## Retained

- Automation: `playwright`, `web-access` — deterministic browser/web wrappers and constrained retrieval paths.
- Meta: `darwin-skill`, `html-output-quality`, `multi-search`, `skill-installer`, `skill-vetter` — executable evaluators, quality gates, multi-source adapters, link state machine, and static security scanner.
- Kingdee: `iscb-script`, `kingdee-cosmic`, `kingdee-cosmic-devtools`, `kingdee-cosmic-login`, `kingdee-custom-control`, `kingdee-frontend-script`, `kingdee-kcs-ops`, `kingdee-kingscript`, `kingdee-metadata-analyzer`, `kingdee-observability`, `kingdee-openapi-client`, `kingdee-report`, `kingdee-sdk-helper`, `kingdee-security-review`, `kingdee-sql-and-data`, `kingdee-testing`, `kingdee-ui-testing` — exact platform APIs, local indexes, deterministic generators/validators, or authorization and evidence contracts that the baseline did not reproduce reliably.

Examples of decisive deltas included the ISCB `#{new_int_id()}` and mapping aggregation syntax, KCS endpoint/status contracts, KingScript event imports, Cosmic test harness lifecycle, OpenAPI token/request envelopes, and SDK signatures from the local index.

## Resolved retained issues

- `kingdee-cosmic-login` CLI no longer prints raw Cookie or CSRF values; the Python API return contract remains unchanged. CLI subprocess regression: 6/6 passed.
- `kingdee-cosmic --json` now emits one parseable JSON document on stdout; stage and Gradle messages use stderr.
- A successful Gradle stage now continues into lint and combines the final status; lint errors return non-zero.
- A non-executable `gradlew` is invoked through `sh` without changing file mode.
- The bundled 46-file asset set now has zero A-layer errors: 45 unscoped `DataSet` examples are covered by SDK-index-verified `AlgoContext` try-with-resources, including exceptional exits; the large-batch example uses bounded keyset pagination that `STYLE-015` validates semantically; and the SHA-256 invariant no longer masquerades as a business exception. Full-asset plus positive/negative rule regressions guard this result.

## Remaining non-blocking advisories

- A full scan of `kingdee-cosmic/assets/` now passes with 0 errors, 5 warnings, and 4 infos. The remaining advisory rules are `STYLE-002` ×2, `STYLE-026` ×2, `STYLE-027` ×1, and `STYLE-013` ×4; they do not fail the A-layer gate and were not mechanically rewritten without an exact SDK/i18n contract.

## Post-check environment verification

The parser dependency is now pinned by `kingdee-cosmic/requirements.txt` and was verified in a fresh Python 3.14 virtual environment:

- `tree-sitter==0.26.0`
- `tree-sitter-java==0.23.5`

The lint implementation uses `QueryCursor.matches()` on 0.26 and retains the old `Query.matches()` path for 0.24 compatibility. Both versions executed the four core post-check subprocess regressions; the fresh 0.26 environment also executed the full-asset, `AlgoContext`, and keyset-pagination regressions, for 7/7 total. `pip check` passed.

Real subprocess verification using the documented `python3 cosmic-post-check.py ...` entrypoint produced:

- valid Java sample: exit 0, no findings;
- invalid operation plugin: exit 1 with `SCENE-001` and AST-backed `SCENE-011`;
- missing listener registration: exit 0 with AST-backed `SCENE-005` warning;
- bundled `FormPluginTemplate.java`: exit 0 in normal mode;
- JSON mode: stdout parses as a single JSON document;
- Gradle-success/lint-failure: exit 1 after both stages run;
- non-executable wrapper: mode remains unchanged;
- bundled 46-file asset scan: exit 0 with zero errors;
- `python3 -m pip check`: no broken requirements.
