# ISCB 平台层函数详细文档

> 平台层函数依赖苍穹平台环境，需在苍穹运行时中执行。
> 仅当用户明确说明平台节点/资源/上下文，或需求本身必须使用平台层函数时，再把本文件作为主要参考。
> 不要把本文件中的 `cn`、`$cn`、`$src`、`$tar`、`tar` 等示例，当成普通脚本的默认起手变量。

---

## 1. ID 生成

### new_int_id() -> Long
生成分布式唯一长整数 ID。适用于数据库主键。
```javascript
var id = new_int_id();
execute_update(cn, "INSERT INTO t_demo(fid, fname) VALUES(?, ?)",
    [id, 'test'], [BIGINT, VARCHAR]);
```

### new_uuid() -> String
生成 UUID 字符串（标准格式含连字符）。
```javascript
var uuid = new_uuid();  // "550e8400-e29b-41d4-a716-446655440000"
```

### new_boid(type) -> String
生成业务对象 ID（BOS 架构专用）。
- `type`：十六进制类型标识字符串
```javascript
var boid = new_boid("01020304");
```

---

## 2. 上下文与环境

### GetContext() -> Map
获取当前请求上下文信息。返回 Map 包含：

| 字段 | 说明 |
|------|------|
| `userId` | 当前用户 ID |
| `userName` | 用户名 |
| `userOpenId` | 开放平台用户 ID |
| `userType` | 用户类型 |
| `uid` | 用户标识 |
| `lang` | 语言设置 |
| `loginOrg` | 登录组织 |
| `orgId` | 组织 ID |
| `traceId` | 请求追踪 ID |
| `tenantId` | 租户 ID |
| `accountId` | 账户 ID |
| `userAgent` | 用户代理 |

```javascript
var ctx = GetContext();
var userId = ctx.userId;
var orgId = ctx.orgId;
```

### WithContext(options) { body }
切换用户/组织上下文执行代码块。
- `userId`（Long，**必填**）：目标用户 ID
- `orgId`（Long，可选）：组织 ID
- `lang`（String，可选）：语言（"ZH_CN", "EN_US" 等）

执行完毕后自动恢复原上下文。userId 不传会抛异常。

```javascript
WithContext(userId: 123456, orgId: 789) {
    // 以用户 123456 的身份执行
    var data = query_list(cn, "SELECT * FROM t_order WHERE fcreator = ?",
        [L(123456)], [BIGINT]);
};
```

### THIS_URL -> String
系统变量，当前苍穹服务器 URL。
```javascript
var callbackUrl = THIS_URL + "/api/callback";
```

### ISC_ENV -> Context
环境变量上下文，访问平台配置的环境变量。
- 通过属性名访问：`ISC_ENV.API_KEY`
- 变量不存在会抛异常，建议先检查
```javascript
var apiKey = ISC_ENV.API_KEY;
```

### CheckCancelSignal() -> void
检查取消信号。长时间运行的脚本应定期调用，如果用户取消会抛出 TaskCancelException。
```javascript
for(item : largeList) {
    CheckCancelSignal();
    processItem(item);
}
```

---

## 3. JSON

### FastJsonFormat(obj) -> String
对象转 JSON 字符串。
- 保留 null 值（WriteMapNullValue）
- BigDecimal 输出为普通数字（不用科学计数法）
- 日期使用标准格式
```javascript
var json = FastJsonFormat({name: 'test', value: null, amount: N('123.456')});
// {"name":"test","value":null,"amount":123.456}
```

### FastJsonParse(str) -> Object
JSON 字符串转对象。
- 小数解析为 BigDecimal（保持精度）
- 启用安全模式
```javascript
var obj = FastJsonParse('{"name":"test","amount":123.456}');
var name = obj.name;      // "test"
var amount = obj.amount;  // BigDecimal 123.456
```

### flatObjectToMapOrList(obj) -> Map|List
复杂对象（特别是 DynamicObject）转 Map/List。
- String 输入：当作 JSON 解析
- DynamicObject 输入：序列化为 JSON 后再解析
- null 输入返回 null
```javascript
var plainMap = flatObjectToMapOrList(dynamicObject);
```

---

## 4. 工作流

