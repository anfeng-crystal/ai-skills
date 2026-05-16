# ISCB 引擎层函数详细文档

> 引擎层函数不依赖苍穹平台，可独立运行。

---

## 1. Hash 工具包

### Hash.MD5(data) -> String
计算 MD5 哈希。返回 32 位十六进制小写字符串。
```javascript
Hash.MD5("hello")  // "5d41402abc4b2a76b9719d911017c592"
```

### Hash.SHA1(data) -> String
计算 SHA-1 哈希。返回 40 位十六进制字符串。

### Hash.SHA256(data) -> String
计算 SHA-256 哈希。返回 64 位十六进制字符串。
```javascript
var sign = Hash.SHA256("data to sign");
```

### Hash.SHA384(data) -> String
计算 SHA-384 哈希。返回 96 位十六进制字符串。

### Hash.CRC32(data) -> String
计算 CRC32 校验和。返回十六进制字符串。

### Hash.MUR(data) -> Number
计算 MurmurHash。返回数值。

### Hash.MUR16(data) -> Number
计算 MurmurHash，返回 16 位数值。

### Hash.MUR32(data) -> Number
计算 MurmurHash，返回 32 位数值。

### Hash.HmacMD5(data, key) -> byte[]
- `data`：**必须是 byte[]**，不能传 String
- `key`：**必须是 byte[]**，不能传 String
- 返回 byte[]，通常需 `Base64Encode()` 编码后使用
- **重要**：使用 `String.getBytes()` 将字符串转为 byte[] 后传入
```javascript
// 正确用法
var data = String.getBytes("hello", "UTF-8");
var key = String.getBytes("<SECRET_KEY>", "UTF-8");
var hmac = Hash.HmacMD5(data, key);
var result = Base64Encode(hmac);

// 错误用法（会抛出 IscBizException）
// Hash.HmacMD5("hello", "<SECRET_KEY>")  // 参数类型错误！
```

### Hash.HmacSHA1(data, key) -> byte[]
HMAC-SHA1 签名。**data 和 key 均必须为 byte[]**。
```javascript
var sig = Hash.HmacSHA1(String.getBytes(message, "UTF-8"), String.getBytes(secret, "UTF-8"));
```

### Hash.HmacSHA256(data, key) -> byte[]
HMAC-SHA256 签名。最常用的 API 签名算法。**data 和 key 均必须为 byte[]**。
```javascript
var sig = Hash.HmacSHA256(
    String.getBytes("request body", "UTF-8"),
    String.getBytes("<SECRET_KEY>", "UTF-8"));
var base64Sig = Base64Encode(sig);
```

### Hash.HmacSHA384(data, key) -> byte[]
HMAC-SHA384 签名。**data 和 key 均必须为 byte[]**。

### Hash.HmacSHA512(data, key) -> byte[]
HMAC-SHA512 签名。**data 和 key 均必须为 byte[]**。

> **已废弃别名**：`Hash.HMAC_SHA1()` → 请使用 `Hash.HmacSHA1()`；`Hash.HMAC_SHA256()` → 请使用 `Hash.HmacSHA256()`

### Hash.RSA_SHA256(data, privateKey) -> byte[]
RSA-SHA256 数字签名。
- `data`：待签名数据
- `privateKey`：RSA 私钥（PEM 格式）
```javascript
var sig = Hash.RSA_SHA256("data", privateKey);
var base64Sig = Base64Encode(sig);
```

### Hash.PseudoKey(data) -> String
生成伪密钥，用于数据脱敏/混淆。

---

## 2. String 工具包

### String.indexOf(str, sub, fromIndex?) -> int
查找子串首次出现位置。
- `fromIndex`：可选，起始搜索位置（默认 0）
- 未找到返回 -1；null 输入返回 -1
```javascript
String.indexOf("hello world", "world")    // 6
String.indexOf("hello world", "world", 7) // -1
```

### String.lastIndexOf(str, sub) -> int
查找子串最后出现位置。未找到返回 -1。

### String.lower(str) -> String
转小写。null 返回空字符串。
```javascript
String.lower("HELLO")  // "hello"
```

