# ISCB 平台层函数 — 服务调用与集成

> 本文件覆盖服务调用、数据集成、服务流程、数据对比、数据流等平台功能函数。
> 这些示例默认都带有平台上下文前提，不适合作为普通引擎层脚本的默认模板。
> 只有当用户明确说到集成方案、服务流程、脚本 API、连接资源或平台服务调用时，再优先参考这里。

---

## 1. 业务对象操作

### $action(cn, entity, actions, data, judgeFields) -> Map
调用目标系统实体操作（保存、提交等）。用于服务流程/脚本 API 中。
- `cn`：连接别名（String，如 `'ierp'`）
- `entity`：实体编码（String）
- `actions`：操作列表（List，如 `['save']`、`['save','submit']`）
- `data`：数据 Map
- `judgeFields`：候选键 Map，`$` 表示主表，分录实体名表示分录
- 返回 `{id: Long, type: String}`（type: INSERT/UPDATE/DELETE/UNKNOWN）
```javascript
var result = $action('ierp', 'isc_demo_basedata_1', ['save'], tar,
    {'$': ['id'], 'entryentity': ['id']});
// result: {id: 12345, type: "INSERT"}
```

### $action2(cn, entity, actions, data, judgeFields, proxyUser?, actionParams?) -> Map
带操作参数的实体操作调用。
- `proxyUser`：代理用户（String/Long，可选）
- `actionParams`：操作参数 Map，key 为操作名，value 为参数 Map
```javascript
var result = $action2('cn', 'isc_demo_basedata_5', ['save','submit'], data,
    {'$': ['number'], 'entryentity': ['id']}, null, {'save': {'x': 'abc'}});
```

### $batch_action(cn, entity, dataList, pk, judgeFields, action, proxyUser?) -> List
批量执行实体操作。
- `dataList`：数据列表（List\<Map>）
- `pk`：主键字段名（String）
- `action`：操作名（String，如 `'save'`）
- 返回操作结果列表
```javascript
var results = $batch_action('ierp', 'isc_demo_basedata_5', dataList, 'id',
    {'$': ['number'], 'entryentity': ['seq']}, 'save');
```

### triggerEvent(entity, operation, ids) -> Boolean
模拟触发单据事件（不支持删除事件）。
```javascript
triggerEvent("isc_demo_basedata_1", "save", [L(123456789), L(456789123)]);
```

### InvokeHandlerClass(cn, className, data, judgeFields, proxyUser?) -> Map
调用目标数据处理类。支持苍穹、EAS、直连数据库连接器。
- `className`：类全限定名或微服务地址（如 `"msvc://isc.iscb.IscTestService.targetHandle"`）
```javascript
var result = InvokeHandlerClass(cn, "msvc://isc.iscb.IscTestService.targetHandle",
    data, judgeFields, "17299999999");
```

---

## 2. 业务系统服务

### $service(cn, serviceName, params, proxyUser?) -> Object
调用业务系统服务。
- `cn`：连接别名（String）
- `serviceName`：服务协议地址，支持：
  - `xapi://cloudid.appid.service.method` — 苍穹 XAPI
  - `mservice://cloudid.appid.service.method` — 微服务
  - `openapi_invoke://path` — OpenAPI 调用
  - `openapi_query://path` — OpenAPI 查询
  - `facade://classname.method` — EAS Facade
- `params`：参数 Map（key 为 `p0`, `p1`... 表示参数位置）
- `proxyUser`：代理用户（String/Long，可选）
```javascript
$service('ierp', 'xapi://cloudid.appid.service.method',
    {p0: value1, p1: value2}, '17299999999');
```

### $src_service(serviceName, params) -> Object
调用源系统星空/EAS API。仅在数据集成方案中可用。
```javascript
var res = $src_service("ExecuteBillQuery", {"#data": [{"FormId": "BD_Currency"}]});
```

### $tar_service(serviceName, params) -> Object
调用目标系统星空/EAS API。仅在数据集成方案中可用。

### bizQuery(cn, entity, requires, filters, orderby?) -> List\<Map>
查询单据对象列表（支持苍穹、EAS、星空、PG）。
- `requires`：需要的字段（String，逗号分隔）
- `filters`：过滤条件 Map
- `orderby`：排序 Map（可选）
```javascript
var list = bizQuery('ierp', 'isc_data_copy_trigger',
    'number,id,name,data_copy.id',
    {number: 'isc_demo_basedata_5-isc_demo_basedata_3'},
    {id: 'ASC'});
```

### invokeMicroService(cloudid, appid, servicename, method, ...args) -> Object
调用苍穹微服务（变长参数）。
```javascript
var result = invokeMicroService('isc', 'iscb', 'ISCDataCopyService',
    'getExecutionState', 'AASCI1ONKBGVA-jwltest');
```

