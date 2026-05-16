# ISCB 脚本常见业务模式

> 默认先写**干净、简洁、最小必要**的脚本。
> 若用户已经给了变量名、列表或对象结构，就直接沿用，不额外包 `input` / `target` 外壳。
> 本文中带有 `$src`、`$tar`、`$this`、`tar`、`$cn`、`cn`、`$process` 的示例，仅在用户明确说明对应平台上下文时再使用。

## 0. 默认简洁写法

### 0.1 直接处理用户给定列表
```javascript
var inputList = [
    {ProductCode: 'MAT-001', Name: '物料A', UnitPrice: '99.90'},
    {ProductCode: 'MAT-002', Name: '物料B', UnitPrice: '128.00'}
];

var materialList = inputList
    .filter(ProductCode != null && Name != null)
    .each(
        number: ProductCode,
        name: Name,
        price: Number.test(UnitPrice) ? N(UnitPrice) : null
    );

return materialList;
```

### 0.2 直接处理单个对象
```javascript
var item = {code: 'C001', name: '分类A', enabled: 'true'};

var result = {
    number: item.code,
    name: item.name,
    isEnable: X(item.enabled)
};

return result;
```

## 1. 数据库查询与处理

### 1.1 嵌入式 SQL 查询 + 流式处理（仅值转换规则/数据集成方案）
```javascript
// 查询源系统用户列表
SELECT @@users[] = (fid, fnumber as "number", fname as name)
    FROM $src.t_pm_user@basedata WHERE fislocked = 0;

// 按部门分组，每组拼接姓名
var result = users.group(department).each(value.concat(name, ","));
return result;
```

### 1.2 SQL 函数查询（参数化，需连接资源）
```javascript
var sql = "SELECT fid, fnumber FROM T_PM_USER WHERE fnumber = ?";
var user = query_row($src, sql, ['administrator'], [VARCHAR]);
// user: {fid: xxx, fnumber: 'administrator'}（key 总是小写）

// 查询列表
var sql2 = "SELECT fid FROM T_PM_USER WHERE fislocked = 0";
var list = query_list($src, sql2);

// 查询单值
var id = query_value($this, "SELECT fid FROM T_PM_USER WHERE fnumber = ?", ['admin'], [VARCHAR]);

// 查询单列
var ids = query_column($src, "SELECT fid FROM T_PM_USER WHERE fislocked = 0");
```

### 1.3 数据写入（仅限目标数据处理脚本/自定义API/服务流程脚本节点）
```javascript
// 单条写入
var sql = "INSERT INTO t_demo(fid, fnumber, fname) VALUES(?, ?, ?)";
var affected = execute_update(cn, sql, [1, 'A', 'a'], [BIGINT, VARCHAR, VARCHAR]);

// 批量写入
var sql = "INSERT INTO t_demo(fid, fnumber, fname) VALUES(?, ?, ?)";
var batch = [[1, 'A', 'a'], [2, 'B', 'b'], [3, 'C', 'c']];
var affected = execute_batch(cn, sql, batch, [BIGINT, VARCHAR, VARCHAR]);
```

---

## 2. HTTP 集成

### 2.1 基本 HTTP 调用
```javascript
// GET 请求
var response = HttpGet(
    "https://api.example.com/data",
    {id: "123"},
    "UTF-8",
    null,
    {"Accept": "application/json"}
);
var data = String.ParseJson(response.result);

// POST 请求（JSON 格式）
var body = String.FormatJson({name: 'test', value: 123});
var response = HttpPost(
    "https://api.example.com/save",
    body,
    "UTF-8",
    null,
    {"Content-Type": "application/json"}
);
var saved = String.ParseJson(response.result);
```