### initiateWorkflow(cn, entity, operation, idList, proxyUser, extendInfo?) -> List
发起外部系统工作流。
- `cn`：外部系统连接（ConnectionWrapper，**必填**）
- `entity`：实体编码（String）
- `operation`：工作流操作名（String）
- `idList`：单据 ID 列表（List 或单个值）
- `proxyUser`：代理用户（String）
- `extendInfo`：扩展信息（Map，可选）

返回 WorkflowInfo 列表（异步工作流可能返回空列表，需用 queryWorkflowState 轮询）。

```javascript
var result = initiateWorkflow(cn, "purchase_order", "submit",
    ["PO001", "PO002"], "admin@domain.com", {note: "batch approve"});
```

### queryWorkflowState(cn, entity, operation, idList) -> List
查询工作流状态（按实体+操作+ID）。
```javascript
var states = queryWorkflowState(cn, "purchase_order", "submit", ["PO001"]);
```

### getWorkflowState(cn, idList) -> List
查询工作流状态（按工作流实例 ID）。
```javascript
var states = getWorkflowState(cn, ["instance_001", "instance_002"]);
```

---

## 5. 文件读写

### readXLSX(bytes, sheetIndex?) -> List|Map
读取 Excel 文件。
- `bytes`（byte[]，**必填**）：Excel 文件字节数组
- `sheetIndex`（Integer，可选）：工作表索引（0-based）
- 指定 sheetIndex：返回 `List<List<Object>>`（二维数组）
- 不指定 sheetIndex：返回 `Map<String, List<List<Object>>>`（工作表名 → 二维数组）
- 默认读第 0 个工作表

```javascript
// 读取第一个工作表
var data = readXLSX(fileBytes, 0);
for(row : data) {
    println(row[0] + " - " + row[1]);
}

// 读取所有工作表
var allSheets = readXLSX(fileBytes);
// allSheets: {Sheet1: [[...], [...]], Sheet2: [[...], [...]]}
```

### writeXLSX(data) -> byte[]
写入 Excel 文件。
- 单工作表：传入 `Collection<List<Object>>`（行列表）
- 多工作表：传入 `Map<String, Collection<List<Object>>>`（表名 → 行列表）

```javascript
// 单工作表
var rows = [["姓名", "年龄"], ["张三", 30], ["李四", 25]];
var xlsxBytes = writeXLSX(rows);

// 多工作表
var data = {
    "员工": [["姓名", "部门"], ["张三", "研发"]],
    "部门": [["编码", "名称"], ["DEV", "研发部"]]
};
var xlsxBytes = writeXLSX(data);
```

### readCSV(bytes, delimiter?, hasQuot?) -> List
读取 CSV 文件。
- `bytes`（byte[]，**必填**）：CSV 文件字节数组
- `delimiter`（String，可选）：分隔符，默认 ","
- `hasQuot`（boolean，可选）：是否有引号包裹，默认 false

```javascript
var data = readCSV(fileBytes);                // 逗号分隔
var data = readCSV(fileBytes, "\t", false);   // Tab 分隔
var data = readCSV(fileBytes, ",", true);     // 有引号字段
```

### writeCSV(data, delimiter?, hasQuot?) -> byte[]
写入 CSV 文件。
- `data`（Collection<List<Object>>）：行数据列表
- `delimiter`（String，可选）：分隔符，默认 ","
- `hasQuot`（boolean，可选）：是否用引号包裹，默认 false

```javascript
var rows = [["姓名", "年龄", "城市"], ["张三", 30, "北京"]];
var csvBytes = writeCSV(rows);
var csvBytes = writeCSV(rows, "\t", true);  // Tab 分隔 + 引号
```

---

## 6. 加密

### RSA_Encrypt(plaintext, secretKey, isPrivate?) -> String
RSA 加密。
- `plaintext`（String）：待加密数据
- `secretKey`（String）：密钥（PEM 格式，自动去除头尾标记和空白）
- `isPrivate`（boolean，可选）：是否用私钥加密，默认 false（公钥加密）
- 返回 Base64 编码的密文

自动处理的 PEM 头尾标记：
- `-----BEGIN/END PUBLIC KEY-----`
- `-----BEGIN/END PRIVATE KEY-----`
- `-----BEGIN/END RSA PRIVATE KEY-----`
- `-----BEGIN/END RSA PUBLIC KEY-----`

```javascript
var encrypted = RSA_Encrypt("sensitive data", publicKey);
var encrypted2 = RSA_Encrypt("data", privateKey, true);  // 私钥加密
```

