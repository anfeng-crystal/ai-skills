# ISCB 官方平台脚本目录

## Profile

- 本目录确认平台脚本节点可见的官方名称，不代表 bundled engine JAR 已实现或已运行通过。
- 有详细签名时继续读取 `functions-platform.md`、`functions-platform-services.md`；只有名称而无签名时，先查目标版本官方页面、现有脚本或目标环境，不推断参数。
- 使用 `check-script --mode platform` 做上下文与安全弱预检；最终以目标平台版本验证为准。

## 上下文与语法对象

`#DEFINE`、`#request`、`#RUNTIME.#DEFINE`、`#RUNTIME.#ID`、`$process`、`--=`、`++=`、`char`、`contains`、`empty`、`encode`、`endsWith`、`in`、`length`、`like`、`matches`、`new_boid`、`new_int_id`、`new_uuid`、`NewArray`、`not empty`、`null`、`print`、`println`、`Sleep`、`startsWith`、`static`、`System`、`THIS_URL`、`typeof`。

## 平台调用名称

`$action`、`$action2`、`$batch_action`、`$service`、`$src_service`、`$tar_service`、`bizQuery`、`CheckCancelSignal`、`ClassInfo`、`ClassPath`、`EAS_BOTP`、`executeServiceFlow`、`ExternalApiFunc`、`FastJsonFormat`、`FastJsonParse`、`FilterEvaluator`、`flatObjectToMapOrList`、`GetContext`、`GetPersonByPosition`、`getWorkflowState`、`IERP_BOTP`、`initiateWorkflow`、`invoke_api`、`InvokeHandlerClass`、`invokeMicroService`、`invokeMicroService2`、`NotifyDataCopyEventHandler`、`queryWorkflowState`、`ScriptApiFunc`、`ScriptFunction`、`StartEventDataCopy`、`StartEventServiceFlow`。

以下名称由官方速查确认，但随附资料未给出完整签名；生成调用前必须补目标版本证据：

- `GetPersonByPosition`：按岗位取得当前苍穹系统中启用且未禁用的在职人员 ID。
- `PrivacyTool.convertValue`：按当前系统跨境传输数据标签脱敏。
- `StartEventDataCopy`：补偿启动方案事件触发。
- `NotifyDataCopyEventHandler`：集成事件通知。
- `FilterEvaluator`：事件触发过滤条件。
- `EAS_BOTP` / `IERP_BOTP`：EAS 或当前账套单据下推。

## 命名空间

- `BusinessFlowDataService.isPush`、`BusinessFlowDataService.findSourceBills`、`BusinessFlowDataService.findTargetBills`、`BusinessFlowDataService.loadBillLinkUp`、`BusinessFlowDataService.loadBillLinkUpNodes`、`BusinessFlowDataService.loadBillLinkDown`、`BusinessFlowDataService.loadBillLinkDownNodes`。
- `OpenAPI`：`invokeOperation`、`invokeOperation2`、`queryData`。
- `PrivacyTool`：`convertValue`。

`BusinessFlowDataService.findTargetBills`、`loadBillLinkDown`、`loadBillLinkDownNodes` 由官方速查确认；随附速查未给签名，不按上查函数对称猜参。

## 资源类

| 状态 | 名称 |
|---|---|
| 可用 | `DataCopySchemaResource`、`DataCopyTriggerResource`、`DataSourceResource`、`ExternalApiResource`、`ScriptApiResource`、`ScriptFunctionResource`、`ServiceFlowResource`、`ValueConversionRuleResource` |
| 官方标注暂不支持/未开发 | `MetaSchemaResource`、`SubscriberResource` |

资源类必须来自当前节点已引入的真实资源，不把类名当连接别名，也不自行构造凭据。

## 已废弃

`invokeOpenApi`、`queryOpenApi` 已由官方速查标为废弃；维护旧脚本时允许识别，新代码改用目标版本确认的 `OpenAPI.invokeOperation`、`OpenAPI.invokeOperation2` 或 `OpenAPI.queryData`。
