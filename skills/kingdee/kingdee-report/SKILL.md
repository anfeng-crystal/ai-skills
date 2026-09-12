---
name: kingdee-report
description: "Kingdee Cosmic report development: AbstractReportListDataPlugin data plugins, Algo/DataSet pipelines, precise Algo API signatures, report architecture patterns. Use for 金蝶云苍穹报表插件开发、报表取数、DataSet/Algo 流水线、GroupbyDataSet 聚合、FilterInfo 解析、报表架构选型与 Algo API 精确签名;实体或关键字段未确认时先取证、暂停依赖它们的取数代码生成，不生成占位代码，字段证据交 kingdee-metadata-analyzer,SDK 签名交 kingdee-sdk-helper。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.0.0"
  tags: "kingdee, cosmic, report, algo, dataset, plugin"
---

# Kingdee Report
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

本 skill 承载报表取数与 Algo 流水线，通用 Java 二开走 `kingdee-cosmic`。references 是 API 与写法候选；生成或修改平台相关代码前，先复用用户已确认的产品与目标版本，再用目标项目依赖、匹配目标实际版本的 SDK/Javadoc 或声明确认本次具体 API，不等到资料冲突才核对。

只确认到 `7.0` 时保留该粒度，不补成 `7.0.13`，不因 `8.0` 资料较新而提升目标；用户指定其他版本时按该目标处理。同大版本不同补丁也需核对具体 API，补丁未知但目标 JAR/声明足以确认本次 API 时可继续。目标与实际依赖冲突时如实报告，不以另一版本的编译结果冒充目标兼容。

## 触发边界
- **适用**:苍穹报表插件(`AbstractReportListDataPlugin` / `AbstractReportFormPlugin`)开发、报表取数、DataSet/Algo 流水线、JOIN/分组聚合、FilterInfo 解析、报表架构选型、Algo API 精确签名查询。
- 按用户指定语言、已有工程和目标版本证据选择实现形态。官方支持 KingScript 报表查询/表单插件；用户选择 KingScript 时与 `kingdee-kingscript` 协作核对声明、导入及注册，不强制改为 Java，也不要求先有同类实现。未指定语言时沿用项目惯例；官方指南未声明最低版本，不能据此推断所有旧环境支持。见 `../kingdee-kingscript/references/official-report-support.md`。
- **不适用(转交)**:
  - 普通表单/单据/列表/操作插件、BOTP、工作流 → `kingdee-cosmic`。
  - 字段/实体/挂载点证据 → `kingdee-metadata-analyzer`(先取证再写取数)。
  - SDK 类定义/方法归属/Javadoc → `kingdee-sdk-helper`。
  - 非报表 KingScript / ISCB 脚本 → `kingdee-kingscript` / ISCB 专用 skill；KingScript 报表保留本 skill 的取数合同并协作处理脚本形态。
  - 报表单测与 Gradle 运行 → `kingdee-testing`。

## 核心心智模型
报表 = 单一 `query()` 入口 + 只读查询 + 无状态设计 + BigDecimal 财务计算 + DataSet 单次消费。详见 `references/mental-model.md`。

## 快速工作流
1. 先区分 API 查询、架构分析和取数实现。API 查询与不依赖具体字段的分析无需完整报表合同。具体取数实现须确认报表标识、数据源实体、过滤项、输出列、计算口径、关联与分组；实体或 query/group/sum 关键字段未确认时，先复用项目、缓存和已授权的 `kingdee-metadata-analyzer` 证据，只暂停依赖缺失事实的代码生成，继续独立取证与检查。取证后仍无法确认时，报告 `contract_incomplete` 和最小缺失项；需要用户提供业务信息时再询问。只有用户明确要求架构伪代码时才提供伪代码，且不得写未核实 SDK 签名。
2. 选架构模式(`references/architecture-patterns.md`):默认 Algo Pipeline(90%);复杂逐行转换用 Map-Based Assembly;成本卷算用 AlgoX。
3. 写取数:解析 `FilterInfo` → 构建 `QFilter[]` → 各数据源 `queryDataSet` → JOIN/UNION → `groupBy().sum().finish()` → `addField()` 计算列 → 返回 DataSet。`references/algo-api.md` 用于定位候选；使用各 API 前先核对目标版本签名，不凭记忆或未标版本的表格生成。
4. 按 `references/codegen-checklist.md` 自检:无实例字段、BigDecimal 计算、AlgoKey 唯一、空值安全、NULL 用 `IS NULL`。
5. Java 编译/运行验证交 `kingdee-testing`；KingScript 按目标声明及 `kingdee-kingscript` 的授权边界验证，不把 Java Gradle 编译套到 TS 文件。字段口径回 `kingdee-metadata-analyzer` 复核。

## References
- 核心心智模型:`references/mental-model.md`
- 报表架构模式(Pipeline / Map-Based / AlgoX):`references/architecture-patterns.md`
- Algo API 精确签名集:`references/algo-api.md`
- 代码生成规范与验证清单:`references/codegen-checklist.md`

## 契约与门禁
- 报表是纯只读查询:禁用 `SaveServiceHelper` / `OperationServiceHelper` / 直接写库。
- 数据源实体编码或用于 query/group/sum 的关键字段 key 未确认时，先自主取证，只暂停依赖它们的取数代码；不得生成带占位字段或未核实 SDK 签名的可粘贴插件模板。用户明确要求的架构伪代码不得冒充可运行实现。
- 无状态:禁用实例字段缓存数据,所有数据走局部变量与方法参数;唯一例外 `private static final` 常量。
- 财务计算必须 BigDecimal,比较用 `compareTo()`,禁 `double`/`float`/`==`。
- DataSet 单次消费:遍历后需复用先 `.copy()`;AlgoKey 用 `getClass().getName()+"_suffix"` 保唯一。
- 字段 key、实体编码、refType 用目标元数据确认；SDK 方法签名用目标项目依赖或匹配目标实际版本的 SDK/Javadoc/声明确认，`kingdee-sdk-helper` 与本 skill references 仅在其来源匹配时提供目标依据。
- 不在输出/示例中写真实数据库 IP、账号、密码、租户、数据中心、内部 URL、DB schema、连接串或业务敏感字段样例值;示例一律用占位符。
- 复用已有有效版本与签名证据，不固定追加人工确认、下载、登录或编译步骤。新版本或版本不明的 Algo 签名仍是候选；未知签名只暂停依赖它的代码，继续独立取证、分析和本地检查，验证仍按原任务范围执行。

## Output
使用简体中文:结论 → 架构选型依据 → 取数代码 → 字段/口径依据(已确认/未确认)→ 验证与风险。
- `contract_incomplete`：列出缺少的实体、字段、口径、已查证据和受阻的取数步骤，不包含依赖缺失事实的取数代码或占位插件模板；已完成的独立 API 查询、分析与验证分别报告。
