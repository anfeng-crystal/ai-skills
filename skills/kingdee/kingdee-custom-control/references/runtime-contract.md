# KDApi 运行合同

## 候选经典 profile

内置模板是本 skill 的经典候选工程：运行包根直接包含 `index.js`，其余 HTML、CSS、图片或本地库按相对路径组织；入口使用 IIFE 接收 `window.KDApi`，最后用 `KDApi.register(controlId, Constructor)` 注册。官方 API 和进阶指南已证实注册、相对资源加载、经典生命周期与前后端通信；完整工程、ZIP 布局和所有消息结构仍须目标版本验证，不能把局部 API 证据当成整包实测。

必须保持这些不变量：

- 配置 `controlId`、平台 `schemeId`、`KDApi.register` 第一个参数三者完全一致。
- `init(props)` 初始化可重建资源；经典 profile 的 `update(props)` 接收平台下发的数据并刷新已有实例。新版生命周期按下节选择，不加空 `update` 满足旧规则。
- 清理必须幂等。官方 KDApi API 篇将 `destoryed` 列为 V4.0+ 的卸载入口；进阶篇的 Vue `destroyed` 属于 Vue 实例，不能与外层 KDApi `destoryed` 混为同一平台事件。经典模板保留的双入口是兼容别名策略，非平台必需；只用 `destroyed` 仍需目标证据。
- `KDApi.loadFile` 和 `KDApi.getTemplateStringByFilePath` 使用相对路径；每个字面量资源必须存在于运行包。
- DOM、事件和样式限定在 `model.dom` 对应控件根；禁止依赖页面全局唯一 ID 或编译产物 hash 类名。

## V7.0.4+ 新版生命周期

官方 API 篇明确：V7.0.4+ 继续兼容旧生命周期，也支持 `onPropsUpdate`、`onThemeUpdate`、`onDataUpdate`、`onLockUpdate`、`onCardRowDataUpdate`、`onGridRowDataUpdate`。新钩子不能与旧 `update` 同时使用；`onPropsUpdate` 不再在初始化后额外触发一次更新。迁移专项钩子时移除原通用更新中对应的重复处理。

默认 `init` 命令仍生成 `classic-kdapi-candidate-v1`。已有现代工程显式设置 `runtimeContract: "modern-kdapi-v7.0.4"`，并在 `platformEvidence.version` 填已核实的实际目标版本，不填 `latest`，也不复制本页示例版本。只知道 `7.0` 不能据此确认 `7.0.4+`；已有目标声明可证实具体接口时，其相关实现可继续，但显式 modern profile 仍需已核实 `7.0.4+`，不能为通过工具而伪填补丁号。校验器要求 `init`、至少一个实际使用的新更新钩子和销毁清理；拒绝新旧混用、未声明现代 profile 及低于 7.0.4/无法判定的版本。它只检查结构，不证明版本兼容或目标页面已运行通过；modern 条件缺失不阻断经典候选工程及其本地 release。`candidate` 本地 release 仍标运行 `not-run`，声称 `verified` 时仍需 `source` 和 `verifiedAt`。

## 三条通信链

| 方向 | 前端控件 | 对端 | 验证点 |
|---|---|---|---|
| 页面脚本 → 控件 | `handleDirective(customProps, methodName, arg)` | 页面 `this.$(id).invoke(method, arg)` | 方法名、参数 schema、未知方法行为 |
| 控件 → 页面脚本 | `model.triggerCustomMsgEvent(type, payload)` | 页面 `onCustomMsgEvent(cb)` | `type` 和 payload，不混用候选资料中冲突的嵌套结构 |
| 控件 → 服务端 | `model.invoke(eventName, payload)` | 表单插件 `customEvent` | 控件 key、事件名、错误和重试语义 |
| 服务端 → 控件 | 经典 `update(props)` 或已验证版本的新更新钩子 | `CustomControl.setData(data)` | `props.data` schema、空值、重复更新 |

上述消息 API 和结构均须由目标版本模板或运行探针确认。平台预置的 `__init__` 页面消息是否自动发送属于版本合同；不要在控件里重复伪造。真实页面联调时记录收到的原始脱敏结构，再固定目标版本测试。

官方进阶篇明确 `getControl` 接收页面控件 `key`，不是方案 `schemaId`；`KDApi.register` 接收方案 ID。配置文件现有字段名为 `schemeId`，对应官方 `schemaId`，不要因此重命名既有配置 schema。

## 已证实的服务端版本合同

Cosmic V8.0.1 SDK 可证实 `IFormView.addCustomControls`、`loadCustomControlMetas`、`onGetControl` 和 `CustomEventArgs.getKey/getEventName/getEventArgs` 的服务端链路；该证据仅确认所查 SDK，不证明这些接口在 7.0 项目中的存在、签名或行为，也不能反推前端工程或 ZIP 格式。生成/修改调用前使用 `kingdee-sdk-helper` 对实际目标项目依赖/JAR 或同目标版本官方资料重查；已有目标证据可复用，不写死 `CustomControl` import，不自动升级项目依赖。

## 数据合同

- 为每个方法/事件保存最小 JSON 样例：名称、方向、必填字段、类型、空值、最大量级、错误结果。
- 不直接信任服务端或页面消息；解析失败应显示可诊断的非敏感状态，不执行任意 HTML/脚本。
- 频繁 `update`、重复初始化和销毁后迟到 Promise 必须安全；异步回调先检查实例是否已释放。
- 第三方库只能进入已审查许可证、版本、完整性和目标 CSP 的本地资源；默认模板不带 jQuery、Vue、React 或 CDN。

## 版本证据

`cosmic-control.json.platformEvidence` 记录实际目标版本和证据来源。先结合任务声明核对当前项目依赖、目标环境官方脚手架/SDK 或声明，再用注明该目标适用版本的官方文档及已有目标运行证据补齐。最新官方文档与内置模板只提供候选线索，不能覆盖已确认目标；存在版本冲突先报告，不自行提升目标或仅按发布时间选新版本。社区示例不能单独证明兼容。

版本不明时仍允许生成候选工程和候选本地 release，沿 helper 已有候选合同如实记录未知版本，保持 `platformInstall` / `runtimeVerification` 为 `not-run`（有明确阻塞则为 `blocked`）。这不代表目标版本可部署、接口兼容或目标环境通过，也不允许伪填版本选择 modern profile。只暂停依赖未知接口的目标实现或平台验证，继续候选产物与其他独立工作。

## 官方来源

- [自定义控件开发API篇](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=249447947539332864&id=236186162019022848&type=Knowledge&productLineId=29&lang=zh-CN)，更新于 2025-09-03 18:18。基础 API/经典生命周期标 V4.0+；新版生命周期标 V7.0.4+。短证据：“旧版本update无法与新生命周期同时使用”。另有 `getLangObj` V7.0.2+、`getThemeObj` V7.0.3+ 和暗黑/移动设备/RTL props V8.0.1，按需查询，不向旧版补这些属性。
- [自定义控件开发进阶篇](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=249447947539332864&id=236768241354411008&type=Knowledge&productLineId=29&lang=zh-CN)，更新于 2025-01-22 15:33；变更记录含 V7.0.4 脚手架更新。正文证实 `setData → props.data` 与 `model.invoke → customEvent`，以及控件 key/方案 ID 的区别。其旧 KDE/KS 示例不能直接当成现代 TypeScript KingScript 导入和类型合同。