### String.upper(str) -> String
转大写。null 返回空字符串。

### String.trim(str) -> String
去除首尾空白。null 返回空字符串。

### String.rtrim(str) -> String
去除右侧空白。

### String.left(str, len) -> String
从左截取 len 个字符。超出长度返回完整字符串。

### String.right(str, len) -> String
从右截取 len 个字符。

### String.sub(str, start, end?) -> String
子串提取。
- `start`：起始索引（0-based）
- `end`：可选，结束索引（不包含）
- 也可用于 BinaryString
```javascript
String.sub("hello", 1, 3)  // "el"
String.sub("hello", 2)     // "llo"
```

### String.lpad(str, len, pad) -> String
左填充到指定长度。
```javascript
String.lpad("42", 5, "0")  // "00042"
```

### String.rpad(str, len, pad) -> String
右填充到指定长度。

### String.replace(str, pattern, replacement) -> String
替换所有匹配项（支持正则）。null 输入返回空字符串。
```javascript
String.replace("a-b-c", "-", "_")  // "a_b_c"
```

### String.split(str, delimiter?, limit?) -> String[]
分割字符串。
- `delimiter`：默认 ","
- `limit`：可选，最大分割数
- null 输入返回空数组
```javascript
String.split("a,b,c")          // ["a", "b", "c"]
String.split("a|b|c", "|")     // ["a", "b", "c"]
String.split("a,b,c,d", ",", 2)// ["a", "b,c,d"]
```

### String.join(separator, strings...) -> String
拼接字符串。
- 第一个参数为分隔符，后续为待拼接元素
- 支持传入集合或多个参数
- 可传入第三个参数为 getter 函数，从每个元素提取值
```javascript
String.join(",", "a", "b", "c")  // "a,b,c"
String.join("-", list)           // 列表元素用 - 连接
```

### String.space(count) -> String
生成指定数量的空格字符串。

### String.capital(amount) -> String
金额转中文大写（壹、贰...）。等价于 `Number.capital()`。

### String.valueOf(obj) -> String
对象转字符串表示。

### String.toString(obj, charset?) -> String
转字符串。如果 obj 是 byte[]，使用指定 charset 解码（默认 UTF-8）。

### String.getBytes(str, charset?) -> byte[]
字符串转字节数组。charset 默认 UTF-8。
```javascript
var bytes = String.getBytes("hello", "UTF-8");
```

### String.getBytes2(str, charset?) -> byte[]
字符串转字节数组。与 `getBytes` 类似，常用于需要显式 `byte[]` 的场景。
- `str`：输入字符串
- `charset`：编码格式（默认 UTF-8）
```javascript
var bytes = String.getBytes2("1234", "UTF-8");
var hmac = Hash.HmacSHA256(String.getBytes2("data", "UTF-8"), String.getBytes2("key", "UTF-8"));
```

### String.HTMLEncode(str) -> String
HTML 特殊字符编码（&, <, >, ", '）。

### String.URLEncode(str) -> String
URL 编码，使用 UTF-8。

### String.URLDecode(str) -> String
URL 解码，使用 UTF-8。

### String.ParseJson(jsonStr) -> Object
解析 JSON 字符串为对象/Map/List。等价于 `FastJsonParse()`。

### String.FormatJson(obj) -> String
对象转 JSON 字符串。Long 值转为字符串。等价于 `FastJsonFormat()`。

### String.FormatJson2(obj) -> String
对象转 JSON 字符串。**保留 Long 值为数字**（不转字符串）。

### String.parseXml(xmlStr) -> XMLObject
解析 XML 字符串为可操作的 XML 对象。

### String.PrettyXml(xmlStr) -> String
XML 美化格式化（缩进 + 换行）。

### String.createXml(name) -> XMLObject
创建新的 XML 文档，name 为根元素名。

### String.xml2Json(xml) -> Object
XML 转 JSON 对象。

### String.json2Xml(json, rootName) -> String
JSON 转 XML 字符串。rootName 为根元素名。

