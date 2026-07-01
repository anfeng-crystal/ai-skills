---
name: fix-bug
description: "Diagnose and fix bugs: errors, exceptions, failing tests, regressions, unexpected behavior. Minimal fix. Use review-code for review-only, explain-code for understanding."
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [bug, fix, debug, root-cause]
---

# Fix Bug

> Cross-platform Agent Skill: keep shell examples POSIX-friendly where possible, avoid host-specific paths unless provided by the user, and preserve user worktree changes.

## 触发
- 用户提供报错、日志、异常现象、失败测试、回归或线上行为不符合预期，并要求定位根因和修复时使用。
- 只解释代码或执行流程用 `explain-code`；只审查风险且不改代码用 `review-code`；新增能力、扩展接口或改变预期行为用 `implement-feature`。
- 混合请求按目标判定：说“修掉、解决、定位根因并改”进入本 skill；说“只看看、review、找风险”保持只读。

## 契约
- 根因必须能用一句话解释全部已知症状，且有报错栈、日志、失败用例、调用链、数据快照、配置或复现证据支撑。
- 修复只覆盖必要范围，保持接口、数据结构和调用方行为稳定。
- 交付必须有复现、测试、构建、脚本或人工验证证据；不能验证时说明替代验证和未覆盖风险。

## 工作流
1. 建事实：确认现象、复现条件、报错栈、输入数据、影响范围、最近变更和当前期望。
2. 还原路径：优先复跑失败用例或最小复现；无法复现时用日志、调用链、数据快照和差异对比补证据。
3. 定根因：沿入口、调用链、数据流、状态写入点、异常处理、事务、缓存、并发和边界值验证假设。
4. 设计修复：改代码前写出 `根因是 X，因为证据 Y`；先检查问题附近已有 helper、wrapper、SDK 封装、共享工具或平台能力，能复用就修回现有能力。
5. 实施修复：只改问题附近必要逻辑；不顺手新增第二套 util、retry、http、date、parser 或 wrapper。现有能力确有缺口时，说明缺口和最小新增范围。
6. 扫同类风险：从根因提取具体 pattern，例如函数、API、选择器、校验入口、配置键或异常条件；同类问题可纳入修复，无关问题只列风险。
7. 验证闭环：小改动跑相关测试或失败用例；公共层、共享 helper、wrapper 或公共 API 变更跑全量或相关模块测试；无测试时跑覆盖改动路径的构建、编译、脚本或人工验证。

## 门禁
- 根因未确认前不改代码；证据不足时输出需要补充的日志、数据、复现步骤或候选假设。
- 同一症状修过一次仍存在时，停止叠 patch，重读入口、调用链、状态变化和验证条件。
- 连续三个候选假设被证伪后停止修改，输出已测假设、证据、已排除原因、未知项和下一步诊断。
- 修复需要改依赖、公共 API、文件结构、数据模型、外部协议或大范围重构时，先说明必要性、影响和验证方式，并等待确认。
- 不吞异常，不返回无说明空数据，不用兜底改动掩盖根因。
- 不把排查过程、尝试路径或修复经过写入代码注释、skills、操作说明或示例说明。

## 补充约束

- **不要用 patch 把顶层控制流逻辑错位成局部块。** 典型陷阱：给包含 `try/except`、`if/elif/else`、循环或返回点的错误处理块打 patch 时，旧文本必须先匹配到整块（包括外层缩进和同类分支），否则静默破坏分支结构。补丁前先 `sed`/read 确认作用域。
- **异步/重试类修复要枚举覆盖率。** 先做，后去掉先做分支，后添加更内层分支（size-retry 500、direct 500、empty-content retry）会使 elif 变成悬挂分支，造成运行时跳过条件或进入错误的 except 分支。

## 环境兼容（Not portable）
- macOS/BSD `find` 不支持 `-printf`。
  - 跨平台替代：`find ... -type f -name 'SKILL.md' | while read -r f; do ... done | sort`
  - 或在脚本中用 Python/Node 方案，不依赖 GNU `find` 特定主操作符。

## 注释
- 新增或改动文件、类、公共函数、复杂私有函数、关键算法、事务/并发/异步/资源管理、兼容边界、异常边界和平台约束时，补稳定注释或语言原生 docstring。
- 修复 bug 的注释只写兼容边界、失败条件、业务口径或不直观原因；不写过程记录。
- 简单赋值、简单透传和显而易见条件不逐行注释；优先用命名、拆分和类型表达意图。

## References
- 根因定位：`references/root-cause.md`。
- 修复闭环：`references/repair-loop.md`。
- 注释策略：`references/comment-doc-policy.md`。

## 输出
使用简体中文：原因 -> 修改 -> 验证 -> 风险。