### invokeMicroService2(cloudid, appid, servicename, method, params, proxyUser?) -> Object
调用苍穹微服务（List 参数 + 代理用户）。
```javascript
var result = invokeMicroService2('isc', 'iscb', 'ISCDataCopyService',
    'getExecutionState', ['AASCI1ONKBGVA-jwltest'], '17299999999');
```

---

## 3. OpenAPI

### OpenAPI.invokeOperation2(apiUrl, requestData, header?) -> Object
调用 OpenAPI 2.0 端点，仅返回 data 域。
```javascript
var apiUrl = "/v2/iscb/isc_demo_basedata_1/demo1_query";
var params = {data: {number: "sw0907A"}, pageNo: 1, pageSize: 10};
var result = OpenAPI.invokeOperation2(apiUrl, params, null);
```

### OpenAPI.queryData(apiUrl, data, pageSize, pageNo) -> Object
调用 OpenAPI 2.0 查询服务。
```javascript
var result = OpenAPI.queryData("/v2/iscb/isc_data_source/get_data_source",
    {"number": "UNIT-TEST-THIS-SYSTEM-1"}, 10, 1);
```

---

## 4. 数据集成服务（ISCDataCopyService）

> 以下函数通过 `invokeMicroService('isc','iscb','ISCDataCopyService', ...)` 调用。

### pull(triggerNumber, filterParams) -> Map
查询源数据。返回 `{success, data, msg}`。

### pullAndTranslate(triggerNumber, filterParams) -> Map
查询源数据并按方案值转换规则翻译。返回 `{success, data, total_count, msg}`。

### translate(triggerNumber, srcData) -> Map
翻译已有源数据列表。`srcData` 为 `List<Map>`。

### translateX(triggerNumber, objects) -> Map
翻译动态对象列表。`objects` 为 `DynamicObject[]`。

### syncExecute(triggerNumber, filterParams) -> Map
同步执行启动方案。返回 `{trigger_number, success, execution_number, msg}`。

### synExecuteWithRealDataSource(triggerNumber, params, realSource, realTarget) -> Map
同步执行启动方案（运行时修改源/目标系统）。

### execute(triggerNumber, params, callback?) -> Map
异步执行启动方案。`callback` 可选回调信息 Map。

### executeWithRealDataSource(triggerNumber, params, realSource, realTarget) -> Map
异步执行启动方案（运行时修改源/目标系统）。

### push(triggerNumber, dataSet) -> Map
用准备好的数据同步写入目标单。`dataSet` 为 `List<Map>`。返回 `{success, msg, total_count}`。

### pushX(triggerNumber, objects) -> Map
用动态对象列表同步写入目标单。

### submit(triggerNumber, dataset, callback?) -> Map
用准备好的数据异步写入目标单。返回 `{success, msg, execution_number}`。

### submitX(triggerNumber, objects, callback?) -> Map
用动态对象列表异步写入目标单。

### enableTrigger(number) -> void
启用启动方案。

### disableTrigger(number) -> void
禁用启动方案。

### queryExecutionLogs(executionId, limit) -> Map
查询数据集成执行日志。返回 `{success, data, msg}`。

### retryLog(logId) -> Map
重试执行日志。

```javascript
// 示例：同步执行启动方案（平台服务调用）
var result = invokeMicroService('isc', 'iscb', 'ISCDataCopyService',
    'syncExecute', 'TRIGGER_001', {fstatus: '0'});
if(result.success) {
    println("执行成功，编号: " + result.execution_number);
}

// 示例：用准备好的数据写入目标（平台服务调用）
var data = [{fnumber: '001', fname: '物料A'}, {fnumber: '002', fname: '物料B'}];
var result = invokeMicroService('isc', 'iscb', 'ISCDataCopyService',
    'push', 'TRIGGER_001', data);
```

---

## 5. 集成方案服务（IscIntegrateSchemaService）

### pullBySchema(schema, filter, limit, ignoreError) -> List\<Map>
从源系统取数并按集成方案转换。

### executeBySchema(schema, filter, maxCount, ignoreError) -> List\<Map>
取数、转换并推送到目标系统。返回含 srcId, tarId, type, errorMessage 的列表。

### pushBySchemaX(schema, objects, ignoreError) -> List\<Map>
将动态对象列表按方案转换并推送到目标。

---

## 6. 服务流程（IscFlowService）

### execute(number, inputs?) -> Map
同步执行服务流程。
- `number`：服务流程编码
- `inputs`：参数（List 或无参）
- 返回 `{id: Long, output: Map}`
```javascript
var result = invokeMicroService('isc', 'iscb', 'IscFlowService',
    'execute', 'flow_demo', [1, 2]);
// result: {id: 1387508114353294336, output: {c: 3}}
```

### execute2(number, params) -> Map
同步执行服务流程（Map 参数）。

