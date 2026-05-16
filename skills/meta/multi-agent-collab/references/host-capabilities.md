# Host Capabilities

This skill is host-neutral. Use the current tool's actual capabilities, and never claim a real subagent was started unless the host supports it and the action was performed.

## Capability Fields

```text
Host: {codex | claude-code | junie | agents-universal | unknown}
Real subagents: yes/no/unknown
Parallel execution: yes/no/unknown
Model selection: yes/no/unknown
Reasoning control: yes/no/unknown
Write isolation: yes/no/unknown
Fallback: {real delegation | serial handoff simulation | plan only}
```

## Default Host Guidance

| Host | Guidance |
|------|----------|
| Codex | Use available subagent/delegation tools only when present and allowed. Otherwise use Coordination Plan or serial handoff simulation. |
| Claude Code | Use the host's supported agent/task mechanisms if available. Keep prompts host-neutral and pass `model_profile` as intent when exact model routing is unavailable. |
| Junie | Treat host capabilities as unknown unless the session exposes explicit delegation controls. Prefer plan or serial handoff fallback. |
| Agents/Universal CLI | Treat as a common entrypoint for many tools. Verify actual capabilities before delegation; do not assume parallel agents, model selection, or write isolation. |
| Unknown | Use plan-only or serial handoff simulation. |

## Fallback Modes

- `real delegation`: actual subagents are started by the host.
- `serial handoff simulation`: main agent performs roles in sequence using the same handoff contracts, clearly saying this is not parallel execution.
- `plan only`: output a Coordination Plan for a capable host or later execution.

## Safety Rules

- Host-specific tool names belong in the executing agent's local actions, not in portable skill instructions.
- Host-specific model names belong in adapters or local execution notes, not in the generic SKILL.md.
- If a host cannot isolate writes, avoid parallel Workers and prefer Single Worker or staged review.