### String.Xml2JsonWithAttribute(xml) -> Object
XML 转 JSON（保留 XML 属性）。

### String.Json2XmlWithAttribute(json, root) -> String
JSON 转 XML（保留属性信息）。

### String.toBinary(str) -> BinaryString
转二进制串对象。

### String.toBinary16(str) -> String
转十六进制编码字符串。

### String.fromBinary16(hex) -> String
十六进制字符串解码。

### String.PseudoBase64Encode(str) -> String
伪 Base64 编码。

### String.PseudoBase64Decode(str) -> String
伪 Base64 解码。

### String.HM(time) -> String
时间格式化为 HH:MM 格式。

### String.HHMM(time) -> String
时间格式化为 HHMM 格式。

### String.isQname(str) -> Boolean
判断是否为限定名（qualified name）。

---

## 3. Math 工具包

### Math.abs(n) -> Number
绝对值。返回类型与输入相同。

### Math.max(a, b, ...) -> Number
返回最大值。支持多参数。

### Math.min(a, b, ...) -> Number
返回最小值。支持多参数。

### Math.sin(n) -> Double
正弦（弧度制）。

### Math.cos(n) -> Double
余弦（弧度制）。

### Math.rnd(max) / Math.rnd(min, max) -> Number
生成随机数。
```javascript
Math.rnd(100)     // [0, 100) 的随机数
Math.rnd(10, 20)  // [10, 20) 的随机数
```

---

## 4. Number 工具包

### Number.format(n, pattern) -> String
数字格式化。pattern 使用 Java DecimalFormat 语法。
```javascript
Number.format(1234567.89, "#,##0.00")  // "1,234,567.89"
Number.format(0.5, "0.00%")           // "50.00%"
```

### Number.abs(n) -> Number
绝对值。

### Number.ceil(n) -> Long
向上取整。
```javascript
Number.ceil(3.2)  // 4
Number.ceil(-3.8) // -3
```

### Number.floor(n) -> Long
向下取整。

### Number.round(n, scale?) -> Long|BigDecimal
四舍五入。无 scale 返回 Long；有 scale 返回保留指定小数位的 BigDecimal。
```javascript
Number.round(5.5)        // 6
Number.round(5.48369, 4) // 5.4837
```

### Number.int(v) -> Integer
转 Integer。支持带逗号的数字字符串。等价于 `I(v)`。

### Number.long(v) -> Long
转 Long。支持带逗号的数字字符串。等价于 `L(v)`。

### Number.double(v) -> Double
转 Double。等价于 `D(v)`。

### Number.decimal(v) -> BigDecimal
转 BigDecimal。等价于 `N(v)`。**金额计算必须使用此函数**。

### Number.parseHex(hex) -> Number
解析十六进制字符串为数字。等价于 `H(hex)`。

### Number.parseInt(v) -> Integer
解析整数。

### Number.parseLong(v) -> Long
解析长整数。

### Number.parseDouble(v) -> Double
解析浮点数。

### Number.parseDecimal(v) -> BigDecimal
解析定点数。

### Number.rnd(range) -> Double
生成随机数。

### Number.test(v) -> Boolean
判断值是否为数字。
```javascript
Number.test("123")   // true
Number.test("abc")   // false
Number.test(null)    // false
```

### Number.capital(n) -> String
金额转中文大写。
```javascript
Number.capital(12345.67)  // "壹万贰仟叁佰肆拾伍元陆角柒分"
```

### Number.split(n, sep) -> String[]
数字拆分。

### Number.$(n) -> String
货币格式化，保留两位小数。
```javascript
Number.$(3)    // "3.00"
Number.$(3.1)  // "3.10"
```

### Number.%(n) -> String
百分比格式化，乘以 100 并保留两位小数。
```javascript
Number.%(3)    // "300.00"
Number.%(0.5)  // "50.00"
```

---

## 5. Date 工具包

### Date.new(str, format?) -> Date
创建日期对象。
```javascript
Date.new("2024-01-15")                     // 解析日期
Date.new("2024-01-15 10:30:00", "yyyy-MM-dd HH:mm:ss")  // 指定格式
```

