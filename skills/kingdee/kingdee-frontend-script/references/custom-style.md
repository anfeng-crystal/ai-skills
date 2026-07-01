# 自定义 CSS 样式

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
- `/** */` 注释会被系统过滤(可写说明,不影响功能)。
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
确认外层有 `data-page-id` 父元素 → 选择器路径(空格/层级)正确 → 权重足够(被覆盖则加层级)→ F12 看语法报错 → 元素不在 body 下 → 未用 at-rules。`!important` 仅兜底,不推荐。
