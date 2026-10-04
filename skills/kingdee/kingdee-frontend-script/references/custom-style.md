# 自定义 CSS 样式

官方依据：[自定义样式，教你如何做出自己的控件定制效果](https://vip.kingdee.com/knowledge/771087151064286720?productLineId=29&isKnowledge=2&lang=zh-CN)（帮助中心功能介绍，更新于 2025-10-28；2026-09-26 核验正文）。适用入口是设计器控件“样式面板 → 自定义样式”，不是浏览器 CSS 标准、全局扩展 CSS 或独立 KDApi 资源样式表的通用限制。正文明确 at-rules、注释、作用域与 hash 类名规则，未声明最低平台版本；具体目标与正文有差异时按目标证据处理。

苍穹控件自定义样式的选择器语法与限制。元素定位用浏览器 F12(Elements 面板选中目标元素)跨平台完成,**不依赖任何单平台本地拾取工具**。

## 选择器语法
| 选择器 | 示例 | 说明 |
|---|---|---|
| `$` | `$ { background:red; }` | 当前控件 className(系统保留,不可自定义) |
| `'themeColor'` | `background:'themeColor';` | 平台主题色,**必须单引号** |
| `$ > div` | `$ > div { ... }` | 直接子元素 |
| `$ .class` | `$ .class { ... }` | 后代(`$` 后**必须留空格**) |
| `[data-code="x"]` | `td[data-code="kded_name"]` | 字段定位(表格字段必用) |
| `[data-key="x"]` | `li[data-key="tabKey"]` | 其他属性定位 |
| `:hover` `::before` `:not()` `:nth-child()` | `$:hover`、`tr:not(:first-child)` | 伪类/伪元素/否定/位置 |

## 关键限制
- `/* ... */` 注释会被系统过滤；注释中的示例不参与校验，字符串中的 `/*` 则不是注释。
- **不支持 at-rules**:`@keyframes` / `@media` / `@import` 等,使用可能报错。
- 作用域只影响子孙元素;body 下的弹窗/下拉框不受影响。
- `$` 与后代之间必须有空格(`$ .class` 对,`$.class` 错)。
- 不用编译产物 hash 类名(如 `.uGTwvQaG`),升级后失效。

## 选择器针对性原则
1. 优先属性选择器:`[data-code]` > `[data-key]` > `.class`。
2. 表格字段必须 `data-code`,禁裸 `td` 或纯 `:nth-child()`。
3. 用 `>` 限定层级缩小范围。
4. 组合多条件精确定位:`$ > div [data-code="x"] .kd-cq-field-value-wrap`。
5. `:not()` 排除(如表头 `tr:not(:first-child)`)。

## 常见场景
| 需求 | 写法 |
|---|---|
| 隐藏字段 | `$ > div table td[data-code="kded_xxx"] { display:none; }` |
| 字段背景色 | `$ > div [data-code="kded_amount"] { background:#fff3cd; }` |
| 表头背景 | `$ .kd-table-header-cell { background:#722; color:#fff; }` |
| 行悬停 | `$ > div table tbody tr:hover td { background:#e6f7ff; }` |
| 主题色 | `$ { background:'themeColor'; color:#fff; }` |

## 样式未生效排查
先检查控件上是否生成 `data-custom-style` 属性及对应规则；仅有页面级 `data-page-id` 不能证明样式已加载。未生成时核对元数据保存与该控件对自定义样式的支持，再查选择器层级、CSS 语法与权重、body 下挂载的弹层。可折叠容器的 `$` 仍指向内部容器，新增外层不在该选择器范围内。`!important` 仅兜底,不推荐。

## 表单布局冲突与验收

- 先核对元数据 `FullLine`、宽高、父容器和现有页面脚本，再选择承担布局的一层。原生整行控件与强制两列 grid 混用可能溢出；不要只改控件类型掩盖布局冲突。
- 调整 flex/grid 后按真实容器宽度检查“子项宽度 + gap + padding/border”，两个 50% 子项再加横向 gap 可能挤成单列。根据实测尺寸修正，不把某次像素值写成通用模板。
- 多行文本优先保留平台自动高度；短内容不占固定大块空白，换行后能增长。验收同时覆盖相邻普通字段、整页上下段、滚动区域及底部按钮，不只截改动的两个控件。
- 元数据包携带脚本时核对源码和实际加载的编译内容；两者生成与更新遵守平台格式。只改源码、实际仍加载旧编译产物时不能声称已生效。
