---
name: review-code
description: "Code review read-only: bugs, perf, compatibility, maintainability, test gaps. No code changes. Use fix-bug to fix, explain-code to explain."
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [code-review, quality, risk, PR]
---

# Review Code

> Cross-platform Agent Skill: keep shell examples POSIX-friendly where possible, avoid host-specific paths unless provided by the user, and preserve user worktree changes.

## 触发
- 用户要求 review、审查、质量检查、风险分析、找问题、看 PR 或给修改建议时使用。
- 只读审查，不修改代码、不提交、不声明已修复。
- 路由：要求修复现有错误用 `fix-bug`；新增或改造能力用 `implement-feature`；只问代码含义用 `explain-code`；提交、push、package、release 或能否交付用 `delivery-check`。

## 契约
- 结论必须来自当前 diff、PR、文件范围、源码、配置、测试或本轮命令输出。
- 有问题时 findings 优先，按严重程度排序；无问题时明确“未发现阻塞问题”，并说明已看范围、未覆盖范围和测试缺口。
- 每条 finding 必须有位置或明确范围、影响、依据和建议；无法定位的问题只能列为开放问题或测试缺口。

## 工作流
1. 定范围：先看 `git status --short --branch -uall`、diff/PR base、目标文件、入口、调用链、测试和用户关注点；base 不清时标明“按当前可见 diff 审查”或询问。
2. 建上下文：读相关代码、调用方、被调用方、配置、数据模型和现有测试；文件过多时先入口和变更路径。
3. 判目标一致性：识别 on target / drift / incomplete；无关重构、新依赖、公共接口或配置变动要单独列风险。
4. 查维度：正确性和兼容性必查；公共层查职责边界、命名、重复逻辑、注释质量、安全权限；性能敏感路径查循环、查询、分页、缓存、资源释放、并发和事务。
5. 查复用：仓库、标准库、官方 SDK、共享 helper、wrapper、模板或成熟三方能力已覆盖时，新写第二套方法、工具类或包装层按可维护性风险审查。
6. 查注释：公共接口、复杂逻辑、跨模块工具、业务规则、并发/事务/资源/异常边界缺少稳定注释时作为可维护性问题；过程记录和机械复述注释也要指出。
7. 收口：列无法验证处、开放问题和最小后续动作；建议不要写成已完成修复。

## 门禁
- 没有具体代码、diff 或文件范围时，不做泛泛 review；只能做有限审查并说明范围。
- 严重问题必须说明触发条件、上下游依据，以及为什么现有 guard、测试或配置拦不住。
- 验证类结论必须来自本轮命令输出；未运行命令时只能写“基于代码阅读”。
- 发现需要立即修复的问题也保持只读，除非用户明确要求进入修复或实现。
- 审查依赖运行时、数据、权限或外部系统时，必须标注未验证假设。
- 代码、注释、文档或提交信息署名 AI，或需署名时未使用 `anfeng`，应作为问题指出。

## References
- 审查维度：`references/review-rubric.md`。
- finding 格式：`references/finding-format.md`。

## 输出
使用简体中文：严重问题 -> 一般问题 -> 建议优化 -> 测试缺口。
每条 finding 使用：位置 -> 影响 -> 依据 -> 建议。
