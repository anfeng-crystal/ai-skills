# KDApi 运行合同

## 候选经典 profile

内置模板根据候选资料重建：运行包根直接包含 `index.js`，其余 HTML、CSS、图片或本地库按相对路径组织；入口使用 IIFE 接收 `window.KDApi`，最后用 `KDApi.register(controlId, Constructor)` 注册。公开匿名渠道尚未取得官方自定义控件专题正文，因此这些是待目标版本验证的 profile，不是跨版本官方契约。

必须保持这些不变量：

- 配置 `controlId`、平台 `schemeId`、`KDApi.register` 第一个参数三者完全一致。
- `init(props)` 只初始化一次可重建资源；`update(props)` 接收平台下发的数据并刷新已有实例。
- 清理必须幂等。历史资料同时出现 `destoryed` 与 `destroyed`；经典模板将二者都委托到同一个 `_dispose`。目标版本官方脚手架有明确单一入口时可按证据收窄。
- `KDApi.loadFile` 和 `KDApi.getTemplateStringByFilePath` 使用相对路径；每个字面量资源必须存在于运行包。
- DOM、事件和样式限定在 `model.dom` 对应控件根；禁止依赖页面全局唯一 ID 或编译产物 hash 类名。

## 三条通信链

| 方向 | 前端控件 | 对端 | 验证点 |
|---|---|---|---|
| 页面脚本 → 控件 | `handleDirective(customProps, methodName, arg)` | 页面 `this.$(id).invoke(method, arg)` | 方法名、参数 schema、未知方法行为 |
| 控件 → 页面脚本 | `model.triggerCustomMsgEvent(type, payload)` | 页面 `onCustomMsgEvent(cb)` | `type` 和 payload，不混用候选资料中冲突的嵌套结构 |
| 控件 → 服务端 | `model.invoke(eventName, payload)` | 表单插件 `customEvent` | 控件 key、事件名、错误和重试语义 |
| 服务端 → 控件 | 控件 `update(props)` | `CustomControl.setData(data)` | `props.data` schema、空值、重复更新 |

上述消息 API 和结构均须由目标版本模板或运行探针确认。平台预置的 `__init__` 页面消息是否自动发送属于版本合同；不要在控件里重复伪造。真实页面联调时记录收到的原始脱敏结构，再固定目标版本测试。

## 已证实的服务端版本合同

Cosmic V8.0.1 SDK 可证实 `IFormView.addCustomControls`、`loadCustomControlMetas`、`onGetControl` 和 `CustomEventArgs.getKey/getEventName/getEventArgs` 的服务端链路；这不能反推前端工程或 ZIP 格式。使用 `kingdee-sdk-helper` 对目标项目 JAR 重查签名，不写死 `CustomControl` import。

## 数据合同

- 为每个方法/事件保存最小 JSON 样例：名称、方向、必填字段、类型、空值、最大量级、错误结果。
- 不直接信任服务端或页面消息；解析失败应显示可诊断的非敏感状态，不执行任意 HTML/脚本。
- 频繁 `update`、重复初始化和销毁后迟到 Promise 必须安全；异步回调先检查实例是否已释放。
- 第三方库只能进入已审查许可证、版本、完整性和目标 CSP 的本地资源；默认模板不带 jQuery、Vue、React 或 CDN。

## 版本证据

`cosmic-control.json.platformEvidence` 记录目标版本和证据来源。证据优先级：目标环境官方脚手架/SDK → 当前官方文档 → 可复现目标环境探针 → 社区示例。社区示例只能形成待验证假设，不能覆盖当前官方模板。

版本不明时允许生成候选工程和本地 release，但交付 manifest 必须保持 `runtimeVerification.status = "not-run"`，不得写成目标环境通过。
