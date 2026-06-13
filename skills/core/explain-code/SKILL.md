---
name: explain-code
description: "Explain code read-only: logic, call chain, data flow, module responsibilities, design intent. Use fix-bug to fix, review-code to review."
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [code, explanation, read-only, architecture]
---

# Explain Code
> Cross-platform Agent Skill: use host-neutral paths and current project commands.


## 触发
- 用户要求解释代码、梳理流程、说明设计意图、分析函数或模块职责、理解错误原因但未要求修复时使用。
- 只读，不修改代码、不生成补丁、不把建议当作已完成修改。
- 需要定位并修复错误用 `fix-bug`；需要审查问题或风险用 `review-code`；需要新增或改造能力用 `implement-feature`。

## 契约
- 关键判断必须能对应到代码、配置、测试、文档或用户输入。
- 缺材料时列出假设和需要补充的文件、日志或运行信息；不要把命名推断写成事实。
- 输出按用户问题深度压缩，不做无关背景扩展。

## 工作流
1. 定对象和模式：模块职责、函数用法、执行流程、调用链、数据流或设计意图；确认只读。
2. 建证据：入口优先，例如主函数、路由、事件处理、公共 API；然后读调用方、被调用方、失败路径、数据结构、配置、外部依赖、测试和文档。
3. 控制范围：相关文件过多时先读入口和调用方，再按用户关注点补充；缺少入口时先给材料清单。
4. 组织说明：职责 -> 入口/流程 -> 设计原因 -> 关键边界；复杂逻辑补事务、缓存、并发、权限、平台约束或算法原因。
5. 说明复用关系：仓库已有 helper、wrapper、SDK 封装、模板或标准能力与当前实现强相关时，点明调用入口、共享层职责和复用收益。
6. 收口：列易错点、可验证入口、未确认假设和建议继续阅读的位置。

## 门禁
- 没有可读代码、文件路径、片段或调用入口时，不做具体实现判断。
- 关键分支、数据流转、异常处理依赖假设时必须标注假设，并说明假设不成立时结论如何变化。
- 发现明显 bug 或风险时，只能作为“可能问题”提示；用户要求修复或审查时切到 `fix-bug` 或 `review-code`。
- 如果用户问“为什么没有自己再造一套”，先说明共享层职责、调用入口和复用收益，再展开局部实现细节。

## References
- 解释结构和表达模式：`references/explanation-patterns.md`。

## 输出
使用简体中文，按需压缩：概述 -> 入口/流程 -> 设计原因 -> 关键边界 -> 假设/需补充。
