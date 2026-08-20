---
name: kingdee-cosmic
description: "Kingdee Cosmic Java dev: 金蝶云苍穹 Java 二开、插件、BOTP/工作流、服务端 OpenAPI、Cache/MQ、运行诊断和代码质量核查。纯报表交 kingdee-report；外部 OpenAPI 调用交 kingdee-openapi-client；元数据/挂载证据交 kingdee-metadata-analyzer；SDK/API 签名交 kingdee-sdk-helper；KingScript/ISCB 分别交 kingdee-kingscript/iscb-script。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.4.0"
  tags: "kingdee, cosmic, java, plugin, BOS, SDK"
---

# Kingdee Cosmic
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 契约
- 默认“封装优先，原生兜底”：项目已有 `kd.cd.common.plugin` 扩展基类、`OpUtils`、`BotpUtils`、`QueryUtils`、`DynamicObjectUtils` 或同类 helper 能覆盖时，不再另写第二套平台封装。
- 字段、`entityId`、枚举值、`refType`、SDK 方法签名和 `@Override` 事件签名不能凭记忆猜；用元数据、项目依赖、`kingdee-sdk-helper` 或本 skill 脚本确认。
- 改插件注册、页面打开参数或挂载链路前，先确认实体、表单、布局、派生页面和操作的真实挂载/继承关系。
- 本地 SDK/JAR/Javadoc 和目标项目编译证据优先于社区文章或跨版本示例；社区资料只能提供候选，必须标明来源与版本并在本地复核。

## 模式

| 模式 | 动作边界 |
|---|---|
| `author` | 本地生成、修改、编译和测试；不触碰外部环境 |
| `diagnose-readonly` | 对已知目标、范围和授权做日志、元数据、配置、状态或只读接口取证；生产只读任务满足契约后可直接执行 |
| `execute-approved` | 仅执行用户已批准的环境、目标、动作、数据范围和回滚/恢复契约；契约完整后不重复确认，不扩到部署、发布或数据写入之外的动作 |

目标、范围、授权或动作性质不明时停止在本地证据层，并列出缺失项；任何模式都不回显凭据。

## 触发与路由
1. 只处理金蝶云苍穹 Java 二开、插件、配置、诊断、代码核查或改造任务，以及服务端 OpenAPI 开发。KingScript 用 `kingdee-kingscript`；ISCB 用 `iscb-script`；外部 OpenAPI 调用用 `kingdee-openapi-client`；SDK/Javadoc/方法签名查询用 `kingdee-sdk-helper`。
2. 纯 Java 语法、类型、泛型、集合或编译错误可直接分析，不要无意义触发元数据查询。
3. 涉及实体、字段、表单、页面/操作挂载点、插件绑定或上下游关系时，先交 `kingdee-metadata-analyzer` 做环境选择、配置候选、在线查询和降级取证。
4. 移动端、派生表单、页面元素或生产行为链路问题，不能只看实体 quick-query；要求 analyzer 全景分析并核对 `pageElement`、`formPage`、派生表单和插件挂载链。
5. 宿主工程模板、资源包、本地启动/页面联调上下文、登录态、配置检查或 KSQL/数据脚本，转 `kingdee-cosmic-devtools`、`kingdee-cosmic-login`、`kingdee-sql-and-data`。
6. 纯报表插件取数、DataSet/Algo 流水线、GroupbyDataSet 聚合、FilterInfo 解析和 Algo API 精确签名，转 `kingdee-report`；本 skill 只保留轻量路由和概览。

## 取证
- 只有任务实际需要本 skill 的在线 API、知识库或扩展点查询时才做配置预检；纯源码分析、Java 修改、模块级 Gradle 编译/测试、`jarZip`、`uploadZipRestartAndWait`、服务重启或部署验收不得仅为例行检查运行它。
- 配置预检先从当前目录向上定位聚合项目根，再按“用户明确目标环境 → 当前任务已确定环境 → 同项目通用配置仅作明确后备”选择配置。环境已确定时优先使用 `ok-cosmic.<env>.json`，不得用其它环境或泛化 `ok-cosmic.json` 静默替代。
- 环境配置文件按目标环境选择，但 `graph.dbPath` 表示本地离线知识库，同一项目的 DEV/PROD 可以按项目约定共享同一路径；路径相同不是跨环境混用。共享文件不存在时应报告知识库缺失，不能误判为环境配置选择错误。
- 执行时必须显式传绝对配置路径：`python3 <SKILL_ROOT>/scripts/cosmic-config-check.py --config <PROJECT_ROOT>/ok-cosmic.<env>.json`。未确定环境或未找到对应配置时只停用相关在线能力，不得声称“仓库未提供配置”，也不得阻断不依赖在线能力的本地编译、测试或部署。
- 业务话术先读 `rules/intent-routing.md`，再按 `rules/decision-matrix.md` 选插件、配置、脚本或诊断路径。
- 生成或修改 Java 前，读 `rules/platform-baseline.md`、`rules/cheat-sheet.md` 和最接近的 `assets/*.java` 模板；事件顺序不确定时读 `references/event-lifecycle.md`。
- 在线元数据不可用时，可复用 analyzer 产物、quick-query 缓存、项目源码、JAR 和本 skill references，但输出必须区分“源码推断”和“目标环境元数据已确认/未确认”。

