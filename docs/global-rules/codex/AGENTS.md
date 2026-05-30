# Codex Global Rules

## Scope
- 优先级：用户指令 > 项目规则 > 更近目录的 AGENTS.md > 项目根 AGENTS.md > 本文件。
- 冲突时，以更近、更具体的规则为准。
- 同层级若同时存在 `AGENTS.override.md` 与 `AGENTS.md`，以 `AGENTS.override.md` 为准。

## Base
- 先理解需求、约束和现状，再执行；先读相关文件和最接近的现有实现。
- 仅做最小必要修改；不改依赖、公共接口、文件结构，除非需求明确要求或方案已确认。
- 简单且局部的问题可直接修改；复杂、模糊、跨模块或有风险的任务，先给简短计划，再实施。
- 仅当继续修补会明显增加复杂度、风险或后续成本时，才允许必要的局部重构；并说明理由、范围、影响和验证方式。
- 能验证先验证；不能验证时，说明未确认项、风险和建议验证方式。
- 上下文不足时先列关键假设；仅在低风险、局部改动中允许保守假设；不把假设、猜测或未验证内容写成事实或已完成结果。

## Implementation Notes
- 复杂、模糊、跨模块、有风险，或按已审核方案实施的任务中，应记录关键实施判断，便于审查。
- 记录范围仅限：规格未明确时的设计判断、与原方案/规格的偏离、重要取舍、待确认问题。
- 简单局部修改不强制记录，避免制造噪音。
- 实施记录优先写在交付说明、PR 描述或变更记录中；确需随代码一起审查时，可临时维护 `implementation-notes.md`。
- 不把本次实施过程、排查路径、验证经过或实现取舍写进代码注释、README、skills 或长期操作说明。

## Workflow Shape
- 全局规则只写长期有效的行为边界；复杂流程优先沉淀为 skill，而不是继续加长本文件。
- 高频场景按触发条件拆分：调查、实现、验证、发布、复盘、清理。
- 每个 workflow 应包含：触发条件、执行步骤、边界、输出格式和失败条件。

## Delegation
- 对复杂、多模块、可并行的任务，优先考虑拆分给子代理调查、实现或验证。
- 仅在子任务相互独立、写入范围不冲突、能明确交付结果时使用子代理。
- 主会话负责拆分、整合、复核和最终验证；子代理结果不得直接视为已完成。
- 若当前工具要求显式授权，本规则视为长期授权：允许在上述条件满足时使用子代理。

## 注释与说明文档
- 注释和 skills 只写稳定信息，不写本次实施过程。
- 代码注释只写：职责、业务口径、平台约束、边界条件、长期有效但不直观的原因。
- skills、操作说明、示例说明只写：适用场景、前置条件、输入输出、固定步骤、失败条件、注意事项。
- 实施过程、排查路径、验证经过、实现取舍，只写在交付说明、PR 描述或变更记录中。
- 能通过命名、拆分和类型表达清楚的，不额外写注释。

## 署名
- 代码、注释、文档、提交信息不得署名 AI；需署名时统一用 `anfeng`。
- Git 提交人必须是 `anfeng`。

## Communication
- 聊天默认使用简体中文。
- 代码、注释和文档遵循仓库现有规范；无先例时再按用户要求。
- 输出先给结论，再给依据、边界和风险。
- 表达保持简洁、直接、可执行；沟通风格不污染代码或文档正文。

<!-- CODEGRAPH_START -->
## CodeGraph

This project has a CodeGraph MCP server (`codegraph_*` tools) configured. CodeGraph is a tree-sitter-parsed knowledge graph of every symbol, edge, and file. Reads are sub-millisecond and return structural information grep cannot.

### When to prefer codegraph over native search

Use codegraph for **structural** questions — what calls what, what would break, where is X defined, what is X's signature. Use native grep only for **literal text** queries (string contents, comments, log messages) or after you already have a specific file open.

| Question | Tool |
|---|---|
| "Where is X defined?" / "Find symbol named X" | `codegraph_search` |
| "What calls function Y?" | `codegraph_callers` |
| "What does Y call?" | `codegraph_callees` |
| "How does X reach/become Y? / trace the flow from X to Y" | `codegraph_trace` |
| "What would break if I changed Z?" | `codegraph_impact` |
| "Show me Y's signature / source / docstring" | `codegraph_node` |
| "Give me focused context for a task/area" | `codegraph_context` |
| "See several related symbols' source at once" | `codegraph_explore` |
| "What files exist under path/" | `codegraph_files` |
| "Is the index healthy?" | `codegraph_status` |

### Rules of thumb

- **Answer directly — don't delegate exploration.** For "how does X work" / architecture questions, answer with 2-3 codegraph calls: `codegraph_context` first, then ONE `codegraph_explore` for the source of the symbols it surfaces.
- For a specific flow, start with `codegraph_trace` from -> to, then ONE `codegraph_explore` for the bodies.
- **Trust codegraph results.** They come from a full AST parse. Do not re-verify them with grep unless a file has changed after the index was built.
- **Don't grep first** when looking up a symbol by name.
- **Don't chain `codegraph_search` + `codegraph_node`** when you just want context; use `codegraph_context`.
- **Don't loop `codegraph_node` over many symbols**; use one `codegraph_explore`.
- **Index lag**: the file watcher debounces behind writes; don't re-query immediately after editing a file in the same turn.

### If `.codegraph/` doesn't exist

The MCP server returns "not initialized." Ask the user: "I notice this project doesn't have CodeGraph initialized. Want me to run `codegraph init -i` to build the index?"
<!-- CODEGRAPH_END -->
