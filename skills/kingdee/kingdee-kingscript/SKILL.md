---
name: kingdee-kingscript
description: "编写、解释或修复 KingScript 服务端脚本插件，查询脚本 SDK 声明；ISCB 与浏览器页面脚本使用各自专用 skill。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.0.0"
  tags: "kingdee, KingScript, script, plugin, SDK"
---

# Kingdee KingScript
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 触发边界
- 用户明确涉及 KingScript/Kingscript、苍穹脚本插件、脚本 SDK 声明、脚本运行错误或风险审查时使用。
- 普通苍穹 Java 插件开发不使用；改用 `kingdee-cosmic`。
- KingScript 报表查询/表单插件由本 skill 处理脚本语法、导入和注册形态，同时使用 `kingdee-report` 核对取数、字段与 Algo 合同。官方已有 TS 继承 `AbstractReportListDataPlugin` 的开发指南，不因出现该基类或 DataSet 就强制转 Java；目标版本仍须有匹配的声明/SDK 证据，新建实现不以已有同类插件为前提。见 `references/official-report-support.md`。
- ISCB、ISC 脚本、集成云 DSL 或数据集成方案脚本不使用；改用 `iscb-script`。
- 前端页面/扩展 `index.js`、`index_m.js` 或浏览器端页面脚本不使用；改用 `kingdee-frontend-script`。独立 KDApi 自定义控件源码、生命周期、构建和交付改用 `kingdee-custom-control`。
- 用户只说“脚本”时，先用当前会话、所附文件、路径、导入和生命周期入口判断脚本体系；证据明确则直接路由。只有仍存在会改变实现结果的多种解释时才询问一次，并继续不依赖该选择的只读检查。

## 实现与证据

- 按用户请求完成生成、修改、SDK 解释、运行错误排查或风险审查；先复用项目已有脚本、公共函数、wrapper 和同类实现。已有实现与目标签名足够时，不为局部修改另读模板或完整索引链。
- 沿用已确认的产品与目标版本。`7.0` 不等于某个补丁，也不能被 `8.0` 示例/声明提升；用户指定其他版本时按该目标处理。
- 生成或修改平台相关脚本前，用目标项目依赖、匹配目标实际版本的 `.d.ts`/SDK/JAR/Javadoc 确认本次 API、导入、归属和事件签名。references 只定位候选；同大版本另一补丁也不自动兼容。补丁未知但目标声明足以确认本次 API 时可继续；目标与实际依赖冲突时报告，不以另一版本检查通过冒充目标兼容。
- 交付前核对受影响的事件/参数类型、字段标识、异常与空值边界及复用选择；完成已授权本地修改和适用验证，真实动作按下方契约执行。

## 按需资料路由

已知具体卡片或目标声明时直接读取；只有位置不明才走索引。目录名、索引命中和示例标题均不是签名证据，须收敛到具体内容。

| 当前需要 | 资料入口 |
|---|---|
| 不确定资料位置或任务类别 | `references/index.md` |
| 新建脚本结构、插件模板 | `references/templates/index.md`，选择对应模板；需要事件写法时再读其关联示例 |
| 插件或场景示例 | `references/examples/index.md` 或 `references/examples/plugins/index.md`，按类型/事件/场景进入具体文件 |
| SDK 来源和版本判定 | `references/sdk/strategy.md`；需要总体组织说明时读 `references/sdk/index.md` |
| 已知类名或方法名 | `references/sdk/indexes/class-index.md`、`method-index.md` 或 `methods-by-name.md` 中匹配的一项 |
| 生命周期或插件类型 | `references/sdk/indexes/methods-lifecycle.md`、`plugin-index.md` |
| 场景、关键词或错误 | `references/sdk/indexes/scenario-index.md`、`keyword-index.md` 或 `error-index.md`；参数不匹配、`any`、确认框/关闭回调优先用错误索引 |
| 语法、关键字、模块或异常处理 | `references/language/kingscript/index.md`，再读对应主题（如类、方法、变量、接口、异常处理或语法示例） |

SDK 索引定位后读取对应 `classes/`、`packages/`、`plugins/` 或 `microservices/` 卡片。未命中时在本 skill 的 `references/` 检索；仍不足时用 `references/sdk/manifests/index.md` 与相关 JSON 清单，或目标声明/官方资料补证。无需按顺序穷尽已无帮助的资料，未知签名仍不得猜。