### RSA_Decrypt(ciphertext, secretKey, isPublic?) -> String
RSA 解密。
- `ciphertext`（String）：Base64 编码的密文
- `secretKey`（String）：密钥
- `isPublic`（boolean，可选）：是否用公钥解密，默认 false（私钥解密）

```javascript
var decrypted = RSA_Decrypt(encryptedData, privateKey);
var decrypted2 = RSA_Decrypt(encryptedData, publicKey, true);  // 公钥解密
```

### SM4_Encrypt(plaintext, secretKey) -> String
SM4 国密加密（对称加密，128 位密钥）。
- `plaintext`（String）：待加密数据
- `secretKey`（String）：16 字节密钥
```javascript
var encrypted = SM4_Encrypt("sensitive data", "0123456789abcdef");
```

### SM4_Decrypt(ciphertext, secretKey) -> String
SM4 国密解密。
```javascript
var decrypted = SM4_Decrypt(encryptedData, "0123456789abcdef");
```

---

## 7. FTP 工具包

> 以下目录/文件级 `Ftp.*` 函数都需要显式传入 FTP/SFTP 连接参数（下文统一记为 `ftpCn`）。
> `Ftp.readLine` 和 `Ftp.readRow` 只消费 `Ftp.getInputStream(...)` 返回的流对象，不再接收连接参数。

### Ftp.list(ftpCn, dirPath, type?) -> List\<Map>
列出指定目录下的文件和目录信息。
- `ftpCn`：FTP 系统连接别名
- `dirPath`：FTP 目录路径
- `type`：过滤类型，支持 `null`、`"FILE"`、`"DIR"`；`null` 表示返回所有文件和目录
- 返回 Map 列表，每个 Map 含 `fileName`、`modifyTime`、`fileSize`、`fileExt`、`type`

```javascript
var files = Ftp.list(ftpCn, "/data", "FILE");
for(f : files) {
    println(f.fileName + " (" + f.fileSize + " bytes)");
}
```

### Ftp.exists(ftpCn, dirPath) -> Boolean
检查目录或文件是否存在。
- `ftpCn`：FTP 系统连接别名
- `dirPath`：FTP 目录路径（目录通常以 `/` 结尾）或文件完整路径

```javascript
if(Ftp.exists(ftpCn, "/data/input.txt")) {
    var content = Ftp.getString(ftpCn, "/data", "input.txt", "UTF-8");
}
```

### Ftp.getBytes(ftpCn, dirPath, fileName) -> byte[]
下载文件为字节数组（二进制模式）。
- `ftpCn`：FTP 系统连接别名
- `dirPath`：FTP 目录路径
- `fileName`：文件名

```javascript
var fileBytes = Ftp.getBytes(ftpCn, "/download", "document.pdf");
```

### Ftp.getString(ftpCn, dirPath, fileName, charset) -> String
下载文本文件并按指定编码解码。
- `ftpCn`：FTP 系统连接别名
- `dirPath`：FTP 目录路径
- `fileName`：文件名
- `charset`：编码格式（`"UTF-8"`、`"GBK"`、`"ISO-8859-1"` 等）

```javascript
var content = Ftp.getString(ftpCn, "/config", "settings.txt", "UTF-8");
```

### Ftp.getInputStream(ftpCn, dirPath, fileName, bufferSize?, keepBreakpoint?) -> FtpByteStream
获取 FTP 文件输入流（适合大文件）。
- `ftpCn`：FTP/SFTP 连接别名
- `dirPath`：文件目录路径
- `fileName`：文件名
- `bufferSize`：缓冲区大小（字节），默认 2MB；帮助手册标注范围为 `1048576 ~ 8388608`
- `keepBreakpoint`：是否保留断点，默认 `false`

```javascript
var stream = Ftp.getInputStream(ftpCn, "/large", "bigfile.iso");
var resumableStream = Ftp.getInputStream(ftpCn, "/large", "bigfile.iso", 1048576, true);
```

### Ftp.putBytes(ftpCn, dirPath, fileName, data, isUpdate?) -> boolean
上传字节数组到 FTP。
- `ftpCn`：FTP 系统连接别名
- `dirPath`：FTP 目录路径
- `fileName`：文件名
- `data`：文件内容（`byte[]`）
- `isUpdate`：文件存在时是否覆盖，默认 `false`

```javascript
Ftp.putBytes(ftpCn, "/upload", "result.xlsx", xlsxBytes, true);
```

