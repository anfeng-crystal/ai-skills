---
name: multi-agent-collab
description: Multi-agent orchestration: task decomposition, role routing, parallel execution.
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [multi-agent, collaboration, delegation, parallel, subagent]
---

# Multi-Agent Collaboration

> **Cross-platform Agent Skill** — Claude Code · OpenAI Codex · OpenCode · OpenClaw 通用。
> 跨平台 SKILL.md，遵循开放 Agent Skill 规范。

## 原则

主 agent 是调度器和最终责任人：先判断是否拆分，再定分工、控边界、同步上下文、验收结果、做最终集成。子 agent 默认彼此不知道对方做了什么，所有协作事实都必须通过主 agent 的 handoff/context relay 传递。

不要把某个宿主的工具名、模型名或推理参数写进通用委派指令。用 `model_profile` 表达能力需求，按当前宿主能力映射到实际模型、推理强度或默认模型。

## 快速工作流

1. **Host Capability Check**：确认当前宿主是否支持真实子代理、并行执行、模型选择、推理强度选择、写入隔离；不支持时降级为 Coordination Plan 或串行 handoff 模拟。
2. **Split Decision**：先决定 `No split` / `Explorer-only` / `Single Worker` / `Staged pipeline` / `Parallel Workers` / `Integrator required`，并说明理由。
   - 如果用户只要求“多代理执行方案/分工方案，我来审核”，默认只输出 Coordination Plan，不真实派发 agent；只有用户明确要求执行委派，或审核通过后进入实施阶段，才启动真实子代理或串行 handoff。
3. **Ownership Lock**：给每个 Worker 指定唯一写入 owner；共享 schema、DTO、接口契约、公共 helper、配置、测试 fixture 只能有一个 owner。
4. **Coordination Plan**：写清 goal、main-agent work、host mode、delegations、context relay、shared constraints、acceptance gates。
5. **Context Relay**：子代理间不直接假设共享上下文；主 agent 把 Worker handoff、diff 摘要、验收标准转交给 Tester/Reviewer/Integrator。
6. **Handoff Review**：按交接协议检查 scope、越界、证据、验证、风险；不接受没有证据的完成结论。
7. **Final Integration**：主 agent 解决冲突、补齐验证、输出结论；不要拼接子 agent 输出。

## Host Capability Check

委派前先判断当前宿主：

```text
Host: {codex | claude-code | junie | agents-universal | unknown}
Real subagents: yes/no/unknown
Parallel execution: yes/no/unknown
Model selection: yes/no/unknown
Reasoning control: yes/no/unknown
Write isolation: yes/no/unknown
Fallback: {real delegation | serial handoff simulation | plan only}
```

- 能真实委派时，按宿主工具执行。
- 不能真实委派但能继续工作时，用串行 handoff 模拟角色分工。
- 宿主能力不明时，不假装已派 agent；输出可执行 Coordination Plan。
- 具体宿主差异见 `references/host-capabilities.md`。

## Split Decision Matrix

| 决策 | 适用场景 |
|------|----------|
| `No split` | 单文件/小改动、共享契约强耦合、下一步依赖即时判断、拆分成本高于收益 |
| `Explorer-only` | 根因未知、只读调查可并行、写代码风险高 |
| `Single Worker` | 核心接口、共享 schema、公共 helper 或同一文件必须统一修改 |
| `Staged pipeline` | 开发和测试强依赖；先 Worker，再把 handoff + diff 摘要交给 Reviewer/Tester |
| `Parallel Workers` | 写入范围独立、验证独立、共享契约已有唯一 owner |
| `Integrator required` | 多个 handoff 冲突、跨模块集成复杂、结果互相矛盾 |

不满足独立写入范围、独立验证方式或可交接产物时，不要为了多代理而拆分。详细规则见 `references/task-splitting.md`。
方案审核阶段即使存在可并行调查，也优先把调查项写成 Explorer delegation 清单；不要为了让方案看起来“已并行”而启动长时间 explorer，避免在用户等待审核方案时消耗上下文和时间。

## Model Profile Routing

用 `model_profile` 表示任务需要的能力，不在通用 skill 中写死模型名：

| profile | 用途 |
|---------|------|
| `fast_probe` | 快速只读搜索、文件定位、轻量事实核对 |
| `deep_research` | 复杂根因、跨系统推理、多假设验证 |
| `code_worker` | 明确实现、局部重构、测试补充 |
| `reviewer` | 风险审查、回归分析、测试缺口 |
| `integrator` | 冲突仲裁、最终合并判断、验收口径统一 |

如果宿主不支持模型或推理强度选择，使用默认模型，但保留 `model_profile` 作为任务意图。详细路由见 `references/model-routing.md`。

## Coordination Plan 模板

