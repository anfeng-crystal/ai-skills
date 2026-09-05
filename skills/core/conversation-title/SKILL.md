---
name: conversation-title
description: Automatically name the current root conversation once its main goal is clear, or rename it when the user asks. Use a native title API when available and otherwise govern the host's automatic title generation without simulating unsupported mutation.
---

# Conversation Title

> Cross-platform Agent Skill: shared naming semantics; native host adapters only, with no simulated internal mutation.

Name a new root conversation without waiting for an explicit user request once its first substantive goal is clear. Keep this metadata action silent and subordinate to the user's actual task.

## Title contract

Use exactly:

```text
MMDD | 类型 | 主题
```

- `MMDD`: derive from the conversation `createdAt` in `Asia/Shanghai`. For a confirmed new conversation, the first lifecycle event time may stand in for `createdAt`. If neither is reliable, do not rename.
- `类型`: choose exactly one of `功能`, `设计`, `修复`, `优化`, `发布`, `探索`, `文档`, `研究`.
- `主题`: summarize the primary deliverable as a compact object-action or object-problem phrase. Prefer 4-14 Chinese characters or 2-8 English words; preserve necessary product names and abbreviations.

Classify by the intended final deliverable, not an intermediate activity. Research performed to implement a feature is `功能`; log analysis performed to fix a defect is `修复`; comparison without implementation is `研究`; an experiment or POC is `探索`.

Do not repeat the type in the topic. Avoid empty phrases such as `帮我处理`, `分析一下`, `一个问题`, `项目任务`, `相关内容`, `功能需求`, or `问题讨论`. Do not use a sentence, emoji, quote, newline, or final punctuation.

## Passive lifecycle

- Act only on the current root conversation after the first substantive user request makes the main goal clear.
- Skip greetings, acknowledgements, attachment-only turns, subagents, resumed conversations, and conversations already named by the user.
- Name once. Do not rename for added parameters, screenshots, logs, or implementation details.
- Rename later only when the user explicitly asks. A changed goal alone does not authorize another automatic rename.
- If several tasks exist, use the main deliverable. If no main deliverable can be identified, leave the title unchanged.

## Capability boundary

The naming contract always applies, including on hosts without an agent-callable title API. Use a documented host title API or tool when available; otherwise apply the contract whenever the host automatically generates or requests a title, without attempting unsupported direct mutation. Change only the current conversation title. Never scan or batch-rename history, edit project names or files, parse unstable transcripts, or write a host's internal database/cache to simulate naming. A failed direct write must not interrupt the user task.

For host-specific activation and degradation behavior, read [references/host-support.md](references/host-support.md).