### Ftp.putInputStream(ftpCn, dirPath, fileName, stream, isUpdate?) -> boolean
上传输入流到 FTP（适合大文件，不占内存）。
- `ftpCn`：FTP/SFTP 连接别名
- `dirPath`：文件目录路径
- `fileName`：文件名
- `stream`：输入流，可来自 `Ftp.getInputStream(...)`
- `isUpdate`：文件存在时是否更新
- 使用 apache(ftp) 连接时，返回 `true` 表示上传成功；其他 FTP 连接类型的返回值可能没有明确语义

```javascript
var sourceStream = Ftp.getInputStream(sourceFtpCn, "/", "test.txt", 3000000);
Ftp.putInputStream(targetFtpCn, "/", "test.txt", sourceStream, true);
```

### Ftp.delete(ftpCn, dirPath, fileName) -> boolean
删除指定目录下的文件。
- `ftpCn`：FTP 系统连接别名
- `dirPath`：FTP 目录路径
- `fileName`：文件名

```javascript
Ftp.delete(ftpCn, "/temp", "oldfile.txt");
```

### Ftp.mkdir(ftpCn, dirPath) -> boolean
创建目录。
- `ftpCn`：FTP 系统连接别名
- `dirPath`：FTP 目录路径

```javascript
Ftp.mkdir(ftpCn, "/output/new_dir");
```

### Ftp.rmdir(ftpCn, dirPath) -> boolean
删除指定目录及其所有子文件和子目录。
- `ftpCn`：FTP 系统连接别名
- `dirPath`：FTP 目录路径

```javascript
Ftp.rmdir(ftpCn, "/output/old_dir");
```

### Ftp.readLine(inputStream, charset?) -> String
从流中读取一行文本。到达末尾返回 `null`，遇到空行会自动跳过。
- `inputStream`：`Ftp.getInputStream(...)` 返回的流对象
- `charset`：字符集，默认 `UTF-8`，仅支持 `UTF-8` / `GBK` / `ISO-8859-1`

```javascript
var stream = Ftp.getInputStream(ftpCn, "/data", "records.txt");
var line;
while((line = Ftp.readLine(stream, "GBK")) != null) {
    println(line);
}
```

### Ftp.readRow(inputStream, delimiter?, charset?) -> List
从 CSV 文件输入流读取一行数据并按分隔符拆分为列表；文件结束时返回 `null`。
- `inputStream`：`Ftp.getInputStream(...)` 返回的流对象
- `delimiter`：分隔字符，默认 `,`
- `charset`：字符集，默认 `UTF-8`

```javascript
var stream = Ftp.getInputStream(ftpCn, "/", "user.csv", 1000000);
var row = Ftp.readRow(stream);
```

---

## 8. DataFile 工具包

数据文件管理，用于数据迁移和文件附件场景。

### DataFile.createJob() -> Job
创建数据文件迁移任务。

### DataFile.attach(jobId, fileInfo) -> Boolean
将文件关联到迁移任务。

### DataFile.start(jobId) -> Boolean
启动迁移任务。

### DataFile.getBytes(fileId) -> byte[]
按文件 ID 获取文件字节。

### DataFile.uploadFile(fileInfo) -> String
上传文件并注册。

### DataFile.uploadAndBind(fileInfo, billId) -> String
上传文件并绑定到单据。

### DataFile.getState(jobId) -> String
获取任务执行状态。

### DataFile.getIerpFileInfoByBillId(billId) -> List
获取单据的附件信息列表。
```javascript
var attachments = DataFile.getIerpFileInfoByBillId(billId);
for(att : attachments) {
    println(att.fileName + " - " + att.fileSize);
}
```

---

## 9. 附件操作

### AttachPanel.removeAllByBillId(formId, billId) -> void
删除单据所有附件面板的全部附件。
- `formId`：表单标识（如 "isc_demo_basedata_1"）
- `billId`：单据 ID
```javascript
AttachPanel.removeAllByBillId("isc_demo_basedata_1", L(12345));
```

### AttachPanel.removeByAttachNumber(formId, billId, attachNumber) -> void
按附件编号删除单个附件。
- `attachNumber`：附件唯一编号（系统生成，如 "rc-upload-1669856264414-10"）
```javascript
AttachPanel.removeByAttachNumber("isc_demo_basedata_1", L(12345), "rc-upload-1669856264414-10");
```

