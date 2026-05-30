---
name: design-review
description: "需要审查已渲染 UI、截图、本地 HTML 产物、布局、字体、间距、颜色、层级、一致性或响应式质量时使用。"
compatibility: claude-code-only
---

# Design Review

> Cross-platform Agent Skill: 只基于视觉证据做只读审查；需要实现时转 `frontend-design`，除非用户明确要求直接改。

## 触发
- 用户说“丑、怪、看着不对、不统一、不够精致”，或要求视觉审查、截图评审、本地 HTML 报告验收、响应式检查时使用。
- 不做完整 UX 流程审计，除非视觉问题是重点。
- 如果问题本质是运行时报错、数据错误或渲染失败，转 `fix-bug`。

## 契约
- 输出按严重程度排序的视觉问题，必须绑定渲染证据。
- High/Medium 问题必须包含区域、严重级别、缺陷、证据路径/视口、最小修复方向。
- 没有渲染证据时只能做 `limited review`，并说明缺口。

## 证据路径
1. 优先使用用户给的 URL、文件路径或截图。
2. 目标优先级：显式 live URL -> localhost -> `file://` / 本地 HTML -> 用户截图 -> source-only limited review。
3. 本地 HTML 产物优先跑共享门禁：
   ```bash
   node skills/meta/html-output-quality/scripts/check-html.mjs \
     --html <path-to-index.html> \
     --source <optional-json-or-tsv> \
     --out <artifact-dir>
   ```
4. 响应式页面至少检查桌面和 375px 移动视口。
5. 截图投诉直接以截图为证据；若用户给参考图或旧版好图，先列当前与参考的视觉差异。
6. 无法渲染时，不推断不可见状态。

## 检查项
- 布局：对齐、网格、间距尺度、垂直节奏、密度。
- 字体：层级、行宽、行高、字重、截断和换行。
- 颜色：对比度、语义一致性、深浅模式、状态色。
- 层级：主行动、分组、扫描顺序、留白、渐进呈现。
- 组件：按钮、卡片、输入、图标、圆角、阴影、重复项一致性。
- 交互：hover、focus、active、disabled、loading、状态反馈。
- 响应式：移动导航、触控目标、图片、表格、平板宽度、溢出。
- HTML 产物：证据区、长文本换行、表格溢出、搜索/过滤/排序是否真的提升审阅效率、外链资源和敏感数据暴露。
- 截图投诉：一句话定位缺陷类型，再给最小材质、间距、字体、颜色、层级或布局修复方向。

## 严重级别
- High：空白/破碎、不可读、严重溢出、文字不可见、敏感信息暴露、第一眼不专业。
- Medium：可用但明显粗糙，如间距/字体/图标不一致、层级弱、响应式别扭、换行差。
- Low：局部 polish，影响有限。

## 门禁
- 本 skill 不改 UI。
- 有 High 问题的 HTML 产物不能判定为可交付。
- HTML 产物缺 evidence 区、截图不可见、外链资源或敏感数据暴露，一律 High。
- 交互审查至少看 hover/focus、键盘可达、可见反馈，以及搜索/过滤/排序/展开/复制/跳转中是否有一个真有用。
- 不凭审美泛泛评价；每条问题绑定可见区域。
- 只有单截图/单视口时，明确覆盖范围有限。

## 输出
简体中文：
- 优先写到 `.jez/artifacts/design-review.md`；HTML 产物写到门禁输出目录的 `design-review.md`。
- 结论：通过 / 有问题可通过 / 阻塞。
- Evidence：URL/路径/截图/视口。
- High、Medium、Low：区域 -> 缺陷 -> 影响 -> 修复方向。
- What looks good：只保留应继续沿用的视觉模式。
- Top fixes：最多 3 条。
- Handoff：需要实现时转 `frontend-design` 或 `fix-bug`。
