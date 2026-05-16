# ISCB 平台约定与常见陷阱

## 0. 复用优先

- 写新脚本前先看当前工作区已有 `.iscb`、共享脚本段、资源别名约定、函数组合和现成节点实现。
- 平台已有资源、函数或脚本模式能覆盖需求时，不再复制第二套写法；只在缺口明确时补最小片段。

## 1. 变量作用域

### @@上下文变量
- `@@var` 在嵌入式 SQL 中用于绑定脚本变量
- `@@var` 赋值后在当前脚本执行上下文中持续有效
- `@@var[]` 后缀 `[]` 表示列表赋值

### 流式处理上下文变量
- `_` 上级上下文：`_.index` 访问上级变量
- `#` 根上下文：`#.total` 访问根变量
- `$` 当前元素：`$.name` 访问当前元素属性
- 在 each 中设置 `_.counter` 会修改上级变量，可用于累加器

### var 声明
- `var` 声明块作用域变量
- 未声明直接赋值的变量也可使用，但建议始终用 `var`

---

## 2. 类型转换陷阱

### null 运算规则
- `null + number` = `null`（不是 NaN）
- `null == null` = `true`
- `null === null` = `true`
- 使用 `IS_NULL(value, default)` 处理空值

### 数字类型精度
- 整数运算使用 `I()` 或 `L()`
- 金额计算**必须**使用 `N()`（BigDecimal），不要用 `D()`（有精度损失）
- `3 / 2` = `1`（整数除法），`D(3) / 2` = `1.5`

### 字符串与数字比较
- `==` 自动类型转换：`1 == '1'` → true
- `===` 不转换：`1 === '1'` → false
- 建议使用 `===` 避免歧义

---

## 3. 集合操作注意事项

### List vs Array
- `[1, 2, 3]` 创建的是 List（可变长度）
- `NewArray([1, 2, 3], INTEGER)` 创建类型化数组

### Map 键的大小写
- SQL 查询返回的 Map，key **总是小写**
- `query_row($src, "SELECT FID, FNUMBER FROM T")` 返回 `{fid: ..., fnumber: ...}`
- 使用 AS 别名可以控制 key 名：`SELECT fid as id`

### 空集合判断
- `list is Empty` 判断列表为空或 null
- `list == null` 仅判断 null
- SQL 查询无结果时：
  - `@@var`（单值）= null
  - `@@var[]`（列表）= 空列表（不是 null）

---

## 4. 嵌入式 SQL 注意事项

### 必须大写的关键字
- `SELECT` 必须大写（是脚本语法关键字，不仅是 SQL）
- 建议其他 SQL 关键字也大写：`FROM`, `WHERE`, `ORDER BY`, `GROUP BY`, `LEFT JOIN` 等

### 空格规则
- `@@id = fid` 等号前后必须有空格
- 错误写法：`@@id=fid`（会被解析为不同含义）

### 表名格式
- 苍穹环境：`$this.tablename@database`（@ 分隔分库标识）
- 直连数据库：`tablename`（无需 @ 分库标识）

### MySQL 关键字冲突
- 字段名/表名与 SQL 关键字冲突时用反引号：`` `order` ``
- 字段名与脚本关键字冲突时用双引号：`"number"`

### 子查询限制
- 子查询中**不允许**对脚本变量赋值
- 子查询只能在 WHERE 条件的 IN 子句中使用

### IN 条件自动展开
```javascript
var ids = [1, 2, 3];
SELECT @@list[] = fname FROM $this.t_table WHERE fid IN (@@ids);
// 自动展开为: WHERE fid IN (?, ?, ?)
```

---

## 5. 流式处理陷阱

### each 返回值规则
- `list.each(expr)` — expr 结果为 List 时会展开（一对多映射）
- 若需要保持嵌套 List 结构，用 `Data.asList(...)` 包装

### each 的 => 操作符结合方向
- `=>` 是**右结合**的
- `a => b => c` 等价于 `a.each(b.each(c))`（不是 `a.each(b).each(c)`）
- `a.each(b).each(c)` 等价于 `(a => b) => c`

### filter 后 each
- 建议先 filter 再 each，避免对无效数据做转换
- `list.filter(condition).each(transform)`

### group + concat 模式
```javascript
// 正确：分组后拼接每组的字段值
list.group(dept).each(value.concat(name, ","))

// 注意：concat 的第一个参数是要拼接的字段表达式，第二个是分隔符
```

---

## 6. 性能注意事项

### 内存控制
- 大数据量处理时，使用 `EnableMemoryControl()` 开启内存监控
- 处理完毕后调用 `DisableMemoryControl()` 关闭
- `ObjectSize(obj)` 检查对象占用内存

### 超时
- 脚本有执行超时限制
- 长时间运行的循环应定期调用 `CheckCancelSignal()` 检查取消信号

### SQL 查询优化
- 避免在循环中执行 SQL，尽量一次性查询
- 使用 IN 条件批量查询，而非循环单条查询
- 批量写入使用 `execute_batch` 而非循环 `execute_update`

---

## 7. 常见错误模式

### 错误 1：在值转换规则中写入数据
```javascript
// 错误！值转换规则只能读取
execute_update($this, "INSERT INTO ...", params, types);

// 正确：在目标数据处理脚本或服务流程中写入
```

### 错误 2：混淆引擎层和平台层函数
```javascript
// 错误：不要写裸 parseInt()
var n = parseInt("123");

// 正确：优先使用 I() 类型转换
var n = I("123");

// 如确需显式解析，也可以用 Number.parseInt()
var n2 = Number.parseInt("123");
```

### 错误 3：忘记 SQL 类型声明导致类型错误
```javascript
// 可能出错：参数类型推断不准确
SELECT @@users[] = (fid, fname) FROM $this.t WHERE fid IN (@@ids);

// 更安全：显式声明类型
SELECT @@users[] = (fid, fname) FROM $this.t WHERE fid IN (@@ids :: BIGINT);
```

### 错误 4：流式处理中修改原集合
```javascript
// 注意：流式处理生成新集合，不修改原集合
var result = list.filter(age > 18);
// list 不变，result 是新列表
```

### 错误 5：Hmac 函数传入 String 而非 byte[]
```javascript
// 错误！会抛出 IscBizException: 参数类型不支持
var sig = Hash.HmacSHA256("data", "key");

// 正确：使用 String.getBytes() 或 String.getBytes2() 转为 byte[]
var sig = Hash.HmacSHA256(
    String.getBytes("data", "UTF-8"),
    String.getBytes("key", "UTF-8"));
var result = Base64Encode(sig);
```

### 错误 6：金额用 Double 而非 BigDecimal
```javascript
// 错误：精度损失
var total = D(100.1) + D(200.2);  // 可能不精确

// 正确：用 N() 保证精度
var total = N('100.1') + N('200.2');  // 300.3 精确
```

### 错误 7：使用不存在的 newList() 函数
// 错误
var list = newList();

// 正确：使用字面量或 Data.asList()
var list = [];
var list = Data.asList(1, 2, 3);