### AttachField.removeByAttachPkId(entityNumber, tableName, pkIdList) -> void
按主键 ID 批量删除附件字段文件。
- `entityNumber`：实体标识
- `tableName`：附件字段对应的表名（来自元数据）
- `pkIdList`：bd_attachment 表主键 ID 列表（必须为 List）
```javascript
var ids = [L(1565113255142097920), L(1565108343368845313)];
AttachField.removeByAttachPkId("isc_demo_basedata_1", "t_isc_demo1_file", ids);
```

### AttachField.removeByAttachUid(entityNumber, tableName, attachmentMap) -> void
按 UID 删除单个附件字段文件。
- `attachmentMap`：必须为 Map，包含 `uid` 字段
```javascript
AttachField.removeByAttachUid("isc_demo_basedata_1", "t_isc_demo1_file",
    {uid: "rc-upload-1670978268054-9"});
```

---

## 10. HTTP 扩展

### Http.sendMultipart(cn, path, method, formData, charset, cookies?, headers?, timeout?) -> Map
发送 multipart/form-data 请求（文件上传）。
- `cn`：HTTP 连接器（HttpConnectionWrapper）
- `path`：相对路径（自动拼接连接器的 website URL）
- `method`：HTTP 方法（POST, PUT 等）
- `formData`：表单数据 Map（值以 "@IERP:" 开头表示苍穹附件引用）
- `charset`：编码（如 "utf-8"）
- `cookies`：Cookie Map（可选，null 表示无 cookie）
- `headers`：请求头 Map（可选）
- `timeout`：超时毫秒数（可选，默认 300000ms，最大可扩展到系统默认的 3 倍）

自动处理 Content-Type 和 boundary。返回含 `code`, `cookies`, `headers`, `body` 的 Map。

```javascript
var form = {
    name: "John",
    email: "john@example.com",
    file: "@IERP:12345"  // 苍穹附件引用
};
var result = Http.sendMultipart($cn, "/api/upload", "POST", form, "utf-8",
    null, {Authorization: "Bearer <ACCESS_TOKEN>"}, 60000);
println("状态: " + result.code);
println("响应: " + result.body);
```

### ApacheHttpPatch(url, data, charset, ...headers) -> Object
HTTP PATCH 请求（使用 Apache HttpClient，支持 PATCH 方法）。
- `url`：完整 URL
- `data`：请求体
- `charset`：编码
- `headers`：请求头（变长参数，按 key, value 交替传入）

```javascript
var body = FastJsonFormat({status: 'updated'});
var result = ApacheHttpPatch("https://api.example.com/resource/1", body, "UTF-8",
    "Content-Type", "application/json",
    "Authorization", "Bearer <ACCESS_TOKEN>");
```

### MapToURLEncodeString(map) -> String
Map 转 URL 编码查询字符串。null 输入返回 null。
```javascript
var params = {username: "john@example.com", password: "<PASSWORD>"};
var encoded = MapToURLEncodeString(params);
// "username=john%40example.com&password=%3CPASSWORD%3E"
```

### ConvertToUrlEncodeString(fieldName, values) -> String
字段名+值转 URL 编码字符串。支持多值参数。
```javascript
ConvertToUrlEncodeString("status", "active")        // "status=active"
ConvertToUrlEncodeString("id", [1, 2, 3])           // "id=1&id=2&id=3"
```

---

## 11. 解析与工具

### parseJsoup(html) -> NodeList
使用 Jsoup 解析 HTML/XML，返回 W3C DOM 节点列表。
```javascript
var dom = parseJsoup("<html><body><div class='content'>数据</div></body></html>");
```

### parseCron(expr, count?) -> Date|List
解析 Cron 表达式，计算下次执行时间。
- `expr`：Quartz 格式 Cron 表达式（6-7 个字段）
- `count`：计算未来多少次执行时间，默认 1（最大 50）
- count=1 返回单个 Date；count>1 返回 Date 列表

```javascript
var next = parseCron("0 0 12 * * ?");           // 下次中午12点
var nextFive = parseCron("0 0 9 ? * MON-FRI", 5); // 未来5个工作日上午9点
```

### getCreateTimeByCosmicId(id) -> Date
从 Cosmic ID 提取创建时间。
- `id`：Long 或 String 类型的 Cosmic ID
```javascript
var createTime = getCreateTimeByCosmicId(L(1234567890123456789));
println(Date.format(createTime, "yyyy-MM-dd HH:mm:ss"));
```