### start(number, inputs?) -> Long
异步执行服务流程，返回实例 ID。

### start2(number, params) -> Long
异步执行服务流程（Map 参数），返回实例 ID。

### executeServiceFlow(flowAlias, params, withProcInst?) -> Map
执行引入的服务流程（在脚本中直接调用）。
- `flowAlias`：导入的服务流程别名
- `params`：参数（Array/Map/单值）
- `withProcInst`：是否返回流程实例信息（Boolean）
```javascript
var result = executeServiceFlow(flow_demo, [1, 2], true);
// result: {output: {c: 3}, id: 1387508114353294336}
```

### StartEventServiceFlow(flowNumber, param, proxyUser, isSync) -> Map
触发事件型服务流程。
- `isSync`：true=同步，false=异步
```javascript
var result = StartEventServiceFlow("event_flow",
    {number: "20230213"}, "17299999999", true);
```

### terminate(instId) -> Boolean
取消/终止等待中或失败的流程实例。

---

## 7. 数据对比（IscDataCompService）

### execute(dataCompNumber, params) -> Map
同步执行数据对比方案。返回 `{success, msg, execution_number}`。

### start(dataCompNumber, params) -> Map
异步启动数据对比方案。

### compensateByExeDetail(logIdList) -> Map
按对比结果明细日志 ID 执行补偿（每次最多 100 条）。

### compensateExecution(executions) -> Map
批量执行对比结果补偿。

### getStateList(executions) -> Map
批量获取对比结果状态。

---

## 8. 数据流（IscDataFlowService）

> 通过 `invokeMicroService('isc','iscx','IscDataFlowService', ...)` 调用。

### enable(triggerNumber) -> void
启用数据流启动方案。

### disable(triggerNumber) -> void
禁用数据流启动方案。

### start(triggerNumber, params) -> Long
模拟启动数据流（人工启动/定时启动类型），返回数据流实例 ID。

### startX(triggerNumber, batch) -> Long
模拟启动数据流（事件触发/MQ 触发类型），传入批量数据。

---

## 9. 数据加载（IscDataLoadService）

### invokeX(tars, loadRes, connector) -> List\<Map>
批量执行数据加载（保存/删除/其他服务）。
- `tars`：目标数据列表
- `loadRes`：数据加载资源 ID
- `connector`：目标连接器编码

---

## 10. 表操作

### executeSqlQuery(cnNumber, sql, values?, types?) -> List\<Map>
执行 SQL 查询（元数据方案），最多返回 10,000 行或 20MB。

### restart(tableCopyLogId) -> Boolean
重试数据表复制日志。通过 `invokeMicroService('isc','dbc','IscTableCopyService','restart', ...)` 调用。

### startSyn(tableDiffId) -> Long
执行表结构同步（异步）。通过 `invokeMicroService('isc','dbc','IscTableDiffService','startSyn', ...)` 调用。

---

## 11. 外部 API 调用

### invokeExternalApi(number, args, caller) -> Object
调用已注册的外部系统 API。
- `number`：API 编码
- `args`：参数数组
- `caller`：调用方标识

### invokeScriptApi(number, args, caller) -> Object
调用自定义脚本 API。

### subscribe(solutionId) -> Map
同步订阅方案包。返回 `{success, msg}`。

---

## 12. 业务流关系查询（BusinessFlowDataService）

### BusinessFlowDataService.isPush(entityNumber, billId) -> Boolean
判断单据是否已下推。也可判断分录行：`isPush(entityNumber, entryKey, billId, entryId)`。

### BusinessFlowDataService.loadBillLinkUp(entityNumber, billIds, onlyDirtSource) -> List
上查单据级关联关系。`onlyDirtSource` 为 true 只查直接来源。

### BusinessFlowDataService.findSourceBills(entityNumber, billIds) -> Map
查找上游关联单据（跨层级），按源实体分组返回。

### BusinessFlowDataService.loadBillLinkUpNodes(entityNumber, billIds, onlyDirtSource) -> Map
上查上游关联追溯树（树形结构）。

---

## 13. MinIO 对象存储

> 需要 MinIO 连接资源。

```
MinIO.getBytes(cn, bucketName, fileName) -> byte[]           # 下载文件
MinIO.getString(cn, bucketName, fileName, charset) -> String  # 下载文本文件
MinIO.fileExists(cn, bucketName, fileName) -> Boolean         # 文件是否存在
MinIO.folderExists(cn, bucketName, folderName) -> Boolean     # 目录是否存在
MinIO.bucketExists(cn, bucketName) -> Boolean                 # 桶是否存在
MinIO.removeBucket(cn, bucketName) -> Boolean                 # 删除桶（需为空）
MinIO.removeFile(cn, bucketName, fileName) -> Boolean         # 删除文件
```