### Date.format(date, pattern) -> String
格式化日期。pattern 使用 Java SimpleDateFormat 语法。
```javascript
Date.format(Date.now(), "yyyy-MM-dd")       // "2024-01-15"
Date.format(Date.now(), "yyyy年MM月dd日")    // "2024年01月15日"
```

### Date.add(date, unit, count) -> Date
日期加减。unit 使用时间单位常量。
```javascript
Date.add(Date.now(), DAY, 7)      // 7天后
Date.add(Date.now(), MONTH, -1)   // 1个月前
Date.add(Date.now(), HOUR, 2)     // 2小时后
```

### Date.diff(d1, d2, unit) -> Integer
计算日期差。结果 = d2 - d1。
- unit 可选：`DAY`, `HOUR`, `MINUTE`, `SECOND`, `MONTH`, `YEAR`, `WEEK`, `QUARTER`
- 默认单位为 MILLISECOND
```javascript
Date.diff(date1, date2, DAY)     // 相差天数
Date.diff(date1, date2, MONTH)   // 相差月数
```

### Date.part(date, part) -> Integer
提取日期部分。
- `YEAR`：年份
- `MONTH`：月份（1-12）
- `DAY`：日
- `HOUR`：小时
- `MINUTE`：分钟
- `SECOND`：秒
- `DAY_OF_WEEK`：星期几（1=周日，7=周六）
- `WEEK_OF_YEAR`：年中第几周
- `WEEK_OF_MONTH`：月中第几周
- `DAY_OF_YEAR`：年中第几天
- `QUARTER`：季度
```javascript
Date.part(Date.now(), YEAR)          // 2024
Date.part(Date.now(), DAY_OF_WEEK)   // 1-7
```

### Date.now() -> Date
当前日期时间（含时分秒）。

### Date.today() -> Date
今天日期（零点）。

### Date.getTime() -> Long
当前毫秒级时间戳。

### Date.firstDay(date) -> Date
所在期间的第一天。

### Date.lastDay(date) -> Date
所在期间的最后一天。

### Date.range(unit, date?) -> DateRange
生成日期区间。常见 unit：`DAY`、`WEEK`、`MONTH`、`QUARTER`、`YEAR`。

### 日期常量

| 常量 | 说明 |
|------|------|
| `NOW` | 当前时间 |
| `TODAY` | 今天 |
| `$TODAY` / `$YESTERDAY` / `$TOMORROW` | 日期范围常量 |
| `$THIS_WEEK` / `$LAST_WEEK` / `$NEXT_WEEK` | 周范围 |
| `$THIS_MONTH` / `$LAST_MONTH` / `$NEXT_MONTH` | 月范围 |
| `$THIS_QUARTER` / `$LAST_QUARTER` / `$NEXT_QUARTER` | 季范围 |
| `$THIS_YEAR` / `$LAST_YEAR` / `$NEXT_YEAR` | 年范围 |

### 时间单位常量

`YEAR` `HALFYEAR` `QUARTER` `MONTH` `WEEK` `DAY` `HOUR` `MINUTE` `SECOND` `MILLISECOND`

别名：`Years` `Months` `Quarters` `Weeks` `Days` `Hours` `Minutes` `Seconds` `Milliseconds`

### 时间部分常量

`YEAR` `QUARTER` `MONTH` `WEEK` `WEEK_OF_MONTH` `WEEK_OF_YEAR` `DAY` `DAY_OF_WEEK` `DAY_OF_YEAR` `HOUR` `MINUTE` `SECOND` `MILLISECOND`

---

## 6. Collection 工具包

### Collection.sum(collection) -> Number
求和。

### Collection.avg(collection) -> Double
平均值。

### Collection.max(collection) -> Number
最大值。

### Collection.min(collection) -> Number
最小值。

### Collection.count(collection, value?) -> Integer
计数。无 value 参数时统计非 null 非 false 元素数；有 value 参数时统计与 value 相等的元素数。

### Collection.first(collection) -> Object
首元素。空集合返回 null。

### Collection.last(collection) -> Object
末元素。空集合返回 null。

