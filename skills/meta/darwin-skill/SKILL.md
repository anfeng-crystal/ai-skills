---
name: darwin-skill
description: "需要用证据、测试 prompt、评分对比和回滚机制优化本地可编辑 SKILL.md 时使用。"
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [skill, optimizer, darwin, auto-tune, evaluation]
---

# Darwin Skill

> Cross-platform Agent Skill: 只优化本地可编辑 skill；使用当前项目命令和宿主中立路径。

## 触发
- 优化本地 skill、检查 skill 回归、验证 prompt 效果、判断“这个 skill 是否真的有用”时使用。
- 第三方 intake / 安全审查转 `skill-vetter`。
- bundled/cache/system skill 默认只评分和建议，不直接改；用户点名 exact path 时除外。

## 契约
- 只有实际提升 agent 行为的修订才保留，不能只追求文字好看。
- 证据包含 baseline、with-skill 或 dry-run 模拟、结构评分、diff、验证输出。
- 优化前必须先提取能力清单；优化后必须证明能力没有静默丢失。
- 失败修订必须回滚，或保持未提交并说明原因。

## 运行时评分
总分 100；结构 60、效果 40。每项 1-10 分后按权重折算：
- 触发精度：description 只写何时加载，不概括流程。
- 运行价值：正文直接告诉 agent 当前该怎么做。
- 边界：能路由到正确 skill/tool，能阻止危险动作。
- 可执行性：步骤有可观察输入/输出。
- Token 经济性：删除动机、历史、宽泛教学和聊天式示例。
- 证据/验证：验证强度匹配风险。
- 失败行为：说明何时停止、询问、降级或 handoff。
- 行为增量：with-skill 在典型 prompt 上应优于 no-skill。

## 产物记录
- `test-prompts.json`：记录 `id`、`prompt`、`expected`、`eval_focus`、`baseline_risk`。
- `results.tsv`：至少记录 `skill`、`prompt_id`、`baseline_score`、`old_score`、`new_score`、`avg_skill_delta`、`eval_mode`、`model_set`、`status`、`notes`。
- `eval_mode` 只能是 `full_test` 或 `dry_run`；不能跑子 agent 时也要写明 dry-run 依据。
- 需要报告时输出 Markdown 主报告；HTML/PNG 成果卡片只作为增强产物。

## 工作流
1. 锁定范围：列出可编辑本地 skill 路径，把只读 bundled/cache skill 分开。
2. 需要隔离时按当前宿主/git 规则创建优化分支；不要破坏用户已有脏改。
3. 为每个目标准备 1-3 个典型 prompt；要复用时写入 `test-prompts.json`。
4. 建 baseline：记录不用 skill 时最可能漏掉、越界或路由错误的点。
5. 跑 with-skill 与 no-skill 对比；可用多模型/子 agent 时至少覆盖默认模型和一个轻量/不同能力模型。
6. 读当前 `SKILL.md`，先提取能力清单，再找人类说明书噪音。能力清单至少覆盖：
   - 触发和路由：何时用、何时不用、转交哪个 skill/tool。
   - 工具和命令：脚本、参数、状态码、输出文件、配置路径。
   - 门禁和边界：确认点、只读/写入边界、敏感信息、破坏性动作。
   - 回退和异常：失败状态、降级路径、阻塞条件、恢复方式。
   - 产物和验证：报告、测试 prompt、results.tsv、截图、dry-run、doctor、lint/test。
7. 每个能力点必须明确处理结果：保留、合并、移到 reference、脚本承载、或说明理由后删除；不允许静默删除行为。
8. 找人类说明书噪音：
   - 来源故事、理念、销售话术、长示例、发布叙事。
   - 系统/项目规则已覆盖的通用工程常识。
   - 面向用户教程，而不是给 agent 的动作。
9. 改成中文运行时卡片：
   - 触发
   - 契约
   - 工作流
   - 门禁
   - 输出
   - 必要时才引用 references
10. 验证：
   ```bash
   git diff --check -- <skill-files>
   node scripts/validate-cross-platform.mjs
   ```
   skill 自带脚本或测试时跑对应验证。
11. 做能力覆盖复核：逐项确认能力清单仍有落点；格式校验通过但能力丢失时视为失败。
12. 重新评分并写入 `results.tsv`；只有 `new_score > old_score` 且相对 baseline 增量变大才保留。
13. 行为变差或能力覆盖失败就回滚该 skill 文件；已提交时用 `git revert`，不使用 `reset --hard`。

## 门禁
- 不往 skill 目录加 README、changelog 或过程记录。
- 不把单次会话的路径、命令、决策写成通用规则。
- 低风险本地文本优化不需要停住确认；涉及外部状态、共享配置、memory 或破坏性动作才停。
- 没有真实 prompt 运行或明确 dry-run 模拟时，不声称“已实测 with-skill”。
- 改动不能改变 skill 核心用途；只能优化表达、边界、流程和验证。
- active skills 的语言选择以语义完整和用户语境为准：中文为主；命令、字段名、状态码、工具标识和能明显省 token 的短标签可用英文；不能整篇套英文模板或因英文压缩丢失语义。
- 更短不是成功标准；能力等价和行为增量优先于 token 压缩。
- 清理临时测试输出时只删本 skill 生成的 `*-test-output-*`、`*-with-skill-*`、`*-no-skill-*`，保留 `test-prompts.json` 和 `results.tsv`。

## 输出
简体中文：
- 结论：保留 / 回滚 / 阻塞。
- 目标：skill 路径。
- 能力覆盖：保留、合并、迁移、删除的能力点摘要。
- 问题：旧 skill 哪些内容降低 AI 运行效果。
- 修改：具体运行时规则变化。
- 验证：命令和结果。
- 风险：未跑的行为测试或仍过长的引用。
