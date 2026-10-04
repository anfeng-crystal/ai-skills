---
name: html-output-quality
description: "检查本地离线 HTML 报告的数据、隐私与视觉质量；不负责决定是否生成报告。"
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
   有 JSON/TSV/CSV source 时增加 `--source <file>`。CSV/TSV 首条记录视为表头，支持引号内换行；JSON 接受顶层记录数组、唯一嵌套数组或明确的非负整数 `recordCount`/`_recordCount`。多个数组且未声明条数时跳过比对并提示，不能取最大数组或编造条数。输出 JSON/Markdown 报告；环境支持时生成 desktop/mobile 截图。缺默认浏览器时可用 `--browser-channel chrome` 或 `--browser-path <executable>` 指定已安装浏览器；也支持 `HTML_QUALITY_BROWSER_CHANNEL`、`HTML_QUALITY_BROWSER_PATH`（兼容 `WEB_ACCESS_BROWSER_PATH`），命令参数优先，路径和 channel 不可同时设置。不自动安装浏览器，不复用用户登录会话。
4. 对实际截图检查内容、溢出和可读性；截图保留交互冒烟前的初始页面，冒烟只覆盖支持的代表性控件，不能代替逐项交互与视觉复核。单个视口或交互失败不丢失已完成截图，报告标出失败阶段；失败或未运行要准确说明。仅聚焦、输入值变化或已有状态属性不能证明交互有效，冒烟需观察可见内容、筛选、排序或折叠状态变化。

## 检查范围与结果

- 检查器针对自包含的离线数据报告：标题、主内容、来源、生成时间、条数、外链资源、敏感字段和截图。报告应声明可用的来源与时间，不能伪造数据计数。
- High 不直接称通过：确认是真实内容/隐私/数量错误还是检查器适用范围冲突。适用范围不符时使用项目等价检查并说明，不为过关删除用户要求的内容。
- 无 source/count、无交互或缺 Playwright 属于检查限制；静态报告无需为了消除交互 Warning 增加无用控件。source 读取失败会记录 High、跳过条数比对并继续其余检查，报告只保留稳定错误代号。敏感字段命中须核实，不能把凭据写入交付。
- 不强制新建顶层目录、框架或过程文档；视觉检查使用独立离线上下文并阻止网络请求，避免打开报告时加载外链或发送数据。发现动态请求时只记录来源域，不保存请求路径、查询参数或载荷；需要联网的页面按已授权需求使用项目等价检查，不能以离线截图证明在线功能已验证。

## 输出

交付实际产物路径、检查结论、影响使用的问题、截图及未验证项；不粘贴完整 HTML 或完整原始数据。