### Collection.mid(collection, comparator?, getter?) -> Object
计算中位数。
- 无额外参数：对列表求中位值
- `comparator`：比较方向 Lambda（如 `(a,b)->(a>b)`）
- `getter`：属性提取 Lambda（如 `a->(a.score)`）
```javascript
Collection.mid([7, 9, 9, 7])                                    // 8.0
Collection.mid(list, (a,b)->(a>b), a->(a.score))                // 按 score 字段求中位数
```
> 注意：截取子集请使用 `Collection.slice()`。

### Collection.sort(collection, comparator?) -> Collection
排序。可传入比较函数。
```javascript
var list = [{age: 3}, {age: 1}];
Collection.sort(list);                           // 自然排序
Collection.sort(list, (a, b) -> a.age - b.age); // 自定义排序
```

### Collection.group(collection, keyExpr) -> Map
分组。返回 Map，key 为分组键，value 为元素列表。

### Collection.contains(collection, obj) -> Boolean
包含判断。

### Collection.intersect(c1, c2) -> Collection
交集。

### Collection.minus(c1, c2) -> Collection
差集（c1 中有但 c2 中没有）。

### Collection.remove(collection, obj) -> Collection
移除单个元素。

### Collection.removeAll(c1, c2) -> Collection
批量移除（从 c1 中移除 c2 的所有元素）。

### Collection.addAll(c1, c2) -> Collection
批量添加。

### Collection.slice(collection, start, end?) -> Collection
切片。

### Collection.visit(collection, visitor) -> int
遍历并执行 visitor 函数，返回遍历计数。

### Collection.sizeOf(collection) -> Integer
集合大小。

### Collection.clear(collection) -> Collection
清空集合。

### Collection.exclude(collection, criteria) -> Collection
按条件排除。

### Collection.project(collection, criteria, getter?) -> Collection
投影，提取子集属性。

### Collection.stdev(collection) -> Double
标准差。

### Collection.cov(collection) -> Double
协方差。

### Collection.toTree(collection, idField, parentField) -> Tree
列表转树结构。
```javascript
var tree = Collection.toTree(list, "id", "parentId");
```

---

## 7. Aggregation 工具包（独立聚合函数）

这些函数在流式处理的 `group().each()` 中最常用，也可独立调用。

```
SUM(list)              -> Number    // 求和（忽略 null）
AVG(list)              -> Object    // 平均值（忽略 null）
COUNT(list)            -> Integer   // 计数（非 null 非 false）
MAX(list)              -> Object    // 最大值
MIN(list)              -> Object    // 最小值
MID(list)              -> Object    // 中位值（忽略 null）
FIRST(list)            -> Object    // 首元素
LAST(list)             -> Object    // 末元素
CONCAT(list, sep)      -> String    // 拼接，sep 为分隔符（null 时用逗号）
CONCAT2(list, sep)     -> String    // 去重拼接，sep 为分隔符
STDEV(list)            -> Double    // 标准差
```

示例（配合流式处理）：
```javascript
var summary = orders.group(dept).each(
    dept: $key,
    total: SUM(value.each(amount)),
    count: COUNT(value),
    maxAmount: MAX(value.each(amount))
);

// CONCAT 示例
CONCAT([1,2,3], "-")      // "1-2-3"
CONCAT([7,9,9,7], null)   // "7, 9, 9, 7"（null 分隔符默认逗号）

// CONCAT2 示例（去重）
CONCAT2([3,5,6], "i")     // "3i5i6"
CONCAT2(["x","y","y"], "-")  // "x-y"（去重后拼接）

// MID 示例
MID([7,9,9,7])             // 8.0（中位数）
MID([7,9,9,7,null])        // 8.0（忽略 null）
```

---

## 8. Data 工具包

### Data.asList(items...) -> List
创建列表。用于在 `each` 中保持嵌套列表结构（避免自动展开）。
```javascript
var list = Data.asList(1, 2, 3);
```

### Data.pair(key, value) -> Pair
创建键值对。在 `each` 中用于生成新的 Map 键值。
```javascript
map.each(Data.pair($key + "_new", $value * 2))
```