### 2.2 通用 HTTP 访问
```javascript
// 通用 HTTP 请求
var result = HttpAccess(
    "https://api.example.com/data",
    "GET",
    {id: "123"},
    "UTF-8",
    null,
    {"Accept": "application/json"},
    30000
);
// result 是 Map 类型，常见字段包含 result、headers、cookies

// POST with headers
var body = String.FormatJson({key: 'value'});
var result = HttpAccess(
    "https://api.example.com/save",
    "POST",
    body,
    "UTF-8",
    null,
    {"Content-Type": "application/json"},
    30000
);
```

### 2.3 文件下载/上传
```javascript
// 下载文件
var fileBytes = HttpDownloadFile("https://example.com/file.xlsx");

// 上传文件
var response = HttpUploadFile(
    "https://example.com/upload",
    fileBytes,
    "data.xlsx",
    {param1: 'value1'},
    {Authorization: 'Bearer <ACCESS_TOKEN>'}
);
```

### 2.4 Multipart 表单提交（平台层）
```javascript
var formData = {
    file: fileBytes,
    fileName: 'data.xlsx',
    param1: 'value1'
};
var result = Http.sendMultipart($cn, "/upload", "POST", formData, "UTF-8", null, {});
```

### 2.5 PATCH 请求（平台层）
```javascript
var body = FastJsonFormat({status: 'updated'});
var result = ApacheHttpPatch("https://api.example.com/resource/1", body, "UTF-8",
    "Content-Type", "application/json",
    "Authorization", "Bearer <ACCESS_TOKEN>");
```

---

## 3. 数据转换

### 3.1 列表投影（提取部分属性）
```javascript
var list = [{name: 'Sky', subject: 'math', score: 95},
            {name: 'Star', subject: 'art', score: 99}];
var names = list.each(name: name, score: score);
// [{name: 'Sky', score: 95}, {name: 'Star', score: 99}]
```

### 3.2 列表 → Map（建索引）
```javascript
var list = [{id: 1, name: 'A'}, {id: 2, name: 'B'}];
var index = list.mapping(id, name);
// {1: 'A', 2: 'B'}
```

### 3.3 分组汇总
```javascript
var orders = [{dept: 'sales', amount: 100}, {dept: 'sales', amount: 200}, {dept: 'hr', amount: 50}];
var summary = orders.group(dept).each(value.sum(amount));
// {sales: 300, hr: 50}
```

### 3.4 嵌套遍历（分录处理，仅明确是目标单上下文时使用）
```javascript
// 遍历目标单分录并赋值
tar.segEntry.each(
    $.programmingContractIds = _.sections[$key]
);
```

### 3.5 序号生成
```javascript
var list = ['Sky', 'Star', 'Denver'];
var result = list.each(seq: ++_.index, name: $);
// [{seq:1, name:'Sky'}, {seq:2, name:'Star'}, {seq:3, name:'Denver'}]
```

---

## 4. 加密与编码

### 4.1 哈希
```javascript
var hash = Hash.SHA256("hello");
var md5 = Hash.MD5("data");
```

### 4.2 HMAC 签名
```javascript
var signature = Hash.HmacSHA256(
    String.getBytes("data", "UTF-8"),
    String.getBytes("<SECRET_KEY>", "UTF-8"));
var base64Sig = Base64Encode(signature);
```

### 4.3 AES 加解密
```javascript
var data = String.getBytes("hello", "UTF-8");
var encrypted = AES_ECB_PKCS5("0123456789abcdef", data);
var decrypted = AES_ECB_PKCS5_Decrypt("0123456789abcdef", encrypted);
```

### 4.4 RSA 加解密（平台层）
```javascript
var encrypted = RSA_Encrypt("plaintext", publicKey);
var decrypted = RSA_Decrypt(encrypted, privateKey);
```

### 4.5 Base64
```javascript
var bytes = String.getBytes("hello", "UTF-8");
var encoded = Base64Encode(bytes);     // "aGVsbG8="
var decoded = Base64Decode(encoded);    // byte[]
```

---

## 5. 文件操作（平台层）

