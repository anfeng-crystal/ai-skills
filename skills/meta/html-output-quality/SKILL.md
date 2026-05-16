---
name: html-output-quality
description: 用于生成、检查和交付本地 HTML 增强产物的质量门禁；适合截图评审、扫描 dashboard、关系图、评分卡片、多维对比和需转交审核的报告。不用于短结论、命令速查、SDK 签名、普通代码解释或低风险一次性回答。
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [html, report, dashboard, quality, design-review]
---

# HTML Output Quality

> **Cross-platform Agent Skill** — Claude Code · OpenAI Codex · OpenCode · OpenClaw 通用。
> 控制 HTML 产物的触发、模板、自动检查和设计复核，不替代原有 Markdown 交付。

## 触发边界

允许生成 HTML 的场景：
- 截图评审、视觉问题标注、设计审查结果。
- 扫描 dashboard、矩阵、可筛选列表、超过 20 条的结构化结果。
- 实体/字段/插件/依赖关系图、多维对比、评分卡片。
- 需要转交审核、长期保存或反复查看的报告。

禁止生成 HTML 的场景：
- 短结论、命令速查、SDK 方法签名、普通代码解释。
- 低风险一次性回答，或 Markdown 已足够表达的少量表格。
- 需要把完整 HTML 粘进聊天上下文的交付方式。

## 标准链路

1. 产出方 skill 生成稳定 source data（JSON/TSV/Markdown 摘要）。
2. 用固定模板或脚本渲染本地 HTML；不要让模型每次自由重写大段 HTML。
3. 运行自动检查：
   ```bash
   node skills/meta/html-output-quality/scripts/check-html.mjs \
     --html <path-to-report.html> \
     --source <optional-json-or-tsv> \
     --out <output-dir>
   ```
4. 对可视化或审核型 HTML，调用 `design-review` 做视觉复核。
5. 聊天只交付结论、路径、High/Medium 问题和验证结果；不粘贴完整 HTML。

## 产物约定

- HTML：`output/html/<skill-name>/<timestamp>/index.html`
- 检查报告：`output/html/<skill-name>/<timestamp>/quality-report.md`
- 截图：`output/html/<skill-name>/<timestamp>/desktop.png`、`mobile.png`
- 原始数据保留在同目录或引用原路径；不要把大 JSON 内嵌进聊天。

## 模板约束

- 使用 `templates/report.html`、`templates/dashboard.html`、`templates/result-card.html` 作为基础。
- 单文件 HTML，内联 CSS/JS，无 React、无构建步骤、默认不访问外网。
- 必须包含 `<title>`、`<main>`、生成时间、来源说明；建议在 `<main>` 写 `data-generated-at`、`data-source`、`data-source-count`。
- 外链脚本、字体、图片默认禁止；确需外链时必须在报告中列出并说明来源。
- 审核型 HTML 必须提供有用的本地交互：搜索/筛选、分组跳转、折叠展开、排序、复制摘要或视图切换中至少一种。
- 交互控件必须可键盘聚焦，有 hover/focus/active 状态；状态变化要反馈到页面，例如可见条数、当前筛选、展开状态或复制结果。
- 不使用装饰性动效；动画只用于状态切换反馈，时长控制在 150-200ms。

## 质量门禁

`check-html.mjs` 会输出 JSON 和 Markdown 摘要。出现 High 时不得直接交付为通过：
- HTML 缺少标题或主内容区。
- 页面主体为空或关键文本过少。
- 存在外链脚本、字体或图片。
- 命中常见敏感字段：password、cookie、token、secret、authorization、数据库密码形态。
- source 条数与 HTML 声明条数不一致。
- Playwright 截图失败、截图为空，或桌面/移动主内容不可见。

Warning 可以交付但必须说明边界：
- 未提供 source，无法校验条数。
- HTML 未声明 source count。
- 页面缺少可操作控件，或交互控件未能在 Playwright 中完成基础操作验证。
- 当前环境缺 Playwright，只完成静态检查。

## Output

使用简体中文，先给结论：HTML 路径 → 检查状态 → High/Medium 问题 → 截图路径 → 限制与下一步。
