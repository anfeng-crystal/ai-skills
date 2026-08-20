---
name: kingdee-report
description: "Kingdee Cosmic report development: AbstractReportListDataPlugin data plugins, Algo/DataSet pipelines, precise Algo API signatures, report architecture patterns. Use for 金蝶云苍穹报表插件开发、报表取数、DataSet/Algo 流水线、GroupbyDataSet 聚合、FilterInfo 解析、报表架构选型与 Algo API 精确签名;实体或关键字段未确认时只列取证项、不生成占位代码，字段证据交 kingdee-metadata-analyzer,SDK 签名交 kingdee-sdk-helper。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.0.0"
  tags: "kingdee, cosmic, report, algo, dataset, plugin"
---

# Kingdee Report
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

报表开发的权威入口。Algo/DataSet API 精确签名默认以本 skill references 为权威参考;若项目 jar/Javadoc 与 references 不一致,以项目依赖版本为准并标注差异。通用 Java 二开走 `kingdee-cosmic`,本 skill 只承载报表取数与 Algo 流水线。

## 触发边界
- **适用**:苍穹报表插件(`AbstractReportListDataPlugin` / `AbstractReportFormPlugin`)开发、报表取数、DataSet/Algo 流水线、JOIN/分组聚合、FilterInfo 解析、报表架构选型、Algo API 精确签名查询。
- 用户建议把上述报表插件“放 KingScript”时仍由本 skill 判断实现形态；默认使用 Java 报表插件，只有目标 KingScript 声明和项目现有实现明确支持报表插件基类与 Algo API 时才切换。
- **不适用(转交)**:
  - 普通表单/单据/列表/操作插件、BOTP、工作流 → `kingdee-cosmic`。
  - 字段/实体/挂载点证据 → `kingdee-metadata-analyzer`(先取证再写取数)。
  - SDK 类定义/方法归属/Javadoc → `kingdee-sdk-helper`。
  - KingScript / ISCB 脚本 → `kingdee-kingscript` / ISCB 专用 skill。
  - 报表单测与 Gradle 运行 → `kingdee-testing`。

## 核心心智模型
报表 = 单一 `query()` 入口 + 只读查询 + 无状态设计 + BigDecimal 财务计算 + DataSet 单次消费。详见 `references/mental-model.md`。

## 快速工作流
1. 明确报表标识、数据源实体、过滤项、输出列、计算口径、关联与分组；实体或 query/group/sum 关键字段任一未确认时，输出 `contract_incomplete` 与取证清单后停止，不进入步骤 2-5。只有用户明确要求架构伪代码时才继续，且不得写未核实 SDK 签名。
2. 选架构模式(`references/architecture-patterns.md`):默认 Algo Pipeline(90%);复杂逐行转换用 Map-Based Assembly;成本卷算用 AlgoX。
3. 写取数:解析 `FilterInfo` → 构建 `QFilter[]` → 各数据源 `queryDataSet` → JOIN/UNION → `groupBy().sum().finish()` → `addField()` 计算列 → 返回 DataSet。API 签名以 `references/algo-api.md` 为准,不凭记忆写签名。
4. 按 `references/codegen-checklist.md` 自检:无实例字段、BigDecimal 计算、AlgoKey 唯一、空值安全、NULL 用 `IS NULL`。
5. 编译/运行验证交 `kingdee-testing`;字段口径回 `kingdee-metadata-analyzer` 复核。

## References
- 核心心智模型:`references/mental-model.md`
- 报表架构模式(Pipeline / Map-Based / AlgoX):`references/architecture-patterns.md`
- Algo API 精确签名集:`references/algo-api.md`
- 代码生成规范与验证清单:`references/codegen-checklist.md`

## 契约与门禁
- 报表是纯只读查询:禁用 `SaveServiceHelper` / `OperationServiceHelper` / 直接写库。
- 数据源实体编码或用于 query/group/sum 的关键字段 key 任一未确认时，先交 `kingdee-metadata-analyzer` 取证，只输出待确认清单；除非用户明确只要架构伪代码，否则不生成带占位字段或未核实 SDK 签名的可粘贴插件模板。
- 无状态:禁用实例字段缓存数据,所有数据走局部变量与方法参数;唯一例外 `private static final` 常量。
- 财务计算必须 BigDecimal,比较用 `compareTo()`,禁 `double`/`float`/`==`。
- DataSet 单次消费:遍历后需复用先 `.copy()`;AlgoKey 用 `getClass().getName()+"_suffix"` 保唯一。
- 字段 key、实体编码、refType、SDK 方法签名不能凭记忆猜:用元数据、项目依赖、`kingdee-sdk-helper` 或本 skill references 确认。
- 不在输出/示例中写真实数据库 IP、账号、密码、租户、数据中心、内部 URL、DB schema、连接串或业务敏感字段样例值;示例一律用占位符。
- Algo API 签名默认以本 skill `references/algo-api.md` 为权威参考;与项目实际依赖版本不一致时以项目 jar/Javadoc 为准并标注。

## Output
使用简体中文:结论 → 架构选型依据 → 取数代码 → 字段/口径依据(已确认/未确认)→ 验证与风险。
- `contract_incomplete`：只输出缺少的实体、字段、口径和证据来源，不包含代码块或占位插件模板。
