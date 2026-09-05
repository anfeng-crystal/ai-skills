# Host support

The skill owns naming semantics. Lifecycle adapters only trigger the policy or apply a validated title; they must not redefine the contract.

| Host | Passive trigger | Supported mutation | Behavior |
|---|---|---|---|
| Codex | Global rule after the first substantive request | Native current-task title tool when exposed | Desktop applies the title once. Without a direct tool, the same global rule still governs native automatic title generation. |
| Claude Code | `SessionStart` records new-session eligibility; `UserPromptSubmit` handles the first substantive prompt | `hookSpecificOutput.sessionTitle` | A dependency-free conservative extractor applies the shared format. Ambiguous input is left unchanged. |
| Pi | `session_start` plus `before_agent_start` extension events | `pi.setSessionName()` | The current model generates a title and calls the extension tool once. |
| Antigravity | Global rule after the first substantive request | No documented direct conversation-title output | The rule governs native automatic title generation; never edit brain artifacts or transcripts to force the result. |
| WorkBuddy | Global rule after the first substantive request | Native current-task title tool when exposed | The rule governs built-in title generation even without a direct tool; never edit WorkBuddy databases or session files. |
| OpenCode | Optional future plugin | Session update API | Do not install unless the host is present and requested. |

Adapters must ignore subagents, resumed sessions, existing custom titles, and non-substantive first turns. A missing or failed direct mutation path does not disable the naming contract and must not block or delay the user task.
