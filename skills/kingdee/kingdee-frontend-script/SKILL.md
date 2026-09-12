---
name: kingdee-frontend-script
description: "Kingdee Cosmic frontend page script (browser JS): lifecycle/field/button/table/tree events, control APIs, server communication, PC/mobile extension JS, custom CSS and deterministic lifecycle/style validation. Use for 金蝶云苍穹前端页面脚本、扩展 JS(index.js/index_m.js)、控件事件绑定、字段联动、表格/树渲染、前后端通信、自定义样式与静态校验;独立 KDApi 自定义控件工程转 kingdee-custom-control。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.1.0"
  tags: "kingdee, cosmic, frontend, page-script, javascript, css"
---

# Kingdee Frontend Script
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 触发与路由
- **适用**:苍穹前端页面脚本(didMount/事件绑定/字段联动)、扩展 JS(`index.js` / `index_m.js`,PC+移动端)、表格/树自定义渲染、前后端通信(fetchData/customEvent)、自定义控件通信、自定义 CSS 样式。
- **不适用(转交)**:
  - 苍穹 Java 插件/报表/操作/BOTP → `kingdee-cosmic` / `kingdee-report`。
  - KingScript 服务端脚本插件(TS,`@cosmic/*`)→ `kingdee-kingscript`。
  - 独立 KDApi 自定义控件的生命周期、工程、测试、构建和交付 → `kingdee-custom-control`；本 skill 只保留页面侧通信。
  - 字段/控件标识证据 → `kingdee-metadata-analyzer`。
- 用户只说“脚本”时，先用当前会话、所附文件、路径、导入和生命周期入口判断脚本体系；证据明确则直接路由。只有仍存在会改变实现结果的多种解释时才询问一次，并继续不依赖该选择的只读检查。

## 模式与契约

| 模式 | 动作边界 |
|---|---|
| `author` | 本地生成、修改、解释和静态校验，不操作真实页面 |
| `verify-readonly` | 在目标、页面、账号权限、数据范围和只读动作已知时验证加载、DOM、网络响应或展示；生产只读契约完整后可直接执行 |
| `execute-approved` | 只执行已批准的页面、操作、数据范围和预期副作用；契约完整后不重复确认，不点击契约外按钮或扩展数据范围 |

缺少目标环境、真实动作性质、范围或授权时，停在 `author`。Cookie、token、session、账号、密码、租户地址、数据中心、内部 URL 和业务敏感字段值不得写入脚本、样式、日志或输出。

## 快速工作流
命令中的 Python/Node 启动器取当前已核实的运行时，Windows、macOS、Linux 均优先按进程参数数组调用；示例 shell 语法不是必需执行环境。浏览器操作使用当前宿主可用且符合合同的能力，不绑定某个 Agent 工具名。

生成或修改平台接口代码前，先沿用任务已确认的产品版本，从当前项目依赖、页面脚本声明、目标 SDK/模板或注明目标适用版本的官方资料核对本次使用的接口。用户未指定版本时，先自主读取相关项目与非敏感版本配置；仍缺影响实现的关键信息才询问。若用户指定版本与依赖/页面证据冲突，先报告冲突，不自行提高目标版本。

只知道 `7.0` 不等于已安装 `7.0.4` 等补丁，也不能因最新文档或内置 helper/示例采用 `8.0` API。已有目标声明能确认本次 API 时可继续，无需为补齐补丁号或逐个 API 重复确认；仅暂停依赖未确认接口的实现，继续独立逻辑、样式、取证和已有授权内的检查。本规则随任务目标版本变化，不把所有工程固定为 7.0。

1. 判定任务:页面脚本事件/联动、扩展 JS(PC/移动)、表格或树自定义渲染、前后端通信、自定义样式。
2. 读最小参考:
   - 事件与控件 API:`references/events-and-api.md`
   - 前后端通信 / PC·移动端扩展入口:`references/server-and-extend.md`
   - 高级模式与调试(React Hooks/iframe/不生效排查):`references/advanced-debugging.md`
   - 自定义 CSS 选择器与限制:`references/custom-style.md`
   - 生命周期/样式确定性校验:`references/validation-contract.md`
3. 控件标识、字段 key 不能猜:用设计器或 `kingdee-metadata-analyzer` 确认。
4. 表格/树操作前必须等待 `onInit()` Promise;嵌套回调用箭头函数保 `this`;`didMount` 注册的监听在 `willUnmount` 配对清理。
5. 产出前运行 `python3 scripts/validate_frontend.py <file-or-directory>`；控件标识、事件时机和 PC/移动端入口仍需目标版本证据。

## References
- 事件体系与 7 类控件 API:`references/events-and-api.md`
- 前后端通信与 PC/移动端扩展:`references/server-and-extend.md`
- 高级模式与调试:`references/advanced-debugging.md`
- 自定义 CSS:`references/custom-style.md`
- 生命周期与样式校验:`references/validation-contract.md`

## Guardrails
- 本 skill 的页面脚本 API 与设计器自定义 CSS 限制尚未取得注明适用版本的官方正文复核，属于待目标版本核验的参考；下列“不支持”不能推广到服务端插件、KDApi 控件资源 CSS 或所有苍穹版本。沿现有规则处理常规任务，遇到目标官方声明或可复现证据冲突时记录差异并以目标合同为准，不凭这些未核验条目直接宣称平台无法实现。
- 锁定性、可见性、必录、标识、类型不支持脚本修改;`set` 可能被服务端优先级覆盖,不要假设一定生效。
- 基础资料字段 `setValue` 无效(需服务端赋值);`getValue()` 基础资料返回不可变对象,取值用 `.toJS()`。
- 表格/树操作前等待 `onInit()`,否则竞速取空。
- `didMount` 注册的 DOM 事件 / 定时器 / 全局监听,必须在 `willUnmount` 解绑清理,引用用 `export var` 保存以便配对移除。
- iframe/postMessage 必须做 `event.origin` 白名单校验。
- 自定义样式:`$` 代表当前控件 className(不可自定义),`$` 后接后代选择器必须留空格;主题色 `'themeColor'` 必须单引号;**不支持 `@keyframes`/`@media`/`@import` 等 at-rules**;只作用子孙元素(body 下弹窗/下拉不受影响);表格字段定位必须用 `[data-code="..."]`,禁用编译产物 hash 类名。
- 元素选取用浏览器 F12(Elements 选中目标)跨平台完成;不依赖 `Start-Process` 或任何单平台本地工具页。
- 不在脚本/样式/输出中写真实地址、账号、密码、Cookie、token 或内部 URL。
- helper/内置模板提供候选写法；校验器通过只代表确定性规则未命中，不证明平台接口在目标版本存在或目标页面运行通过。

## Output
使用简体中文:结论 → 模式/契约 → 入口与事件依据 → 代码或样式 → 控件标识依据(已确认/未确认) → 静态校验 → 页面验证状态与清理点。