## References
- 总入口：`references/index.md`
- 插件基类×事件 / SDK 导入速查：`references/plugin-event-cheatsheet.md`（入口速查；卡片用于定位，签名须由匹配目标版本的声明/SDK 确认）
- SDK 查询：`references/sdk/index.md`、`references/sdk/strategy.md`
- SDK 索引：`references/sdk/indexes/class-index.md`、`references/sdk/indexes/method-index.md`、`references/sdk/indexes/methods-by-name.md`、`references/sdk/indexes/methods-lifecycle.md`、`references/sdk/indexes/plugin-index.md`、`references/sdk/indexes/scenario-index.md`、`references/sdk/indexes/keyword-index.md`
- SDK 清单：`references/sdk/manifests/index.md`
- 模板：`references/templates/index.md`
- 示例：`references/examples/index.md`、`references/examples/plugins/index.md`
- 语法：`references/language/kingscript/index.md`
- 注释规范：`references/comment-policy.md`
- 官方报表支持与版本边界：`references/official-report-support.md`

## 代码注释策略
- 生成或修改 KingScript 时，脚本模块、类、工具函数、公共函数、复杂函数和关键业务分支必须写功能性注释。
- 文件或模块注释说明用途、入口事件、SDK/声明前提、外部副作用和平台约束。
- 函数注释说明参数来源、返回语义、空值/权限/异常边界，以及调用方需要保证的前置条件。
- 简单 getter、简单透传、纯字段拼装不强行写长注释；禁止把排查路径、修改经过或交付口径写进脚本。

## 契约与门禁
- 用户要求生成或修改脚本时，完成已授权的本地源码修改、静态检查和不调用真实业务的本地验证；只要求解释、建议或风险审查时不修改文件。默认不部署脚本、不注册插件、不登录真实环境、不执行真实业务动作。
- 仅阅读或修改包含 `BusinessDataServiceHelper`、操作插件、保存、提交、删除、反审核、调度任务、消息发送或 HTTP 出站 API 的源码，不触发真实执行审批。准备实际执行这些动作前，核对环境、权限、数据范围、幂等性、回滚方案和测试路径；生产环境默认只读分析。
- 真实运行、接口调用或环境验证必须有用户明确的目标环境和授权边界；复用当前会话已有授权，不要求重复确认。缺少真实执行授权时，只暂停相关真实动作，继续已授权的本地修改、静态检查和独立验证。
- Cookie、token、session、账号、密码、租户、数据中心、内部 URL、连接串和业务敏感字段值必须脱敏,不写入脚本、注释、输出或日志。
- 不凭示例猜 API；调用对象方法前必须确认方法属于当前类型或声明继承链。
- 事件参数不得写成 `any`；声明只给出通用类型时按声明原样使用。
- 页面提示、确认框、通知、关闭回调等视图能力，必须回到 `IFormView`、`FormView`、`ListView`、`ReportView` 或对应声明卡片确认，不把别处示例里的方法直接套到当前 view 对象。
- `showConfirm` / `confirmCallBack` / `messageBoxClosed` 使用 `MessageBoxClosedEvent`；子页面关闭回调再看 `ClosedCallBackEvent` 或 `BillClosedCallBackEvent`，不能混用。
- 生成或修改事件方法时，必须核对事件参数类型是否与当前插件基类、生命周期和示例上下文一致；同名事件在不同插件体系下不能混用参数签名。
- 生成脚本前先确认 import、对象归属和声明入口；拿不准时先回 `references/sdk/indexes/` 和具体类卡，不凭印象补全 API。
- `references/` 的发现顺序不代表版本权威；新版或版本不明的卡片始终是目标 API 候选，复用已有有效目标证据，不固定追加人工确认、下载、登录或编译步骤。只暂停依赖未确认签名的实现，继续独立本地检查；实际运行与写入仍遵守原授权。
- 新增脚本模块、类、工具函数和复杂函数必须写功能性注释。
- 涉及代码、注释、文档或提交时，署名必须遵守全局规则：不用 AI，统一用 `anfeng`。
- 当前项目或工作区已有脚本模块、共享工具函数、SDK wrapper、模板或示例能覆盖需求时，不再复制一份同逻辑脚本。
- 不把实施过程、排查过程、修改经过或交付口径写入代码注释、skills、操作说明或示例说明。

## Output
使用简体中文，默认保持现有结构：依据 → 脚本/说明 → 风险检查 → 验证建议。
- 信息不完整时，在“依据”后补一段“假设/待确认”，明确哪些内容已确认、哪些只是保守推断。
- 做代码生成或修改时，“脚本/说明”部分先给复用来源与选择理由，再给最小必要代码或改动点。
- 做 SDK 解释、错误诊断或风险审查时，“风险检查”里至少覆盖 API 归属、事件参数类型、生命周期时机和空值/权限边界。
