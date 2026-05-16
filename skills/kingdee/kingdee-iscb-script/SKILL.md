---
name: kingdee-iscb-script
description: ISCB DSL: integration flows, value transforms, service process scripts, WebAPI scripts.
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [kingdee, ISCB, integration, DSL, script]
---

# Kingdee ISCB Script

> **Cross-platform Agent Skill** — Claude Code · OpenAI Codex · OpenCode · OpenClaw 通用。
> 跨平台 SKILL.md，遵循开放 Agent Skill 规范。

## 触发边界
- 用户明确涉及集成云脚本、ISCB、ISC 脚本、ISCB DSL、数据集成方案脚本、值转换规则、服务流程脚本节点、自定义 API 或 WebAPI 脚本时使用。
- 普通苍穹 Java 二开不使用；改用 `kingdee-cosmic`。
- KingScript 或苍穹脚本插件不使用；改用 `kingdee-kingscript`。
- 只说“苍穹脚本”但未说明 ISCB/集成云/数据集成上下文时，先澄清脚本体系，不默认扩散到 ISCB。
- 普通 JavaScript、TypeScript 或浏览器脚本不使用。

## 快速工作流
1. 先确认任务类型：生成、解释、修改、函数查询、语法查询、静态检查、编译校验或运行验证。
2. 先确认脚本上下文：普通引擎脚本、数据集成方案、值转换规则、服务流程脚本节点、自定义 API 或 WebAPI。
3. 先检查当前工作区已有 `.iscb`、共享脚本段、资源别名约定、函数组合和现成节点实现，能复用时优先复用。
4. 再读 `references/index.md` 选择当前任务需要的 reference；默认只读模式和约定。
5. 默认按普通引擎脚本处理；只有用户明确给出平台节点、资源、连接别名、API 参数或对象结构时，才使用平台上下文变量。
6. 只有用户明确要求校验或运行时，才使用 `scripts/iscb_skill_validator.py`。
7. 只有用户明确要求保存到本地时，才写 `.iscb` 文件。

## References
- 资料导航：`references/index.md`
- 上下文路由：`references/context-routing.md`
- 写法约定：`references/conventions.md`
- 常用模式：`references/patterns.md`
- 引擎函数：`references/functions-engine.md`
- 平台函数：`references/functions-platform.md`、`references/functions-platform-services.md`
- 平台资源：`references/resources.md`
- 语法细节：`references/syntax-complete.md`
- 校验工具：`scripts/iscb_skill_validator.py`
- 注释规范：`references/comment-policy.md`

## 代码注释策略
- 生成或修改 ISCB DSL 时，复杂脚本段、工具函数、平台上下文访问、资源调用、写入动作、异常/失败边界必须写功能性注释。
- ISCB 注释使用 `//` 单行注释，写在复杂段落或函数前；不要伪造块注释，不在每行尾部堆砌说明。
- 注释说明上下文变量来源、资源别名/API 参数前提、输入输出、写入副作用、失败后状态和需要在平台补齐的配置。
- 简单赋值、简单映射、纯字段搬运不逐行注释；但整段脚本如果没有注释会难以理解，必须补段落级说明。

## Guardrails
- 不凭经验发明函数、平台变量、连接资源、API 参数或对象结构。
- `src`、`tar`、`param`、`cn`、`$process`、`#request` 只在用户明确说明对应平台上下文时使用。
- 平台上下文缺少资源、别名、参数定义或对象结构时，只能输出参考脚本，并说明需在苍穹集成平台补齐并验证。
- 默认不自动编译、不自动运行、不自动保存。
- 校验结果必须区分：未校验、已静态校验、已编译校验、已运行验证。
- 新增工具函数或复杂脚本段必须写功能性注释；不写实施过程、排查过程、修改经过或交付口径。
- 涉及代码、注释、文档或提交时，署名必须遵守全局规则：不用 AI，统一用 `anfeng`。
- 当前工作区已有共享脚本段、函数组合、资源别名约定或现成节点实现时，不复制一份同逻辑 ISCB 脚本。

## Output
使用简体中文：上下文 → 依据 → 脚本/说明 → 校验状态 → 风险