### getCosmicIDRangeByDate(date) -> Map
按日期获取 Cosmic ID 范围。返回 Map 含 `minId` 和 `maxId`。
```javascript
var range = getCosmicIDRangeByDate(Date.today());
// 查询今天创建的记录
var sql = "SELECT * FROM t_order WHERE fid >= ? AND fid <= ?";
var list = query_list(cn, sql, [range.minId, range.maxId], [BIGINT, BIGINT]);
```

---

## 12. 系统函数

### businessEventInvoke(eventCode, eventData) -> void
触发业务事件，通知所有已订阅的事件处理器。
- `eventCode`：事件编码（必须已在系统中注册）
- `eventData`：事件负载（会被序列化为 JSON）
```javascript
businessEventInvoke("purchase_order_approved", {
    orderId: 12345,
    status: "approved",
    approver: "admin"
});
```

### PermitServiceUpgrade(permitList) -> String
权限升级（三权分立场景）。
- `permitList`：权限升级规格列表，每项为 List：
  - [0] 旧实体标识
  - [1] 旧权限项
  - [2] 新实体标识
  - [3] 新权限项
  - [4]（可选）虚拟管理员 ID 数组

成功返回消息字符串，失败抛 IscBizException。

```javascript
var permits = [
    ["perm_busirole", "modify", "perm_busirole", "assign", [100, 101]],
    ["perm_employee", "read", "perm_employee", "read_detail"]
];
var result = PermitServiceUpgrade(permits);
```

### printCircuitBreakerInfo(timeSpan?) -> String
启动后台任务，每秒打印熔断器状态信息。
- `timeSpan`：监控持续毫秒数，默认 30000（30 秒），最大 60000（1 分钟）
- 同一时间只允许一个监控任务
- 输出到平台日志（INFO 级别）

```javascript
printCircuitBreakerInfo();        // 监控 30 秒
printCircuitBreakerInfo(10000);   // 监控 10 秒
```

---

## 13. 综合示例（仅明确平台上下文时使用）

### 示例 1：查询数据 + 生成 Excel + FTP 上传
```javascript
// 查询数据
var sql = "SELECT fnumber, fname, famount FROM t_order WHERE fdate >= ?";
var orders = query_list(cn, sql, [T('2024-01-01')], [TIMESTAMP]);

// 构造表头+数据
var rows = [["编号", "名称", "金额"]];
for(order : orders) {
    rows += [[order.fnumber, order.fname, order.famount]];
}

// 生成 Excel
var xlsxBytes = writeXLSX(rows);

// 上传到 FTP（ftpCn 为 FTP/SFTP 连接别名）
Ftp.putBytes(ftpCn, "/reports/", "orders_" + Date.format(Date.now(), "yyyyMMdd") + ".xlsx",
    xlsxBytes, true);
```

### 示例 2：HTTP API 调用 + 签名验证
```javascript
var timestamp = '' + Date.getTime();
var body = FastJsonFormat({orderId: 12345, status: 'confirm'});

// HMAC-SHA256 签名（注意：参数必须是 byte[]）
var signContent = "POST\n/api/order/confirm\n" + timestamp + "\n" + body;
var signature = Base64Encode(Hash.HmacSHA256(
    String.getBytes(signContent, "UTF-8"),
    String.getBytes("<SECRET_KEY>", "UTF-8")));

// 发送请求
var result = HttpAccess(
    "https://api.example.com/api/order/confirm",
    "POST",
    body,
    "UTF-8",
    null,
    {
        "Content-Type": "application/json",
        "X-Timestamp": timestamp,
        "X-Signature": signature
    },
    30000
);
if(result.responseCode == 200) {
    var response = String.ParseJson(result.result);
    println("成功: " + response.message);
}
```

### 示例 3：工作流发起 + 状态轮询
```javascript
// 发起工作流
var ids = query_column(cn, "SELECT fid FROM t_order WHERE fstatus = 'pending'");
if(ids is Empty) { return "无待审批单据"; }

var result = initiateWorkflow(cn, "sal_order", "submit", ids, "admin@company.com");

// 等待并查询状态（在服务流程中可用定时节点轮询）
var states = queryWorkflowState(cn, "sal_order", "submit", ids);
return states;
```
