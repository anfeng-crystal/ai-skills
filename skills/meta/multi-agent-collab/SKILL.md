---
name: multi-agent-collab
description: "任务可拆成相互独立的调查、实现、审查或验证，并需要多代理或阶段性交接时使用。"
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [multi-agent, collaboration, delegation, parallel, subagent]
---

# Multi-Agent Collaboration

> Cross-platform Agent Skill: 主 agent 负责拆分、集成和最终验证；子 agent 输出不能直接视为完成。

## 触发
- 复杂任务存在独立只读范围、互不重叠写入范围、阶段性 review/test，或用户明确要求“多代理”时使用。
- 单文件小改、共享契约未明确、强依赖即时判断、拆分成本高于收益时不拆。

## 契约
- 根据宿主能力，安全使用真实委派；不能真实委派时输出串行 handoff 计划。
- 证据包含宿主能力、ownership lock、委派范围、handoff、主会话验证。
- 最终答案必须区分真实执行、串行模拟和仅计划。

## 拆分判断
- `No split`：小而局部，或共享契约不清。
- `Explorer-only`：根因未知，只读事实可并行收集。
- `Single Worker`：共享 API/schema/helper/config 必须单 owner。
- `Staged pipeline`：Worker 完成后交 Reviewer/Tester。
- `Parallel Workers`：写入范围独立，验证也独立。
- `Integrator required`：多个 handoff 冲突或跨模块行为需统一。

## 工作流
1. 检查宿主能力：真实子代理、并行、模型选择、推理强度、写入隔离。未知就说明并降级。
2. 选择 split mode；如果用户只要方案，不启动 agent。
3. 分配 ownership lock：
   - 一个文件/模块/共享契约只能一个写 owner。
   - 非 owner 只能只读、适配消费端或 advisory。
4. 每个 delegation 必须有 `goal`、`scope`、`do_not_touch`、`output`、`verify`、`model_profile`。
5. 上下文由主 agent 中继；子 agent 不假设共享隐藏状态。
6. 主 agent 审查每个 handoff 的范围、证据、验证和冲突。
7. 只集成 accepted 结果；最终验证在主会话执行。

## 宿主能力记录
```text
Host: codex | claude-code | junie | agents-universal | unknown
Real subagents: yes/no/unknown
Parallel execution: yes/no/unknown
Model selection: yes/no/unknown
Reasoning control: yes/no/unknown
Write isolation: yes/no/unknown
Fallback: real delegation | serial handoff simulation | plan only
```

## model_profile
- `fast_probe`：快速只读搜索、文件定位、轻量事实核对。
- `deep_research`：复杂根因、跨系统推理、多假设验证。
- `code_worker`：明确实现、局部重构、测试补充。
- `reviewer`：风险审查、回归分析、测试缺口。
- `integrator`：冲突仲裁、最终合并和验收口径统一。

## Coordination Plan 字段
- `Goal`、`Split decision`、`Host mode`、`Main-agent work`
- `Runtime prerequisites`、`Ownership locks`、`Delegations`
- `Context relay`、`Existing assets`、`Shared constraints`、`Acceptance gates`

## Handoff 最小内容
- 改过或检查过的文件
- 行为变化或事实发现
- 设计判断或不确定项
- 验证方式
- 依赖/冲突
- 风险和未验证项

## 门禁
- 不允许写入范围重叠。
- 不允许任何 agent revert 用户或其他 agent 的无关改动。
- 不能把“子 agent 说通过”当主会话验证。
- 子 agent 越界改动时，结果先降为 advisory，主会话复核后再决定。
- 用户改目标时，旧结果标记为 `keep`、`advisory` 或 `discard`。
- dry-run 后正式委派、共享 contract owner 变更、宿主只能 plan-only 但用户要并行时，先停住说明并确认。
- 主 agent 不抢做已分配给 Worker 的写入范围；需要接手时先记录 reassign。

## 输出
简体中文：
- 结论：split mode，是否真实委派。
- 分工：owner -> scope -> result。
- 集成：accepted/rejected handoff。
- 验证：主会话命令和结果。
- 风险：未验证或 advisory 部分。

## 参考资料
- 宿主能力：`references/host-capabilities.md`
- 任务拆分：`references/task-splitting.md`
- 交接协议：`references/handoff-contract.md`
