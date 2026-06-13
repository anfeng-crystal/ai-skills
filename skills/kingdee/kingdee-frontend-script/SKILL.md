---
name: kingdee-frontend-script
description: "Kingdee Cosmic frontend page script (browser JS): lifecycle/field/button/table/tree events, control APIs, server communication, PC/mobile extension JS, custom CSS. Use for 金蝶云苍穹前端页面脚本、扩展 JS(index.js/index_m.js)、控件事件绑定、字段联动、表格/树自定义渲染、前后端通信、自定义样式;不用于 Java 二开(kingdee-cosmic)或 KingScript 服务端脚本(kingdee-kingscript)。"
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [kingdee, cosmic, frontend, page-script, javascript, css]
---

# Kingdee Frontend Script
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

苍穹**浏览器端**页面脚本 / 扩展 JS / 自定义样式开发。运行在前端页面,不是 Java 二开,也不是 KingScript 服务端脚本。

## 触发边界
- **适用**:苍穹前端页面脚本(didMount/事件绑定/字段联动)、扩展 JS(`index.js` / `index_m.js`,PC+移动端)、表格/树自定义渲染、前后端通信(fetchData/customEvent)、自定义控件通信、自定义 CSS 样式。
- **不适用(转交)**:
  - 苍穹 Java 插件/报表/操作/BOTP → `kingdee-cosmic` / `kingdee-report`。
  - KingScript 服务端脚本插件(TS,`@cosmic/*`)→ `kingdee-kingscript`。
  - 字段/控件标识证据 → `kingdee-metadata-analyzer`。
- 仅说"脚本"未点明前端页面脚本时,先澄清是前端页面脚本、KingScript 还是 Java 插件,不默认接管。

## 快速工作流
1. 判定任务:页面脚本事件/联动、扩展 JS(PC/移动)、表格或树自定义渲染、前后端通信、自定义样式。
2. 读最小参考:
   - 事件与控件 API:`references/events-and-api.md`
   - 前后端通信 / PC·移动端扩展入口:`references/server-and-extend.md`
   - 高级模式与调试(React Hooks/iframe/不生效排查):`references/advanced-debugging.md`
   - 自定义 CSS 选择器与限制:`references/custom-style.md`
3. 控件标识、字段 key 不能猜:用设计器或 `kingdee-metadata-analyzer` 确认。
4. 表格/树操作前必须等待 `onInit()` Promise;嵌套回调用箭头函数保 `this`;`didMount` 注册的监听在 `willUnmount` 配对清理。
5. 产出前自检:控件标识一致、事件触发时机正确、资源清理到位、样式选择器精准且无 at-rules。

## References
- 事件体系与 7 类控件 API:`references/events-and-api.md`
- 前后端通信与 PC/移动端扩展:`references/server-and-extend.md`
- 高级模式与调试:`references/advanced-debugging.md`
- 自定义 CSS:`references/custom-style.md`

## Guardrails
- 锁定性、可见性、必录、标识、类型不支持脚本修改;`set` 可能被服务端优先级覆盖,不要假设一定生效。
- 基础资料字段 `setValue` 无效(需服务端赋值);`getValue()` 基础资料返回不可变对象,取值用 `.toJS()`。
- 表格/树操作前等待 `onInit()`,否则竞速取空。
- `didMount` 注册的 DOM 事件 / 定时器 / 全局监听,必须在 `willUnmount` 解绑清理,引用用 `export var` 保存以便配对移除。
- iframe/postMessage 必须做 `event.origin` 白名单校验。
- 自定义样式:`$` 代表当前控件 className(不可自定义),`$` 后接后代选择器必须留空格;主题色 `'themeColor'` 必须单引号;**不支持 `@keyframes`/`@media`/`@import` 等 at-rules**;只作用子孙元素(body 下弹窗/下拉不受影响);表格字段定位必须用 `[data-code="..."]`,禁用编译产物 hash 类名。
- 元素选取用浏览器 F12(Elements 选中目标)跨平台完成;不依赖 `Start-Process` 或任何单平台本地工具页。
- 不在脚本/样式/输出中写真实地址、账号、密码。

## Output
使用简体中文:结论 → 入口/事件依据 → 代码或样式 → 控件标识依据(已确认/未确认)→ 验证与清理点。
