---
name: html-output-quality
description: "需要检查本地离线 HTML 报告的数据一致性、敏感信息和视觉结果时使用；不作为普通回答或所有网页的强制生成流程。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.0.0"
  tags: "html, report, dashboard, quality"
---

# HTML Output Quality

> Cross-platform Agent Skill: 对需要导出/复核的本地 HTML 提供检查器，不决定用户是否需要 HTML，也不强制模板或交互。

## 使用范围

- 用户要求检查本地 HTML，或交付需要离线报告、数据条数核对与桌面/移动截图时使用。普通问答、代码解释和少量 Markdown 表格不触发。
- 已有项目构建、测试和视觉验收足够时直接复用，不另加整套产物流程。用户要求特定框架、布局或产物路径时遵循需求。

## 执行

1. 确定 HTML、可用 source data 和输出目录；优先现有文件，不为检查再复制原始敏感数据。
2. 本 Skill `templates/` 可作本地报告起点，不强制重写现有页面。搜索、筛选、排序等交互仅在内容需要时增加；已有控件要可键盘操作并反馈状态。
3. 使用真实 Skill 路径运行：
   ```bash
   node <skill-root>/scripts/check-html.mjs --html <file> --out <dir>
   ```
   有 JSON/TSV/CSV source 时增加 `--source <file>`。输出 JSON/Markdown 报告；环境支持时生成 desktop/mobile 截图。
4. 对实际截图检查内容、溢出和可读性；自动结果不代替视觉复核。截图失败或未运行要准确说明。

## 检查范围与结果

- 检查器针对自包含的离线数据报告：标题、主内容、来源、生成时间、条数、外链资源、敏感字段和截图。报告应声明可用的来源与时间，不能伪造数据计数。
- High 不直接称通过：确认是真实内容/隐私/数量错误还是检查器适用范围冲突。适用范围不符时使用项目等价检查并说明，不为过关删除用户要求的内容。
- 无 source/count、无交互或缺 Playwright 属于检查限制；静态报告无需为了消除交互 Warning 增加无用控件。敏感字段命中须核实，不能把凭据写入交付。
- 不强制新建顶层目录、框架或过程文档；默认保持离线，外链需求单独核对数据外发和授权。

## 输出

交付实际产物路径、检查结论、影响使用的问题、截图及未验证项；不粘贴完整 HTML 或完整原始数据。