## 工作流
1. 明确任务类型、目标对象、插件类型、事件点、事务边界、环境口径和验证方式。
2. 依赖目标环境元数据的问题，把元数据取证交给 `kingdee-metadata-analyzer`；本 skill 并行查源码、同类实现、模板、snippet 和运行时堆栈。
3. 按需读取最小资料集：插件/配置选型 `rules/decision-matrix.md`；API 速查 `rules/cheat-sheet.md`；插件类型 `references/plugin-types-cheatsheet.md`；BOTP `references/botp-convert.md`；DynamicObject `references/dynamic-object.md`；生命周期 `references/event-lifecycle.md`；工作流/布局元数据包 `references/workflow-metadata-change.md`；DataSet 概览 `references/query-dataset.md`；Cache/MQ `references/cache-mq-runtime.md`；异常诊断与复核 `references/error-review-patterns.md`。
4. 先查当前项目已有基类、helper、wrapper 和同类实现；能复用现有 helper 时不新增公共能力。
5. 页面事件已覆盖验收路径时，不默认追加保存、操作、接口或批量链路兜底；只有需求明确覆盖绕过页面事件的入口时才扩展链路。
6. 编码后执行模块级 Gradle 编译/测试；无法定位模块时执行 `python3 <SKILL_ROOT>/scripts/cosmic-post-check.py <file_or_dir> --fix-hint`。
7. 收口按 `rules/post-check.md` 给出依据、改动、验证和风险。

## Scripts
- 配置预检：`scripts/cosmic-config-check.py`
- API/知识库查询：`scripts/cosmic-api-knowledge.py`
- 表单/字段元数据：`scripts/cosmic-form-metadata.py`
- 基础资料查询：`scripts/cosmic-basedata-query.py`
- 业务拓展点查询：`scripts/cosmic-extpoints-query.py`
- 代码后检：`scripts/cosmic-post-check.py`
- lint 规则：`scripts/lint/`
- 历史质量扫描：`scripts/scan/`

## 门禁
- 最小必要修改；不改公共接口、依赖或文件结构，除非用户明确要求或方案已确认。
- 已有挂载或继承链路能覆盖当前页面/操作时，不重复注册插件或追加同类打开参数。
- 未获得元数据挂载授权时只交插件类引用、建议挂载点和验证步骤，不代改/代挂元数据。页面配置已经承担范围过滤、可见性或编辑边界时，Java 不重复编码同一限制，除非存在已确认的绕过入口。
- 第一次出现字段/过滤类型错误后，必须读取完整异常链和目标元数据，按 `references/error-review-patterns.md` 闭合四方类型合同；禁止继续在 `Long`、`String`、`entityField` 或相似字段名之间试错。
- 不把实施过程、排查路径或交付口径写入代码注释、README、skills 或长期操作说明。
- 新增类、公共方法、复杂私有方法、关键平台调用、事务/跨库/回写/DataSet/工作流边界只写长期有效的功能性注释。
- 不直接 SQL，不拼接 SQL/KSQL 条件字符串；验证性数据核对可用独立只读脚本完成，不作为业务交付实现。
- `DataSet` 必须关闭；禁止循环内访问数据库、Redis 或反复 `view.updateView()`；禁止 `printStackTrace()`。
- Cache 必须有隔离 key、容量/条数边界和失效契约；高并发回源需防穿透/击穿，精确 API 按目标 SDK 确认。
- MQ 必须用业务幂等键；`messageId` 非全局唯一，`resend` 不能判幂等；未知异常不得直接 `discard`，publisher 必须关闭。
- 修改工作流、审批布局、业务布局或列表布局时，必须先读 `references/workflow-metadata-change.md`。不得因共用物理表合并实体/入口，不得把普通 `.process` 当作当前生效 Scheme，也不得静默删除原节点单字段可编辑/必录配置。

## 输出
使用简体中文，先给结论，再给依据、边界和风险。实现类任务按“依据 -> 改动 -> 验证 -> 风险/待确认项”收口；区分源码推断、SDK 已确认、目标环境只读确认和实际执行结果。