```text
Goal: {用户目标和成功标准}
Split decision: {No split | Explorer-only | Single Worker | Staged pipeline | Parallel Workers | Integrator required} because {理由}
Host mode: {real delegation | serial handoff simulation | plan only}; capabilities={简述}
Main-agent work: {只读探索、调度、context relay、验收、集成；不得实现已分配给 Worker 的范围}
Runtime prerequisites: {密码/环境变量/账号/路径；缺失项向谁获取}
Ownership locks:
- {owner}: write_scope={文件/目录/模块}; do_not_touch={范围}; shared_contract_owner={yes/no}
Delegations:
- {role}: goal={具体目标}; scope={owned files/questions}; output={handoff/report/patch}; verify={命令或证据}; model_profile={profile}
Context relay:
- From {Worker/Explorer}: pass {handoff/diff/key findings} to {Reviewer/Tester/Integrator}
Existing assets: {已检查的 helper/wrapper/template/SDK/fixture，复用决定}
Shared constraints: {禁止修改范围、注释策略、署名、风险边界}
Acceptance gates: {完成条件}
```

每个 delegation 必须有 `scope`、`output`、`verify`、`model_profile`。写代码类 delegation 还必须有 ownership lock。

## Ownership Lock

- Worker 只能修改自己的 `write_scope`。
- 共享 contract 文件只能有一个写入 owner；其他 agent 只能做 consumer 适配、只读审查或 advisory。
- 主 agent 不实现已分配给 Worker 的范围。需要接手时先记录 `reassign`，把原 Worker 结果标记为 `advisory` 或 `discard`。
- Worker 越界改动默认不接受；只有主 agent 复核证据后，才能手工集成必要部分。
- 不允许任何 agent revert 用户或其他 agent 的无关改动。

## Context Relay Contract

Worker 交付给 Reviewer/Tester/Integrator 前，主 agent 必须转交：

- `Changed Files`
- `Behavior Changed`
- `Design Decisions`
- `How To Test`
- `Dependencies/Conflicts`
- `Risks`
- 相关 diff 摘要或关键行引用

Reviewer/Tester 不能在不了解实现细节时直接“测一下”。如果缺少 handoff 或 diff 摘要，先要求补齐上下文，再执行审查或测试。

## 角色

- **Explorer**：只读探索，不改文件；适合 `fast_probe` 或 `deep_research`。
- **Worker**：在明确 ownership lock 内实现改动；适合 `code_worker`。
- **Reviewer/Tester**：基于 handoff + diff 摘要查风险、回归和测试缺口；适合 `reviewer`。
- **Integrator**：汇总多 handoff、处理冲突、统一验收口径；适合 `integrator`。

Personality 仅作为可选沟通风格，不进入默认调度路径；需要时再读取 `references/agent-personalities.md`。

## 用户确认检查点

| 场景 | 停住确认内容 |
|------|-------------|
| 宿主只能 plan-only，但用户要求真实并行 | 当前宿主无法确认真实子代理能力，是否改为串行 handoff 或换宿主执行 |
| dry-run 后正式委派 | 计划已制定，委派 {N} 个 agent，确认执行 |
| 需要改共享 contract owner | 共享文件只能一个 owner，确认由 {owner} 修改 |
| 用户改目标/优先级 | 目标已变更，旧结果标记为 advisory/discard，重新制定计划 |
| 子 agent 越界改文件 | 发现越界修改，非 owner 结果降级，确认重拆或手工集成 |

## 什么时候重写计划

- 用户改目标、优先级或验收口径
- 宿主能力与原计划不匹配
- 子 agent 越界或 ownership lock 失效
- 新证据推翻根因或实现方向
- Worker handoff 无法支持 Reviewer/Tester 理解改动
- 多个 handoff 结论冲突

重写时标记旧结果：`keep`（仍可用）、`advisory`（仅参考）、`discard`（丢弃）。

## 最终交付前检查

- 已明确 split decision，并说明为什么拆或不拆。
- 宿主能力和降级方式已说明，没有把计划说成已真实委派。
- Worker 写入范围不重叠，共享 contract 只有一个 owner。
- 主 agent 没有抢做已分配给 Worker 的实现范围。
- Reviewer/Tester 输入包含 Worker handoff、diff 摘要和验收标准。
- 子 agent 结果符合原始 scope，越界已复核或丢弃。
- 写代码类 Worker 已说明检查了哪些现成能力，为什么没重复造轮子。
- 验证优先级：项目原生命令/CI > 最小复现 > lint > 接口核对 > 人工复核。
- 剩余风险和未验证项已明确。

## 输出

简体中文。结论 → split decision → 分工/执行模式 → 改动/发现 → 验证 → 风险 → 后续建议。

## References

- 拆分规则：`references/task-splitting.md`
- 宿主能力：`references/host-capabilities.md`
- 模型路由：`references/model-routing.md`
- 角色 prompt 模板：`references/agent-prompts.md`
- 交接协议：`references/handoff-contract.md`
- 冲突处理：`references/conflict-resolution.md`
- 复核清单：`references/review-checklist.md`
- 注释策略：`references/code-comment-policy.md`
- 角色性格定义（可选）：`references/agent-personalities.md`