### Data.set(items...) -> Set
创建 Set 集合。
```javascript
var s = Data.set(1, 2, 3, 2);  // {1, 2, 3}
```

### Data.stack() -> Stack
创建后进先出栈。

### Data.queue() -> Queue
创建先进先出队列。

### Data.tuple(items...) -> Tuple
创建元组（不可变有序集合）。

### Data.struct(props) -> Struct
创建结构体。

### Data.fsm() -> FSM
创建有限状态机。

### Data.routing() -> Routing
创建路由表。

### Data.mapping() -> Mapping
创建映射。

### Data.switch() -> Switch
创建开关。

### Data.heap() -> Heap
创建堆数据结构。

### Data.bloom() -> Bloom
创建布隆过滤器。
```javascript
var bf = Data.bloom(10000, 0.01);  // 预期1万元素，1%误判率
```

### Data.deepClone(obj) -> Object
深拷贝对象。
```javascript
var copy = Data.deepClone(originalMap);
```

---

## 9. Dynamic / Static / Boolean 工具包

### Dynamic.get(name) -> Object
获取动态属性值。

### Dynamic.getAll() -> Object
获取全部动态属性。

### Dynamic.put(name, value) -> Object
设置动态属性，返回旧值。

### Dynamic.putAll(props) -> Object
批量设置动态属性。

### Static.get(className, fieldName) -> Object
访问 Java 类的静态字段。
```javascript
Static.get("java.lang.Integer", "MAX_VALUE")  // 2147483647
```

### X(value) -> Boolean
转布尔值。

---

## 10. Array 工具包

### Array.sub(array, start, len?) -> array
子数组。
```javascript
var sub = Array.sub([1,2,3,4,5], 1, 3);  // [2,3,4]
```

### Array.sort(array, comparator?) -> array
数组排序。

---

## 11. AES 工具包

> 可通过系统属性 `ISC_DISABLE_AES_TOOL=true` 禁用。

### AES.encrypt(mode, padding, key, data, iv?) -> byte[]
AES 加密。
- `mode`：加密模式（ECB, CBC, CTR 等）
- `padding`：填充方式（PKCS5Padding, NoPadding 等）
- `key`：密钥（String 或 byte[]）
- `data`：待加密数据（String 或 byte[]）
- `iv`：初始向量（CBC/CTR 模式必需）
```javascript
var encrypted = AES.encrypt("CBC", "PKCS5Padding", key, data, iv);
```

### AES.decrypt(mode, padding, key, data, iv?) -> byte[]
AES 解密。参数同 encrypt。

---

## 12. 独立函数

### Base64Encode(bytes) -> String
Base64 编码。
```javascript
var encoded = Base64Encode(String.getBytes("hello", "UTF-8"));  // "aGVsbG8="
```

### Base64Decode(str) -> byte[]
Base64 解码。
```javascript
var bytes = Base64Decode("aGVsbG8=");
```

### AES_ECB_PKCS5(key, data) -> byte[]
AES-ECB-PKCS5 加密。key 为 UTF-8 字符串。
> 可通过 `ISC_DISABLE_AES_ECB_PKCS5=true` 禁用。ECB 模式安全性较低，生产环境建议用 AES 工具包的 CBC 模式。
```javascript
var data = String.getBytes("hello", "UTF-8");
var encrypted = AES_ECB_PKCS5("0123456789abcdef", data);
```

### AES_ECB_PKCS5_Decrypt(key, data) -> byte[]
AES-ECB-PKCS5 解密。

### JwkToRSAPrivateKey(jwkMap) -> String
JWK 格式转 PKCS1 RSA 私钥（PEM 格式）。
- `jwkMap`：包含 `kty`, `n`, `e`, `d`, `p`, `q`, `dp`, `dq`, `qi` 的 Map
- 返回 `-----BEGIN RSA PRIVATE KEY-----` 格式的 PEM 字符串

### ObjectSize(obj?, ...) -> Long
计算对象内存占用（字节）。无参返回 0；多参返回总和。

