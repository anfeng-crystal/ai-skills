---
name: kingdee-kingscript
description: "KingScript plugin: SDK declarations, runtime errors, risk review."
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [kingdee, KingScript, script, plugin, SDK]
---

# Kingdee KingScript
## 触发边界
- 用户明确涉及 KingScript、Kingscript、脚本插件、苍穹脚本开发、脚本 SDK、脚本运行错误时使用。
- 普通苍穹 Java 插件开发不使用；改用 `kingdee-cosmic`。
- ISCB、ISC 脚本、集成云 DSL 或数据集成方案脚本不使用；改用 `kingdee-iscb-script`。
- 只说“脚本”但未说明 KingScript/苍穹脚本插件上下文时，先澄清脚本体系，不默认接管。

## 快速工作流
1. 先确认任务类型：生成脚本、修改脚本、解释 SDK、排查运行错误或风险审查。
2. 先检查当前项目或工作区里是否已有同类脚本模块、公共函数、共享工具、SDK wrapper、模板或示例实现，能复用时优先复用。
3. 再读 `references/index.md`，按任务落到 `templates/`、`examples/`、`sdk/` 或 `language/` 的具体入口。
4. 遇到目录级线索时不能停在目录名；必须继续收敛到该目录下的 `index.md`、`indexes/*.md`、`manifests/index.md` 或目标 `*.md`。
5. 生成或修改脚本前读 `references/templates/index.md` 和最接近的模板，再进入对应示例或事件拆分文件确认写法。
6. 涉及 SDK 时先读 `references/sdk/index.md`、`references/sdk/strategy.md` 和 `references/sdk/indexes/`，再进入具体 `classes/`、`packages/`、`plugins/`、`microservices/` 卡片。
7. 涉及语法、关键字、模块、异常处理时先读 `references/language/kingscript/index.md`，再进入对应主题 `*.md`。
8. 需要示例时先读 `references/examples/index.md`、`references/examples/plugins/index.md`，再按插件类型、事件拆分或场景拆分进入具体示例。
9. 只有当 skill 内 `references/` 仍不足以确认 API、声明或运行边界时，才降级到当前项目 `.d.ts`、本地 jar/Javadoc 或外部文档。
10. 输出前检查事件类型、参数类型、API 归属、字段标识、异常处理、空值边界和复用决策。

## 本地资源发现与收敛
- 默认发现顺序：当前项目或工作区已有实现 → `references/index.md` → 对应子目录 `index.md` / `indexes/*.md` / 具体 `*.md`。
- 若当前任务只给出插件类型、类名、方法名、事件名、场景词或报错词，先回到 `references` 对应索引入口，再落到具体知识卡或示例，不直接凭目录名或示例标题作答。
- `examples/` 侧先看 `references/examples/index.md`、`references/examples/plugins/index.md`，再进入插件分类目录下的 `index.md` 与目标场景 `*.md`。
- `templates/` 侧先看 `references/templates/index.md`，确认模板后继续打开模板表中指向的最近示例入口。
- `sdk/` 侧优先用 `references/sdk/indexes/class-index.md`、`method-index.md`、`methods-by-name.md`、`methods-lifecycle.md`、`plugin-index.md`、`scenario-index.md`、`keyword-index.md` 收敛；索引命中后继续打开 `classes/`、`packages/`、`plugins/`、`microservices/` 的具体文件。
- 报错涉及“事件参数类型不匹配”“`any` 用错位置”“`confirmCallBack` / `messageBoxClosed` / `closedCallBack`”时，先看 `references/sdk/indexes/error-index.md` 和 `keyword-index.md`，再落到插件基类、事件参数类卡和对应示例。
- `language/` 侧先看 `references/language/kingscript/index.md`，再按主题进入 `类.md`、`方法.md`、`变量.md`、`接口.md`、`异常处理.md`、`语法示例.md` 等具体条目。
- 当 `sdk/indexes/` 仍不能定位时，再降级到 `references/sdk/manifests/index.md` 与相关 `*.json` 清单；仍不足时才继续外部兜底。
- 目录级资料不够时，优先在当前 skill 的 `references/` 内做关键字检索，再考虑 skill 外资料。

## References
- 总入口：`references/index.md`
- SDK 查询：`references/sdk/index.md`、`references/sdk/strategy.md`
- SDK 索引：`references/sdk/indexes/class-index.md`、`references/sdk/indexes/method-index.md`、`references/sdk/indexes/methods-by-name.md`、`references/sdk/indexes/methods-lifecycle.md`、`references/sdk/indexes/plugin-index.md`、`references/sdk/indexes/scenario-index.md`、`references/sdk/indexes/keyword-index.md`
- SDK 清单：`references/sdk/manifests/index.md`
- 模板：`references/templates/index.md`
- 示例：`references/examples/index.md`、`references/examples/plugins/index.md`
- 语法：`references/language/kingscript/index.md`
- 注释规范：`references/comment-policy.md`

## 代码注释策略
- 生成或修改 KingScript 时，脚本模块、类、工具函数、公共函数、复杂函数和关键业务分支必须写功能性注释。
- 文件或模块注释说明用途、入口事件、SDK/声明前提、外部副作用和平台约束。
- 函数注释说明参数来源、返回语义、空值/权限/异常边界，以及调用方需要保证的前置条件。
- 简单 getter、简单透传、纯字段拼装不强行写长注释；禁止把排查路径、修改经过或交付口径写进脚本。

## Guardrails
- 不凭示例猜 API；调用对象方法前必须确认方法属于当前类型或声明继承链。
- 事件参数不得写成 `any`；声明只给出通用类型时按声明原样使用。
- 页面提示、确认框、通知、关闭回调等视图能力，必须回到 `IFormView`、`FormView`、`ListView`、`ReportView` 或对应声明卡片确认，不把别处示例里的方法直接套到当前 view 对象。
- `showConfirm` / `confirmCallBack` / `messageBoxClosed` 使用 `MessageBoxClosedEvent`；子页面关闭回调再看 `ClosedCallBackEvent` 或 `BillClosedCallBackEvent`，不能混用。
- 生成或修改事件方法时，必须核对事件参数类型是否与当前插件基类、生命周期和示例上下文一致；同名事件在不同插件体系下不能混用参数签名。
- 生成脚本前先确认 import、对象归属和声明入口；拿不准时先回 `references/sdk/indexes/` 和具体类卡，不凭印象补全 API。
- `references/` 内资料能确认时，不降级到 skill 外资料；只有 skill 内资料不足时，才依次查看当前项目 `.d.ts`、本地 jar/Javadoc、外部文档。
- 新增脚本模块、类、工具函数和复杂函数必须写功能性注释。
- 涉及代码、注释、文档或提交时，署名必须遵守全局规则：不用 AI，统一用 `anfeng`。
- 当前项目或工作区已有脚本模块、共享工具函数、SDK wrapper、模板或示例能覆盖需求时，不再复制一份同逻辑脚本。
- 不把实施过程、排查过程、修改经过或交付口径写入代码注释、skills、操作说明或示例说明。

## Output
使用简体中文，默认保持现有结构：依据 → 脚本/说明 → 风险检查 → 验证建议。
- 信息不完整时，在“依据”后补一段“假设/待确认”，明确哪些内容已确认、哪些只是保守推断。
- 做代码生成或修改时，“脚本/说明”部分先给复用来源与选择理由，再给最小必要代码或改动点。
- 做 SDK 解释、错误诊断或风险审查时，“风险检查”里至少覆盖 API 归属、事件参数类型、生命周期时机和空值/权限边界。