### 5.1 读写 Excel
```javascript
// 读取
var bytes = HttpDownloadFile("https://example.com/data.xlsx");
var data = readXLSX(bytes);            // List<Map>
var sheet2 = readXLSX(bytes, 1);       // 第二个工作表

// 写入
var data = [{name: 'A', value: 1}, {name: 'B', value: 2}];
var xlsxBytes = writeXLSX(data);
```

### 5.2 读写 CSV
```javascript
// 假设 ftpCn 已绑定为 FTP/SFTP 连接别名

// 读取
var bytes = Ftp.getBytes(ftpCn, "/data", "file.csv");
var data = readCSV(bytes, ",", true);

// 写入
var csvBytes = writeCSV(data, ",", true);
Ftp.putBytes(ftpCn, "/output", "result.csv", csvBytes, true);
```

---

## 6. FTP 操作（平台层）

```javascript
// 假设 ftpCn 已绑定为 FTP/SFTP 连接别名

// 列出目录
var files = Ftp.list(ftpCn, "/data", null);

// 读取文件
if(Ftp.exists(ftpCn, "/data/input.txt")) {
    var content = Ftp.getString(ftpCn, "/data", "input.txt", "UTF-8");
}

// 写入文件
Ftp.putBytes(ftpCn, "/output", "result.dat", resultBytes, true);

// 创建/删除目录
Ftp.mkdir(ftpCn, "/output/new_dir");
Ftp.rmdir(ftpCn, "/output/old_dir");
```

---

## 7. JSON 处理

### 7.1 解析与格式化
```javascript
var jsonStr = '{"name":"test","value":123}';
var obj = FastJsonParse(jsonStr);
println(obj.name);  // "test"

var newJson = FastJsonFormat(obj);
```

### 7.2 复杂对象转换
```javascript
var map = flatObjectToMapOrList(complexObject);
```

---

## 8. 工作流操作（平台层）

```javascript
// 发起工作流
var result = initiateWorkflow($cn, "entity_name", "operation", [id1, id2], "admin");

// 查询工作流状态
var states = queryWorkflowState($cn, "entity_name", "operation", [id1, id2]);

// 获取工作流状态
var states = getWorkflowState($cn, [id1, id2]);
```

---

## 9. 错误处理模式

```javascript
try {
    var result = HttpAccess(
        "https://api.example.com/data",
        "GET",
        null,
        "UTF-8",
        null,
        {"Accept": "application/json"},
        30000
    );
    if(result == null) {
        throw "API returned null";
    }
    var data = String.ParseJson(result.result);
    return data;
} catch(e) {
    println("Error: " + e);
    return null;
} finally {
    // 清理逻辑
}
```

---

## 10. 综合示例：数据集成方案（仅明确是该上下文时使用）

```javascript
// 1. 查询源系统数据
SELECT @@orders[] = (fid, fnumber, fdate, famount)
    FROM $src.t_sal_order@scm WHERE fdate >= @@startDate :: TIMESTAMP;

if(orders is Empty) { return; }

// 2. 数据转换（金额汇率转换）
var rate = query_value($this, "SELECT frate FROM t_exchange_rate WHERE fcurrency = ?",
    ['USD'], [VARCHAR]);

var converted = orders.each(
    number: fnumber,
    date: Date.format(fdate, 'yyyy-MM-dd'),
    amount: N(famount) * N(rate),
    amountCN: Number.capital(N(famount) * N(rate))
);

// 3. 按日期分组统计
var daily = converted.group(date).each(
    date: $key,
    total: value.sum(amount),
    count: value.count(amount)
);

// 4. 写入目标系统
for(row : daily) {
    var sql = "INSERT INTO t_daily_summary(fdate, ftotal, fcount) VALUES(?, ?, ?)";
    execute_update($tar, sql, [T(row.date), row.total, I(row.count)],
        [TIMESTAMP, DECIMAL, INTEGER]);
}
```