### __enableMemoryControl() -> void
启用内存使用跟踪。大数据量处理前调用。

### __disableMemoryControl() -> void
禁用内存使用跟踪。处理完毕后调用。

### IS_NULL(value, default) -> Object
空值替换。如果 value 为 null 则返回 default。
- 支持 List 参数：`IS_NULL([v1, v2], default)` — v1 和 v2 都为 null 时返回 default
```javascript
var name = IS_NULL(user.name, "未知");
var val = IS_NULL([a, b], 0);  // a 和 b 都为 null 时返回 0
```

### NULL_IF(v1, v2) -> Object
相等时返回 null。v1 == v2 返回 null，否则返回 v1。
```javascript
NULL_IF(status, "draft")  // status 为 "draft" 时返回 null
```

### NewArray(list, type?) -> TypedArray
创建类型化数组。
- `type`：SQL 类型常量（`BIGINT`, `INTEGER`, `VARCHAR`, `TIMESTAMP`, `DECIMAL`）
```javascript
NewArray([1, 2, 3], INTEGER)           // int[]
NewArray(["a", "b"], VARCHAR)          // String[]
NewArray([L(1), L(2)], BIGINT)         // long[]
```

---

## 13. SQL 函数

所有 SQL 函数的第一个参数为数据库连接（`$src`, `$tar`, `$this`, `cn`）。

### query_value(cn, sql, params?, types?) -> Object
查询单值（首行首列）。无结果返回 null。
```javascript
var count = query_value($src, "SELECT COUNT(*) FROM t_user WHERE fstatus = ?", [1], [INTEGER]);
```

### query_row(cn, sql, params?, types?) -> Map
查询单行（返回 Map，**key 总是小写**）。无结果返回 null。
```javascript
var user = query_row($src, "SELECT fid, fnumber, fname FROM t_user WHERE fnumber = ?",
    ['admin'], [VARCHAR]);
// user: {fid: 1, fnumber: 'admin', fname: '管理员'}
```

### query_list(cn, sql, params?, types?) -> List\<Map>
查询多行。无结果返回空列表。
- 受 `ISC_QUERY_MAX_SIZE` 限制（默认 20MB），超限抛异常
```javascript
var list = query_list($src, "SELECT fid, fname FROM t_user WHERE fstatus = 0");
```

### query_column(cn, sql, params?, types?) -> List
查询单列值列表。返回所有行的第一列值。
```javascript
var ids = query_column($src, "SELECT fid FROM t_user WHERE fstatus = 0");
```

### execute_update(cn, sql, params?, types?) -> int
执行 INSERT/UPDATE/DELETE。返回受影响行数。
> 仅在目标数据处理脚本、自定义 API、服务流程脚本节点中可用。
```javascript
var affected = execute_update(cn, "UPDATE t_user SET fstatus = ? WHERE fid = ?",
    [1, L(12345)], [INTEGER, BIGINT]);
```

### execute_batch(cn, sql, batch, types?) -> int
批量执行。batch 为参数列表的列表。返回受影响行数。
```javascript
var batch = [[1, 'A', 'a'], [2, 'B', 'b'], [3, 'C', 'c']];
var affected = execute_batch(cn,
    "INSERT INTO t_demo(fid, fnumber, fname) VALUES(?, ?, ?)",
    batch, [BIGINT, VARCHAR, VARCHAR]);
```

### execute_call(cn, sql, params) -> Object
调用存储过程。
- params 为 Map 列表，每个 Map 含 `mode`（IN/OUT/INOUT）、`type`（SQL 类型）、`value`（值）
```javascript
var result = execute_call(cn, "{call proc_calc(?, ?, ?)}",
    [{mode: 'IN', type: INTEGER, value: 100},
     {mode: 'IN', type: VARCHAR, value: 'test'},
     {mode: 'OUT', type: DECIMAL}]);
```

### SQL 类型常量
`VARCHAR` `NVARCHAR` `CHAR` `NCHAR` `DOUBLE` `BINARY` `BLOB` `CLOB` `NCLOB` `BIT` `BIGINT` `INTEGER` `DECIMAL` `TIMESTAMP` `DATETIME` `VARBINARY`

