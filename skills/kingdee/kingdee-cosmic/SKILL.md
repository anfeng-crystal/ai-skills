---
name: kingdee-cosmic
description: "开发、修复或审查金蝶云苍穹 Java 插件、扩展点、服务端 OpenAPI 与工作流配置，评审相关需求与技术方案；报表、脚本和外部 OpenAPI 调用使用各自专用 skill。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.5.0"
  tags: "kingdee, cosmic, java, plugin, BOS, SDK"
---

# Kingdee Cosmic
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 职责与路由

负责苍穹 Java 二开的方案、实现、诊断和交付。需求/技术方案评审按[评审合同](references/requirements-review.md)交付意见；实现任务按下述流程完成。纯 Java 类型、泛型或语法问题直接分析，不启动无关元数据查询。

| 需要的能力 | 路由 |
| --- | --- |
| 字段、实体、页面、派生布局、挂载和上下游证据 | `kingdee-metadata-analyzer`；复用仍适用的 inventory/quick cache，缺失、过期或范围不足才补查 |
| SDK 类、重载、事件、参数及返回语义 | `kingdee-sdk-helper` |
| 元数据修改；页面 JS/CSS；独立控件 | `kingdee-metadata-change`；`kingdee-frontend-script`；`kingdee-custom-control` |
| KingScript；ISCB；外部 OpenAPI 客户端 | `kingdee-kingscript`；`iscb-script`；`kingdee-openapi-client` |
| 报表、DataSet/Algo、GroupbyDataSet、FilterInfo 与报表 API | `kingdee-report` |
| 工程骨架/COSMIC_HOME；鉴权；KSQL/数据；Trace/性能；测试 | `kingdee-cosmic-devtools`；`kingdee-cosmic-login`；`kingdee-sql-and-data`；`kingdee-observability`；`kingdee-testing` |

本地启动、模块构建和部署沿用当前仓库流程，不因涉及 Gradle 就转工程骨架 Skill。

## 工作边界

| 模式 | 完成范围 |
| --- | --- |
| `author` | 本地分析、修改、编译及适用测试，不操作外部环境 |
| `diagnose-readonly` | 对已确认目标、范围和授权做日志、元数据、配置、状态或只读接口取证 |
| `execute-approved` | 执行已授权的环境、对象、动作和数据范围，沿用其恢复/回滚合同 |

这些是助手工作边界，不是待新增的业务开关。复用已有授权和配置，不逐步重问；缺口只暂停依赖它的动作，其他工作继续。凭据不回显。用户指定先预览、自己导入或自己测试时，以该交接点为界；本地检查和环境准备不等于代做业务验收。

## 实施流程

1. **固定业务结果**：明确对象与真实入口、哪些记录/字段可改、允许状态、权限由哪层承担、保存或内存回填、取消/失败行为，以及验收负责人。合并最新用户口径，不把旧方案、模板限制或排障假设变成业务规则。
2. **核对事实**：先查实际挂载、继承链、字段类型和目标依赖，再选事件与 API。区分元数据身份、实体编码、记录主键和业务编码；字符串传输不改变数据库字段类型。涉及移动/派生页面或页面行为时分析 `pageElement`、`formPage` 和插件链，实体 quick-query 不足以证明入口。仅问工作流客户端支持时先查功能说明。
3. **设计完整调用链**：把输入、初始化、交互、确认、保存、回调及失败出口串起来，标明各阶段可用对象和数据类型。列表批改、动态控件、F7、父子页回填或保存关闭问题读[弹窗与分录合同](references/dialog-entry-contract.md)。按同一字段映射修改元数据与代码，不把选值过滤和保存目标匹配混在一起。
4. **实现最小闭合改动**：复用项目允许的基类/helper；只有合同允许时使用 `kd.cd.common.plugin`、`OpUtils`、`BotpUtils`、`QueryUtils`、`DynamicObjectUtils` 等封装，原生 API 作合适的替代。单类能清楚表达的逻辑不抽公共层；示例阈值、开关和参数仅在当前需求需要时采用。已配置的权限/可见性/编辑限制不重复编码，存在已确认绕过入口时才补充。
5. **定位并修复失败**：沿调用链找第一个不符阶段，核对完整异常和目标事实。字段/过滤类型错误按[错误复核](references/error-review-patterns.md)闭合元数据、过滤列、默认值和操作数类型，不靠 Long/String、相似字段名试错。撤掉本轮已否决的实现，保留无关成果。
6. **验证并交付**：按[rules/post-check.md](rules/post-check.md)完成受影响编译、场景/资源检查及适用测试；已有等价证据不重跑，纯注释/格式只查差异。元数据导入、插件部署、服务就绪和业务验收分别取证；完成获授权的交付点后收口，不用编译通过代替运行结论。