```javascript
// 下载文件
var bytes = MinIO.getBytes(cn, "isc", "test/readme.txt");
var content = MinIO.getString(cn, "isc", "readme.txt", "utf8");

// 检查存在
if(MinIO.fileExists(cn, "isc", "data.csv")) {
    var data = MinIO.getBytes(cn, "isc", "data.csv");
}
```

---

## 14. LDAP 目录

> 需要 LDAP 连接资源。

### Ldap.list(cn) -> List\<String>
获取 LDAP 基础 DN 的直接子项名称列表。

### Ldap.search(cn, filter, searchScope?) -> List
搜索 LDAP 目录。
- `filter`：LDAP 过滤条件（如 `"objectClass=Person"`）
- `searchScope`：搜索范围（0=BASE, 1=ONELEVEL, 2=SUBTREE，默认 2）
```javascript
var result = Ldap.search(cn, "objectClass=Person");
```

---

## 15. 邮件

### smtp_send(emailCn, toEmailMap, billMap) -> Boolean
通过 SMTP 发送邮件。
- `emailCn`：SMTP 连接别名（String）
- `toEmailMap`：邮件信息 Map（`to`, `cc`, `subject`, `content`）
- `billMap`：苍穹单据附件信息 Map（`entityName`, `id`, `attField`, `attPanel`）
```javascript
var toEmail = {to: "test@qq.com", cc: "admin@qq.com", subject: "测试", content: "正文"};
var bill = {entityName: "isc_demo_basedata_1", id: billId, attField: "file", attPanel: "panel"};
smtp_send(emailCn, toEmail, bill);
```

### imap_receive(emailCn, messageID) -> Map
通过 IMAP 接收并解析指定邮件。
- `messageID`：邮件 Message-ID
- 返回包含邮件内容、附件、头部信息的 Map

---

## 16. HTTP 扩展

### HttpAccess2(url, method, data, charset, cookies, headers, timeout?) -> Map
HTTP 请求（字节数组请求/响应）。
- `data`：请求体 byte[]
- 返回 Map 含 `result`（byte[]）、`headers`、`cookies`
- 部分运行时返回中还可能包含 `responseCode`
```javascript
var data = String.getBytes(FastJsonFormat({id: "123"}), "UTF-8");
var result = HttpAccess2(url, "POST", data, "UTF-8", null,
    {"Content-Type": "application/json"});
var bytes = result.result;
```

---

## 17. 系统工具

### System[key] -> Object
访问系统变量。
```javascript
var host = System['YunZhiJiaAppHost'];
var keys = System['keys'];  // 获取所有可用 key
```

### ClassPath(className) -> String
获取类文件绝对路径。

### ClassInfo(className?) -> Map
获取类信息。返回 `{url: String}`。

### ThreadStack(filter) -> Map
获取集群节点线程堆栈信息。filter 支持 name, is_alive, state, priority, is_daemon。
```javascript
var stacks = ThreadStack("is_alive == true && priority >= 5");
```

### to_eas_id(value, bostype) -> String
生成 EAS 业务对象 ID（幂等）。

### DataFile.uploadFile2(map) -> String
上传文件到苍穹文件服务器。
- `map`：含 `fileName`、`content`（byte[]）、`appId`、`formId`、`pkId`（可选）
- 返回文件 URL
```javascript
var map = {fileName: "1.txt", content: String.getBytes("1234", "utf-8"),
    appId: "iscb", formId: "isc_demo_basedata_1"};
var url = DataFile.uploadFile2(map);
```

---

## 18. ClickHouse 函数

### 旧版 API（8.0 以前）
```
ClickHouse.insert(cn, table, columns, data) -> void    # 批量插入
ClickHouse.query(cn, sql) -> List<Map>                  # 查询
ClickHouse.update(cn, sql) -> int                       # 更新
ClickHouse.delete(cn, sql) -> int                       # 删除
ClickHouse.reader(cn, sql) -> ClickHouseReader          # 流式读取
```

### 新版 API（8.0+）
```
ClickHouseClient.insert(cn, table, columns, data) -> void
ClickHouseClient.query(cn, sql) -> List<Map>
ClickHouseClient.update(cn, sql) -> int
ClickHouseClient.delete(cn, sql) -> int
ClickHouseClient.reader(cn, sql) -> ClickHouseReader
```

---

## 19. MongoDB 函数

```
Mongo.insert(cn, collection, doc) -> void               # 插入文档
Mongo.query(cn, collection, filter, projection?) -> List<Map>  # 查询
Mongo.update(cn, collection, filter, update) -> int      # 更新
Mongo.count(cn, collection, filter?) -> long             # 计数
Mongo.batchUpdate(cn, collection, operations) -> int     # 批量更新
Mongo.delete(cn, collection, filter) -> int              # 删除
```
