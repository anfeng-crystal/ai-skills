---
name: frontend-design-principles
description: "复杂 UI 设计深化：为 dashboard、admin、SaaS、landing page、marketing site 等生成领域化视觉方向、签名元素和展示前自检。"
---

# Frontend Design Principles

> Cross-platform Agent Skill: 用于复杂 UI 的设计判断；低风险单组件或明确现有设计系统内的改动由 `frontend-design` 直接实现。

## 触发
- 多页面、多视图、客户级页面、品牌页、复杂 dashboard、数据密集工具、marketing/landing page，或用户要求“更有设计感/不要模板感”。
- 只读视觉审查转 `design-review`；具体实现仍由 `frontend-design` 承接。
- 信息足够且风险低时不要停住等确认；用保守假设继续实现，并在输出中列明。

## 路由
- App guidance: 构建 dashboard、admin、SaaS、内部工具、设置页、表格/表单/列表等重复工作界面时，读 `app.md`。
- Marketing guidance: 构建 landing page、品牌页、宣传页、海报、首屏印象优先页面时，读 `marketing.md`。
- 技术细节需要 spacing、depth、typography、color、dark mode 时，读 `references/principles.md`。
- 混合项目按页面目的拆开：官网读 marketing，产品工作台读 app。

## 设计前置
在写代码前，用最短文字回答：
- 这个人是谁：真实使用者、使用场景、打开页面前后在做什么。
- 他要完成什么：具体动词，而不是“使用系统”。
- 页面应该是什么感受：避免“现代、简洁、好看”这类无差别词。

然后产出四项输入：
- `Domain`：来自产品世界的 5+ 个概念、物件、动作或隐喻。
- `Color world`：这个领域真实存在的 5+ 种颜色、材质或光线。
- `Signature`：一个只属于这个产品的视觉、结构或交互元素。
- `Defaults to reject`：3 个该类界面最容易默认化的视觉或结构选择，以及替代方案。

## 确认门禁
- 信息不足、视觉方向有多个高风险分支、用户明确要审核，或实现成本明显受方向影响时，先给方向提案并等确认。
- 方向提案必须引用 Domain、Color world、Signature 和 Defaults to reject。
- 去掉产品名后仍无法识别领域时，继续探索，不进入编码。
- 已有明确设计系统时，不另起视觉语言；只在局部签名、层级、密度和交互上增强。

## 展示前自检
交付给用户前先自查并修到可交付：
- Swap test：换成常见字体、标准布局或普通卡片后是否几乎无差别；无差别说明默认化。
- Squint test：眯眼看仍能感知层级，且没有刺眼跳点。
- Signature test：能指出签名元素落在哪些具体组件或交互上。
- Token test：CSS 变量、颜色、spacing 名称和用途能反映产品世界，而不是通用模板。
- Workflow test：主流程、空态、错误态、加载态、移动端至少有合理落点。

## 输出
简体中文，面向实现 handoff：
- 设计方向：Domain / Color world / Signature / Defaults to reject。
- 应用位置：签名元素落到哪些组件、布局、动效或 token。
- 验证重点：必须看的视口、交互、资源和文本溢出风险。
- 需要实现时，转 `frontend-design` 并带上以上输入。