## 目标版本与取证

- 沿用已确认的产品/版本与实际项目依赖；`7.0` 不自动补成某个补丁，也不能由较新索引提升到 8.0。具体 API、重载、事件、参数语义和返回行为在写代码前核对；补丁未知但目标 JAR 已足够时继续。版本不明/异版模板只作候选，目标与依赖冲突须报告，不能用另一版本编译证明兼容。
- 本地源码、JAR、现有 analyzer 结果或缓存足够时不启动在线预检；离线证据与目标环境确认分别标记。只有实际使用本 Skill 在线 API、知识库或扩展点查询时才检查配置。
- 从当前目录向上定位聚合根，按“用户指定环境 → 本任务已定环境 → 同项目明确后备”选择配置，优先 `ok-cosmic.<env>.json`，显式传绝对路径：`python3 <SKILL_ROOT>/scripts/cosmic-config-check.py --config <PROJECT_ROOT>/ok-cosmic.<env>.json`。不静默替换环境。
- `graph.dbPath` 是本地离线知识库，可按项目约定跨 DEV/PROD 共用；缺文件是知识库缺失，不是环境冲突。环境/配置不足只停用相关在线能力，不阻断本地编译、测试或已授权部署，也不要求例行登录、下载或预检。

## 按需资料

只加载本次会改变设计或判断的条目；无需读完整资料库。

| 场景 | 资料 |
| --- | --- |
| 需求入口、插件/配置选型、插件类型、命名/日志/模型约束 | `rules/intent-routing.md`、`rules/decision-matrix.md`、`references/plugin-types-cheatsheet.md`、`rules/platform-baseline.md` |
| API 候选、同类模板、事件顺序 | `rules/cheat-sheet.md`、`assets/*.java`、`references/event-lifecycle.md` |
| 扩展点盘点、绑定与治理 | `references/extension-inventory.md`；普通局部修改不扫描全模块 |
| BOTP、DynamicObject、查询、Cache/MQ | `references/botp-convert.md`、`references/dynamic-object.md`、`references/query-dataset.md`、`references/cache-mq-runtime.md` |
| 工作流/审批/业务/列表布局元数据修改 | `references/workflow-metadata-change.md`，修改前读取 |
| CSV/XLSX 导出、容量、数值格式 | `references/list-export-format.md` |
| 任务主题日期/编码显示、移动待办差异、撤销重提旧主题 | `references/workflow-task-subject.md` |
| 元数据生成 DTO/Controller | `references/openapi-metadata-contract.md`，先定对外字段与操作 |
| 提交后自动审核、异步寻址或流转中不能审核 | `references/workflow-submit-audit.md` |
| 参与人、驳回、会审/会签、顺序、同人处理和跳过条件 | `references/workflow-participant-behavior.md` |
| 单据水印 | `references/base/plugin/plugin-form.md` 的“按单据内容生成水印” |

## 实现约束

- 局部修改保留原接口、查询策略、空值/异常和返回语义；只做必要连带调整，不顺带拆类、改依赖或格式化。显式重构按授权范围执行。
- 已有挂载/继承或页面事件覆盖验收路径时不重复注册、追加打开参数或另设保存/接口兜底。没有挂载授权时交类引用、挂载建议和验证步骤，不代改元数据。
- 只写长期有效的功能性注释：类、公共/复杂方法和平台调用、事务、跨库、回写、DataSet、工作流边界；实施流水账不进入源码或长期说明。
- 不直接 SQL，不拼 SQL/KSQL 条件；验证性核对可用独立只读脚本，不混入业务交付。关闭 DataSet/流等资源，避免循环内数据库/Redis/远程调用和反复 `updateView()`，不用 `printStackTrace()`。
- Cache 明确隔离、容量/条数和失效，按并发需求防穿透/击穿；MQ 使用业务幂等键，不能以 `messageId`/`resend` 代替幂等，未知异常不直接 discard，关闭 publisher。具体 API 查目标 SDK。
- 共用物理表不等于同一实体/入口；普通 `.process` 不等于生效 Scheme；保留原节点字段可编辑/必录配置。

## 工具与输出

按需使用 `scripts/cosmic-config-check.py`、`cosmic-api-knowledge.py`、`cosmic-form-metadata.py`、`cosmic-basedata-query.py`、`cosmic-extpoints-query.py`、`cosmic-post-check.py`；lint 和历史扫描在 `scripts/lint/`、`scripts/scan/`。执行前核对该脚本实际参数。

用简体中文报告业务结果、必要改动及证据，区分源码推断、SDK 已确认、目标只读取证和实际运行；明确未完成的交接或验证，不重复罗列无关检查。
