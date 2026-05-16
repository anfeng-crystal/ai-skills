# 完整统一决策矩阵

从 [SKILL.md](../../SKILL.md) 的精简索引命中场景后，只读对应 **1 行主场景** 和 **0-1 行能力行**；不要整表通读。

如果用户原话还是业务描述、还没翻译成“操作插件 / 表单插件 / 基础资料能力”等技术场景，先读 [intent-routing.md](intent-routing.md) 做语义翻译。

## 使用方式

- 先命中 **1 行主场景**（通常是插件行），再按需补 **0-1 行能力行**。
- `入口类 / 包前缀` 主要用于缩小 `cosmic-api-knowledge.py` 的搜索范围，不代表必须直接依赖原生 API。
- `封装文档` 和 `原生文档 / SDK 兜底` 都应先读 `TL;DR`，只有确实需要时再展开全文。

## 插件类

| 需求关键词 | 场景类型 | 入口类 / 包前缀 | 封装文档（先读） | 原生文档 / SDK 兜底 | 模板 / 示例 |
|---|---|---|---|---|---|
| <a id="form-plugin"></a>表单 UI / 字段联动 / 控件交互 | 插件：表单插件 | `kd.cd.common.plugin.AbstractFormPluginExt`<br>`kd.bos.form.plugin.*`<br>`kd.bos.form` / `kd.bos.form.control` | [plugin-base.md](../adv/plugin-base.md)<br>[form-utils.md](../adv/form-utils.md) | [plugin-form.md](../base/plugin/plugin-form.md) | [FormPluginTemplate.java](../../assets/FormPluginTemplate.java)<br>[ViewControlOpsSample.java](../../assets/snippets/form/ViewControlOpsSample.java)<br>[F7FilterSample.java](../../assets/snippets/form/F7FilterSample.java) |
| <a id="bill-plugin"></a>单据 UI / 审核提交按钮 | 插件：单据插件 | `kd.cd.common.plugin.AbstractBillPlugInExt`<br>`kd.bos.form.plugin.*`<br>`this.getView()` / `this.getModel()` | [plugin-base.md](../adv/plugin-base.md)<br>[form-utils.md](../adv/form-utils.md) | [plugin-bill.md](../base/plugin/plugin-bill.md) | [BillPlugInTemplate.java](../../assets/BillPlugInTemplate.java)<br>[OpenBillModalSample.java](../../assets/snippets/form/OpenBillModalSample.java) |
| <a id="list-plugin"></a>列表 / 多选操作 / 批量 | 插件：列表插件 | `kd.cd.common.plugin.AbstractListPluginExt`<br>`kd.bos.list.plugin.AbstractListPlugin`<br>`kd.bos.list` | [plugin-base.md](../adv/plugin-base.md) | [plugin-list.md](../base/plugin/plugin-list.md) | [ListPluginTemplate.java](../../assets/ListPluginTemplate.java)<br>[ListPluginBasicSample.java](../../assets/snippets/list/ListPluginBasicSample.java) |
| <a id="tree-plugins"></a><a id="tree-list-bill-plugin"></a>左树右表（单据） | 插件：单据树列表插件 | `kd.bos.list.plugin.AbstractTreeListPlugin`<br>`kd.bos.list` | [plugin-base.md](../adv/plugin-base.md) | [plugin-tree-list.md](../base/plugin/plugin-tree-list.md) | [TreeListPluginTemplate.java](../../assets/TreeListPluginTemplate.java)<br>[TreeControlSample.java](../../assets/snippets/form/TreeControlSample.java) |
| <a id="tree-list-basedata-plugin"></a>左树右表（基础资料） | 插件：基础资料树列表插件 | `kd.bos.list.plugin.AbstractTreeListPlugin`<br>`kd.bos.list` | [plugin-base.md](../adv/plugin-base.md) | [plugin-tree-list.md](../base/plugin/plugin-tree-list.md) | [StandardTreeListPluginTemplate.java](../../assets/StandardTreeListPluginTemplate.java)<br>[TreeControlSample.java](../../assets/snippets/form/TreeControlSample.java) |
| <a id="op-plugin"></a>审核 / 保存 / 状态流转 / 校验 / 回滚 | 插件：操作插件 | `kd.cd.common.operate.OpUtils`<br>`kd.cd.common.operate.chain.OperateChain`<br>`kd.bos.entity.plugin.AbstractOperationServicePlugIn`<br>`kd.bos.entity.plugin.*` / `kd.bos.entity.plugin.args` | [operate-chain.md](../adv/operate-chain.md) | [plugin-operation.md](../base/plugin/plugin-operation.md)<br>[sdk-dynamic-model-svc.md](../base/sdk/sdk-dynamic-model-svc.md) | [OpPluginTemplate.java](../../assets/OpPluginTemplate.java)<br>[OpAddValidatorsSample.java](../../assets/snippets/operation/OpAddValidatorsSample.java)<br>[OperationOptionBridgeSample.java](../../assets/snippets/operation/OperationOptionBridgeSample.java) |
| <a id="convert-plugin"></a>下推 / 选单 / 来源追踪 / 转换 | 插件：转换插件 | `kd.cd.common.util.BotpUtils`<br>`kd.bos.entity.botp.runtime.*`<br>`kd.bos.entity.botp.plugin.AbstractConvertPlugIn` | [botp-convert.md](../adv/botp-convert.md) | [plugin-botp.md](../base/plugin/plugin-botp.md) | [ConvertPlugInTemplate.java](../../assets/ConvertPlugInTemplate.java)<br>[BotpTracePushSample.java](../../assets/snippets/botp/BotpTracePushSample.java) |
| <a id="writeback-plugin"></a>明确指定反写插件 / BOTP 回写阶段 | 插件：反写插件 | `kd.bos.entity.botp.plugin.AbstractWriteBackPlugIn`<br>`kd.bos.servicehelper.botp.ConvertServiceHelper` | [botp-convert.md](../adv/botp-convert.md) | [plugin-writeback.md](../base/plugin/plugin-writeback.md) | [WriteBackPlugInTemplate.java](../../assets/WriteBackPlugInTemplate.java)<br>[BatchQuerySample.java](../../assets/snippets/query/BatchQuerySample.java) |
| <a id="special-plugins"></a><a id="report-form-plugin"></a>报表 / 数据分析 / 过滤容器 | 插件：报表插件 | `kd.bos.report.plugin.AbstractReportFormPlugin` | — | [plugin-report-form.md](../base/plugin/plugin-report-form.md) | [ReportFormPluginTemplate.java](../../assets/ReportFormPluginTemplate.java) |
| <a id="report-data-plugin"></a>报表取数 / 动态列 / 自定义数据源 | 插件：报表取数插件 | `kd.bos.entity.report.AbstractReportListDataPlugin`<br>`DataSet` | [query-dataset.md](../adv/query-dataset.md) | [plugin-report-data.md](../base/plugin/plugin-report-data.md)<br>[sdk-algo.md](../base/sdk/sdk-algo.md) | [ReportListDataPluginTemplate.java](../../assets/ReportListDataPluginTemplate.java)<br>[DataSetQueryStatSample.java](../../assets/snippets/query/DataSetQueryStatSample.java) |
| <a id="print-plugin"></a>打印 / 套打 | 插件：打印插件 | `kd.bos.print.core.plugin.AbstractPrintPlugin` | — | [plugin-print.md](../base/plugin/plugin-print.md) | [PrintPluginTemplate.java](../../assets/PrintPluginTemplate.java) |
| <a id="openapi-plugin"></a>OpenAPI / 外部集成 | 插件：OpenAPI 控制器 | `kd.bos.openapi.common.custom.annotation`<br>`@ApiController` / `@ApiMapping` | — | [plugin-openapi.md](../base/plugin/plugin-openapi.md) | [OpenApiControllerTemplate.java](../../assets/OpenApiControllerTemplate.java) |
| <a id="task-plugin"></a>后台任务 / 定时 / 调度作业 | 插件：后台任务 | `kd.bos.schedule.executor.AbstractTask` | — | [plugin-task.md](../base/plugin/plugin-task.md) | [TaskTemplate.java](../../assets/TaskTemplate.java)<br>[ScheduleTaskSample.java](../../assets/snippets/task/ScheduleTaskSample.java) |
| <a id="workflow-plugin"></a>工作流 / 审批流 | 插件：工作流插件 | `kd.bos.workflow.engine.extitf.IWorkflowPlugin` | — | [plugin-workflow.md](../base/plugin/plugin-workflow.md) | [IWorkflowPluginTemplate.java](../../assets/IWorkflowPluginTemplate.java) |
| <a id="import-plugin"></a>导入 / 批量导入 | 插件：导入插件 | `kd.bos.form.plugin.impt.BatchImportPlugin` | — | [plugin-import.md](../base/plugin/plugin-import.md) | [BatchImportPluginTemplate.java](../../assets/BatchImportPluginTemplate.java) |

