# Removal Map

This map records sources that are intentionally not introduced into the shared Kingdee skill workflow. It is a cleanup manifest only; it does not authorize deletion.

## Not Introduced

| Source | Decision | Reason |
|---|---|---|
| `<download-root>/kdskills/ClaudeCodeKDSkills` | Do not migrate as a standalone skill | It is tightly coupled to one host workflow, session initialization, user memory layout, and confirmation tooling. Shared behavior was reduced to guardrail cards instead. |
| `<download-root>/kdskills/ClaudeCodeKDSkills/skills/kdcodetrigger` | Do not migrate as a standalone router | It duplicates Kingdee development routing that is now owned by specialized shared skills and would create trigger conflicts. |
| `<download-root>/kdskills/karpathy-guidelines` | Do not migrate as a standalone skill | The useful behavioral constraints are absorbed into small shared cards under `shared/karpathy-guardrails`. |
| `<download-root>/kdskills/kingdee-code-audit/setup-code-review-graph` | Do not migrate | It installs and patches an external graph tool and configures a specific IDE integration. This is outside the current shared Kingdee skill scope. |
| `<download-root>/kdskills/apaas-testcase-router/.qoder\\...` | Do not migrate | The archive contains literal backslash path names and host-specific layout. Importing it would violate the path policy. |

## Boundary

- Do not delete the source directories from `<download-root>/kdskills`.
- Do not delete or rename existing shared skills from this cleanup pass.
- Do not add hidden host directories, host caches, or global agent configuration files to shared logic.

## Follow-Up Owner

Integrator may use this file to decide later cleanup, but only after reviewing all worker outputs and confirming no shared skill still depends on the skipped source.
