---
name: frontend-design
description: "Production frontend: build distinctive UI with bold aesthetics. No generic AI slop. Use design-review to review existing pages."
license: Complete terms in LICENSE.txt
---

## Trigger Boundary
- Use this skill when building or materially changing frontend UI: components, pages, apps, interactions, or visual systems.
- Use `design-review` when the task is read-only visual QA of an existing rendered page, screenshot, or HTML artifact.
- Use `frontend-design-principles` for complex UI direction work where multiple visual directions, app/marketing routing, or strong differentiation matters.

# Frontend Design

用于实现有明确审美判断的生产级前端。目标不是堆装饰，而是让界面与领域、用户任务、已有设计系统和技术约束一致，并避免模板化 AI 观感。

## 工作流

1. 先确认上下文：目标用户、核心任务、产品语气、技术栈、可用设计系统、现有组件和必须兼容的响应式范围。
2. 优先沿用现有设计系统、组件库、字体、spacing、token 和交互模式；从零设计时才建立新的视觉语言。
3. 选择一个清晰方向：安静高密度、编辑感、工业工具、柔和消费级、终端感、数据控制台等。方向必须服务领域，不为了显眼而显眼。
4. 实现真实可用代码，不交付静态假壳；按钮、表单、导航、状态、空态、加载、错误和响应式都按目标流程补齐。
5. 复杂 UI 先加载 `frontend-design-principles`，完成领域词、颜色世界、签名元素和默认项拒绝，再进入实现。

## 设计门禁

- 字体、颜色、密度、布局和动效都要能解释“为什么适合这个产品/页面”。
- 避免默认模板：紫蓝渐变、通用卡片堆、无领域感图标、过强阴影、装饰性漂浮元素、单一色系、没有实际工作流的 hero。
- 工具类、后台、CRM、SaaS 优先信息密度、可扫描性、稳定导航和重复操作效率；不要做营销页式大 hero。
- 营销页和品牌页必须让产品/人物/地点/对象在首屏可见，并在移动和桌面都露出下一段内容的线索。
- 不把 UI 卡片套进卡片，不用说明文字教用户“如何使用本界面”，不用可见文案描述实现技巧。
- 文本必须在按钮、卡片、表格和移动视口中不溢出；固定格式元素要有稳定尺寸或响应式约束。

## 验证

能跑本地服务时必须启动，并给用户 URL。实现后尽量用 Browser/Playwright 验证：
- 桌面和移动视口至少各一次。
- 关键交互可点击、可聚焦、状态可见。
- 图片、canvas、图标、字体和外链资源实际渲染。
- 控制台无致命错误。
- 文本不遮挡、不溢出，主要内容不空白。

无法运行时说明原因，并至少做源码层面的响应式、资源路径和交互状态检查；不能声称已视觉验证。

## 输出
交付时简要说明：实现范围、运行 URL 或无法运行原因、验证过的视口/交互、未覆盖风险。需要只读审查时转 `design-review`。
