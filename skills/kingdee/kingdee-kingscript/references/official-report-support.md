# KingScript 报表支持与版本证据

- [报表查询插件 KingScript 开发指南](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=720698994112075264&id=720667350873190144&type=Knowledge&productLineId=29&lang=zh-CN)，官方开发平台知识库，更新于 2026-07-30 01:35。正文以 TS 继承 `AbstractReportListDataPlugin`，导入 `@cosmic/bos-core/kd/bos/algo` 的 `DataSet`，并在报表设计器注册脚本插件。短证据：“新建ts文件，继承AbstractReportListDataPlugin插件”。
- 指南未给出最低适用版本。它证明此实现形态存在，不能证明每个旧项目、每个 Algo API 或所有脚本 SDK 版本均支持。生成前核对目标 `.d.ts`/SDK 的基类、事件签名、导入和所用方法；不要求新项目已经有同类实现。
- [报表表单插件 KingScript 开发指南](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=720698994112075264&id=720653325691249152&type=Knowledge&productLineId=29&lang=zh-CN)，更新于 2026-07-30 01:36；正文以 TS 继承 `AbstractReportFormPlugin` 并演示 `verifyQuery(ReportQueryParam)`，同样未声明最低版本。
- [VSCode插件开发](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=720698901904349440&id=721307554554364928&type=Knowledge&productLineId=29&lang=zh-CN)，更新于 2026-07-30 01:30；官方流程在连接账套、创建工程时下载 SDK。此事实用于说明工程与环境的关联，不要求本地编辑任务登录、安装 VSCode 或使用特定 Agent。

本 skill 负责脚本形态，`kingdee-report` 负责数据源、字段、过滤、只读和 Algo 流水线。已有 `templates/report-query-plugin-template.md`、`examples/plugins/插件示例/报表查询插件.md` 可作结构线索；它们不能替代目标声明或真实字段证据。真实上传、注册、运行仍遵守原有授权合同。