## 能力类

| 需求关键词 | 场景类型 | 入口类 / 包前缀 | 封装文档（先读） | 原生文档 / SDK 兜底 | 模板 / 示例 |
|---|---|---|---|---|---|
| <a id="view-handler"></a>后台打开表单 / 列表 / 新页签跳转 | 能力：视图打开与跳转 | `kd.cd.common.form.handler.ViewHandler`<br>`AutoCloseViewHandler`<br>`FormShowParameter` | [view-handler.md](../adv/view-handler.md) | —（必要时用 `cosmic-api-knowledge.py` 定向查视图参数类） | —（优先直接看 `view-handler.md` 内示例） |
| <a id="form-utils"></a>表单控件 / UI 消息 / 元数据读取 | 能力：界面工具 | `kd.cd.common.form.FormUtils`<br>`this.getView()` / `this.getModel()`<br>`kd.bos.form.control` | [form-utils.md](../adv/form-utils.md) | [plugin-form.md](../base/plugin/plugin-form.md)<br>[plugin-bill.md](../base/plugin/plugin-bill.md)<br>[plugin-list.md](../base/plugin/plugin-list.md) | [ViewControlOpsSample.java](../../assets/snippets/form/ViewControlOpsSample.java)<br>[ConfirmDialogSample.java](../../assets/snippets/form/ConfirmDialogSample.java)<br>[F7FilterSample.java](../../assets/snippets/form/F7FilterSample.java) |
| <a id="query"></a>数据加载 / 保存 / 查询 / ORM / DataSet | 能力：查询与存取 | `QueryUtils` / `AlgoUtils`<br>`BusinessDataServiceHelper`<br>`QueryServiceHelper`<br>`QFilter` | [query-dataset.md](../adv/query-dataset.md) | [sdk-dynamic-model-svc.md](../base/sdk/sdk-dynamic-model-svc.md)<br>[sdk-orm-access.md](../base/sdk/sdk-orm-access.md)<br>[sdk-algo.md](../base/sdk/sdk-algo.md) | [BatchQuerySample.java](../../assets/snippets/query/BatchQuerySample.java)<br>[DataSetQueryStatSample.java](../../assets/snippets/query/DataSetQueryStatSample.java)<br>[DynamicObjectCrudSample.java](../../assets/snippets/data/DynamicObjectCrudSample.java) |
| <a id="basedata"></a>基础资料 / 管控策略 / 分配 / 个性化 | 能力：基础资料 | `BaseDataServiceHelper`<br>`kd.bd.master.*`<br>`AssignIndividuationHelper` | —（先用 `cosmic-form-metadata.py` / `cosmic-basedata-query.py` 确认 `refType` / `entityId`） | [sdk-dynamic-model-svc.md](../base/sdk/sdk-dynamic-model-svc.md) | [BaseDataQuerySample.java](../../assets/snippets/query/BaseDataQuerySample.java) |
| <a id="dynamic-object"></a>DynamicObject / 安全取值 / 序列化 | 能力：数据包操作 | `kd.cd.common.util.DynamicObjectUtils`<br>`DynamicObject`<br>`DynamicObjectCollection` | [dynamic-object.md](../adv/dynamic-object.md) | [sdk-dynamic-object.md](../base/sdk/sdk-dynamic-object.md) | [DynamicObjectOpsSample.java](../../assets/snippets/data/DynamicObjectOpsSample.java)<br>[DynamicObjectCrudSample.java](../../assets/snippets/data/DynamicObjectCrudSample.java) |
| <a id="entity-metadata"></a>实体元数据 / 字段路径 / DBRoute | 能力：元数据与结构 | `kd.cd.common.entity.EntityUtils`<br>`EntityType` / `MainEntityType`<br>`IDataEntityProperty`<br>`DBRoute` | [entity-metadata.md](../adv/entity-metadata.md) | [sdk-entity-model.md](../base/sdk/sdk-entity-model.md)<br>[sdk-orm-access.md](../base/sdk/sdk-orm-access.md) | — |
| <a id="flex-prop"></a>弹性域字段 / 值解析 | 能力：弹性域 | `kd.cd.common.util.FlexPropUtils`<br>`FlexType` | [flex-prop.md](../adv/flex-prop.md) | —（必要时回到元数据脚本 + `cosmic-api-knowledge.py`） | — |
| <a id="misc"></a><a id="message"></a>消息 / 邮件 / 短信 / 企业微信 | 能力：消息通知 | `kd.bos.servicehelper.message.MessageServiceHelper`<br>`kd.bos.message.api.EmailInfo`<br>`kd.bos.message.api.*` | — | —（必要时用 `cosmic-api-knowledge.py` 定向查 `kd.bos.servicehelper.message` / `kd.bos.message.api`） | [MessageNotifySample.java](../../assets/snippets/message/MessageNotifySample.java) |
| <a id="attachment"></a>附件上传 / 下载 / 复制 / 面板绑定 | 能力：附件与文件 | `AttachmentUtils`<br>`AttachmentServiceHelper` | [attachment-api.md](../adv/attachment-api.md) | [sdk-file.md](../base/sdk/sdk-file.md) | [AttachmentUploadBindSample.java](../../assets/snippets/attachment/AttachmentUploadBindSample.java) |
| <a id="request-context"></a>组织 / 权限 / 上下文 / 组织维度过滤 | 能力：上下文判定 | `RequestContext`<br>`Permission` 相关 service/helper | [request-context.md](../adv/request-context.md) | [sdk-request-context.md](../base/sdk/sdk-request-context.md) | — |
| <a id="thread-context"></a>跨线程身份 / 上下文恢复 | 能力：并发上下文恢复 | `RequestContextUtils`<br>`ThreadPools` | [request-context.md](../adv/request-context.md) | [sdk-threadpool.md](../base/sdk/sdk-threadpool.md)<br>[sdk-request-context.md](../base/sdk/sdk-request-context.md) | [ScheduleTaskSample.java](../../assets/snippets/task/ScheduleTaskSample.java) |

## 未命中兜底

<a id="fallback"></a>

如果需求不属于上述矩阵中的任一场景：

1. **需求可拆分**：将需求拆解为多个子任务，分别匹配矩阵。常见组合：
   - "保存前校验 + 审核后下推 + 下推后在 BOTP 回写阶段更新来源" → 操作插件 + 转换插件 + 反写插件
   - "列表批量选中 + 弹窗编辑 + 保存" → 列表插件 + 表单插件 + 操作插件
2. **纯后端逻辑（无 UI、无操作链）**：优先命中“数据加载 / 保存 / 查询”“基础资料”“消息通知”“上下文恢复”等能力行；仍不匹配时，再回到 `references/base/sdk/` 原生 SDK 文档。
3. **仍无法匹配**：先用 `cosmic-api-knowledge.py search <关键词>` 搜索相关类，再向用户确认具体实现方向后动手。