---

## 14. HTTP 函数

### HttpGet(url, data?, charset?, cookies?, headers?) -> Map
基本 GET 请求。
- `data`：可选，通常为 Map；会作为查询参数发送
- `charset`：可选字符集
- `cookies`：可选 Cookie Map
- `headers`：可选请求头 Map
- 返回 Map，常见字段有 `result`、`headers`、`cookies`
- 按本地 runtime 实测，部分返回还可能包含 `responseCode`
```javascript
var result = HttpGet(
    "https://api.example.com/data",
    {id: "123"},
    "UTF-8",
    null,
    {"Accept": "application/json"}
);
var data = String.ParseJson(result.result);
```

### HttpPost(url, data, charset?, cookies?, headers?) -> Map
基本 POST 请求。
- `data`：如果是 Map，通常按 `x-www-form-urlencoded` 发送；如果是字符串，则按原样发送
- 发送 JSON 时，优先先用 `String.FormatJson()` 生成字符串，再配合 `Content-Type: application/json`
- 返回 Map，常见字段有 `result`、`headers`、`cookies`
```javascript
var body = String.FormatJson({name: "test", value: 123});
var result = HttpPost(
    "https://api.example.com/save",
    body,
    "UTF-8",
    null,
    {"Content-Type": "application/json"}
);
var data = String.ParseJson(result.result);
```

### HttpInvoke(url, data, charset?, method?) -> String
通用 HTTP 调用。
```javascript
var response = HttpInvoke("https://api.example.com/data", body, "UTF-8", "PUT");
```

### HttpAccess(url, method, data, charset?, cookies?, headers?, timeout?) -> Map
通用 HTTP 访问。
- `method`：如 `GET` / `POST` / `PUT` / `DELETE`
- `data`：请求体或请求参数
- `timeout`：可选超时时间，单位毫秒
- 返回 Map，常见字段有 `result`、`headers`、`cookies`
```javascript
var result = HttpAccess(
    "https://api.example.com/data",
    "GET",
    {id: "123"},
    "UTF-8",
    null,
    {"Accept": "application/json"},
    30000
);
var body = result.result;
```

### HttpAccess2(url, method, data, charset?, cookies?, headers?, timeout?) -> Map
字节数组版 HTTP 访问。
- `data`：请求体 byte[]
- 返回 Map，常见字段有 `result`（byte[]）、`headers`、`cookies`
```javascript
var body = String.getBytes(
    String.FormatJson({id: "123"}),
    "UTF-8"
);
var result = HttpAccess2(
    "https://api.example.com/data",
    "POST",
    body,
    "UTF-8",
    null,
    {"Content-Type": "application/json"},
    30000
);
var bytes = result.result;
```

### CallWebService(url, method, data, cookies?, headers?, charset?) -> Map
调用 WebService。
- `method`：WebService 方法名
- `data`：通常为 Map
- 返回 Map；可继续从 `result` 中按 XML/对象结构取值
```javascript
var result = CallWebService(
    "http://www.webxml.com.cn/WebServices/WeatherWebService.asmx",
    "getWeatherbyCityName",
    {theCityName: "深圳"}
);
var rows = result.result.'soap:Body'.getWeatherbyCityNameResponse.getWeatherbyCityNameResult.string;
```

### HttpDownloadFile(url, headers?) -> byte[]
下载文件，返回字节数组。文件大小受 `ISC_MAX_FILE_SIZE` 限制（默认 20MB）。
- 返回 Map 含 `filename` 和 `data`（byte[]）
```javascript
var file = HttpDownloadFile("https://example.com/doc.xlsx");
var data = readXLSX(file.data);
```

### HttpUploadFile(url, fileBytes, fileName, params?, headers?) -> String
上传文件（multipart/form-data）。
```javascript
var response = HttpUploadFile(
    "https://example.com/upload",
    fileBytes, "data.xlsx",
    {param1: 'value1'},
    {Authorization: 'Bearer <ACCESS_TOKEN>'});
```
