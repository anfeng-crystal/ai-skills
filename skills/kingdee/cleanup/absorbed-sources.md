# Absorbed Sources

This file records what Worker F absorbed into shared guardrail and platform documentation.

## Absorbed

| Source | Absorbed Into | Content Used |
|---|---|---|
| `/Users/anfeng/Downloads/kdskills/karpathy-guidelines/SKILL.md` | `shared/karpathy-guardrails/minimal-change-card.md` | Minimal change, no speculative abstraction, trace every edit to the request. |
| `/Users/anfeng/Downloads/kdskills/karpathy-guidelines/SKILL.md` | `shared/karpathy-guardrails/verification-card.md` | Define success criteria first and verify after edits. |
| `/Users/anfeng/Downloads/kdskills/ClaudeCodeKDSkills/SKILL.md` | `shared/karpathy-guardrails/stop-before-editing-card.md` | Preserved the useful caution around ambiguity and user-change protection, without importing host-specific initialization or routing. |
| `/Users/anfeng/Downloads/kdskills/apaas-testcase-router` | `shared/platform/cross-platform.md` and `shared/platform/path-policy.md` | Used only as negative evidence for literal backslash path names and host-specific archive layout. |
| `/Users/anfeng/Downloads/kdskills/kingdee-code-audit/setup-code-review-graph/SKILL.md` | `cleanup/removal-map.md` | Recorded as excluded because it is an external graph-tool setup workflow, not a shared Kingdee guardrail. |

## Not Absorbed

- Host-specific session initialization that reads a particular agent memory directory.
- Tool-specific confirmation workflows from another agent host.
- The standalone code trigger router and its copied sub-skill tree.
- External graph installation, package patching, and IDE-specific MCP configuration.
- Any downloaded file with a literal backslash in its tracked path name.

## Migration Status

No source directory was deleted. No existing active skill was removed. The migration output is limited to guardrail, platform, and cleanup documentation.
