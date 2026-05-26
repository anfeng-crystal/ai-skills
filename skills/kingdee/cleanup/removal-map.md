# Removal Map

This map records sources that are intentionally not introduced into the active Kingdee skill workflow. It is a cleanup manifest only; it does not authorize deletion.

## Not Introduced

| Source | Decision | Reason |
|---|---|---|
| `/Users/anfeng/Downloads/kdskills/ClaudeCodeKDSkills` | Do not migrate as a standalone skill | It is tightly coupled to one host workflow, session initialization, user memory layout, and confirmation tooling. Shared behavior was reduced to guardrail cards instead. |
| `/Users/anfeng/Downloads/kdskills/ClaudeCodeKDSkills/skills/kdcodetrigger` | Do not migrate as a standalone router | It duplicates Kingdee development routing that is now owned by specialized active skills and would create trigger conflicts. |
| `/Users/anfeng/Downloads/kdskills/karpathy-guidelines` | Do not migrate as a standalone skill | The useful behavioral constraints are absorbed into small shared cards under `shared/karpathy-guardrails`. |
| `/Users/anfeng/Downloads/kdskills/kingdee-code-audit/setup-code-review-graph` | Do not migrate | It installs and patches an external graph tool and configures a specific IDE integration. This is outside the current active Kingdee skill scope. |
| `/Users/anfeng/Downloads/kdskills/apaas-testcase-router/.qoder\\...` | Do not migrate | The archive contains literal backslash path names and host-specific layout. Importing it would violate the path policy. |

## Boundary

- Do not delete the source directories from `/Users/anfeng/Downloads/kdskills`.
- Do not delete or rename existing active skills from this cleanup pass.
- Do not add hidden host directories, host caches, or global agent configuration files to active shared logic.

## Follow-Up Owner

Integrator may use this file to decide later cleanup, but only after reviewing all worker outputs and confirming no active skill still depends on the skipped source.
