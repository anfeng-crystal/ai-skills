# ISCB DSL 完整语法参考

## 1. 类型系统

### 基本类型
| 类型 | 转换函数 | Java类型 | 示例 |
|------|----------|----------|------|
| 整数 | `I(v)` | Integer | `I('928')` → 928 |
| 长整数 | `L(v)` | Long | `L(928)` → 928L |
| 浮点数 | `D(v)` | Double | `D('3.14')` → 3.14 |
| 定点数 | `N(v)` | BigDecimal | `N('928.0')` → 928.0 |
| 布尔 | `X(v)` | Boolean | `X('true')` → true |
| 时间戳 | `T(v)` | Timestamp | `T('1999-01-01 12:00:00')` |
| 字符串 | 单/双引号 | String | `'hello'` 或 `"hello"` |
| 二进制 | `0x` 前缀 | BinaryString | `0xDEADBEEF` |

### 集合类型
```javascript
[1, 2, 3]                    // List
{key1: 'val1', key2: 'val2'} // Map（LinkedHashMap，保序）
Data.set(1, 2, 3)            // Set
Data.pair('k', 'v')          // Pair
Data.tuple(1, 'a', true)     // Tuple
```

### 类型判断
```javascript
value is Integer             // 类型检查
value is String
value is List
value is Map
```

### 类型常量（用于 SQL 类型声明和 NewArray）
`VARCHAR`, `NVARCHAR`, `CHAR`, `NCHAR`, `DOUBLE`, `BINARY`, `BLOB`, `CLOB`, `NCLOB`, `BIT`, `BIGINT`, `INTEGER`, `DECIMAL`, `TIMESTAMP`, `DATETIME`, `VARBINARY`

---

## 2. 操作符完整参考

### 2.1 算术操作符
| 操作符 | 说明 | 示例 |
|--------|------|------|
| `+` | 加（数字相加或字符串拼接） | `3 + 5` → 8, `'a' + 'b'` → `"ab"` |
| `-` | 减 | `10 - 3` → 7 |
| `*` | 乘 | `4 * 5` → 20 |
| `/` | 除 | `10 / 3` → 3 |
| `%` | 取余 | `10 % 3` → 1 |
| `**` | 幂 | `2 ** 10` → 1024 |
| `++` | 自增 | `i++` |
| `--` | 自减 | `i--` |

### 2.2 比较操作符
| 操作符 | 说明 | 示例 |
|--------|------|------|
| `==` | 宽松相等（自动类型转换） | `1 == '1'` → true |
| `===` | 严格相等 | `1 === '1'` → false |
| `!=` 或 `<>` | 不等 | `1 != 2` → true |
| `!==` | 严格不等 | `1 !== '1'` → true |
| `<` `<=` `>` `>=` | 大小比较 | `3 > 2` → true |

### 2.3 逻辑操作符
| 操作符 | 说明 | 短路 |
|--------|------|------|
| `&&` | 逻辑与 | 是 |
| `||` | 逻辑或 | 是 |
| `!` 或 `not` | 逻辑非 | - |

### 2.4 位操作符
| 操作符 | 说明 |
|--------|------|
| `&` | 按位与 |
| `|` | 按位或 |
| `^` | 按位异或 |
| `~` | 按位取反 |
| `<<` | 左移 |
| `>>` | 右移 |
| `>>>` | 无符号右移 |

### 2.5 字符串/集合操作符
| 操作符 | 说明 | 示例 |
|--------|------|------|
| `contains` | 包含（正向） | `'hello' contains 'ell'` → true |
| `in` | 包含（反向） | `'ell' in 'hello'` → true |
| `startsWith` | 前缀判断 | `'hello' startsWith 'hel'` → true |
| `endsWith` | 后缀判断 | `'hello' endsWith 'llo'` → true |
| `like` | 模式匹配 | `'hello' like 'hel*'` |
| `match` / `matches` | 正则匹配 | `'hello' matches '^h.*o$'` |
| `&+` | 不重复添加 | `list &+ item` |
| `++=` | 批量添加 | `list1 ++= list2` |
| `--=` | 批量移除 | `list1 --= list2` |

### 2.6 特殊操作符
| 操作符 | 说明 | 示例 |
|--------|------|------|
| `? :` | 三元条件 | `x > 0 ? 'positive' : 'negative'` |
| `..` | 范围 | `1..10` |
| `->` | Lambda | `x -> x * 2` |
| `=>` | each 简写 | `list => expr` 等价 `list.each(expr)` |
| `?.` | 安全导航 | `obj?.field`（obj 为 null 时返回 null） |

### 2.7 赋值操作符
`=`, `+=`, `-=`, `*=`, `/=`, `%=`, `**=`, `++=`, `--=`

---

## 3. 控制流详解

### 3.1 条件语句
```javascript
if(x > 0) {
    // 正数处理
}

if(x > 0) {
    // 正数
} else {
    // 非正数
}

// 注意：没有 else if 语法，需嵌套
if(x > 0) {
    // 正数
} else {
    if(x == 0) {
        // 零
    } else {
        // 负数
    }
}
```

### 3.2 For 循环
```javascript
// C 风格
for(var i = 0; i < 10; i++) {
    println(i);
}

// 遍历集合
for(item : list) {
    println(item);
}

// 带索引遍历
for((item, index) : list) {
    println(index + ": " + item);
}

// 带计数遍历
for((item, index, seq) : list) {
    println("第" + seq + "个");
}

// 遍历 Map
for((key, value) : map) {
    println(key + " = " + value);
}

// 多集合并行遍历
for([a, b] : [list1, list2]) {
    println(a + " " + b);
}

// 无限循环
for(;;) {
    if(condition) break;
}
```

### 3.3 While 循环
```javascript
var i = 0;
while(i < 10) {
    println(i);
    i++;
}
```

### 3.4 循环控制
```javascript
break;        // 退出当前循环
continue;     // 跳过本次迭代
```

### 3.5 异常处理
```javascript
try {
    var result = riskyOperation();
} catch(e) {
    println("Error: " + e);
} finally {
    cleanup();
}

throw "Something went wrong";
```

### 3.6 函数定义
```javascript
function add(a, b) {
    return a + b;
}

var result = add(3, 5); // 8
```

### 3.7 Lambda 表达式
```javascript
// 单参数
var double = x -> x * 2;

// 多参数
var add = (a, b) -> a + b;

// 在流式处理中使用
list.filter(x -> x > 5);
list.sort((a, b) -> a.age - b.age);
```

### 3.8 synchronized 同步块
```javascript
synchronized("lockKey") {
    // 分布式锁保护的代码
}
```

---

## 4. 流式处理详解

### 4.1 上下文变量
在流式处理的表达式中，可使用以下特殊变量：
- `_` (下划线) — 上级上下文环境，`_.name` 读写上级变量
- `#` — 根上下文环境，`#.name` 读写根环境变量
- `$` — 当前元素，`$.property` 读写当前元素属性
- 当元素是 Map 时，可直接用 key 名访问值
- 当遍历 Map 时，`$key` 和 `$value` 访问键值

### 4.2 each — 遍历转换
```javascript
// 列表：提取属性组成新列表
var names = list.each(name);

// 列表：构造新 Map 元素
var list2 = list.each(name: name, age: age);

// 字符串数组转分录
var result = ['Sky', 'Star', 'Denver'].each(seq: ++_.index, name: $);

// Map：对 value 转换，key 不变
var map2 = map.each(value <= 18 ? 'Child' : 'Adult');

// Map：生成新 key-value 对（返回二元组）
var map2 = map.each(Data.pair($key + '_new', $value * 2));

// 等价简写
a.each(b)      等价于  a => b
a => b => c    等价于  a.each(b.each(c))
(a => b) => c  等价于  a.each(b).each(c)
```

### 4.3 filter — 过滤
```javascript
// 列表过滤
var adults = list.filter(age >= 18);

// Map 过滤
var filtered = map.filter($value > 100);

// Set 过滤
var evenSet = set.filter($ % 2 == 0);
```

### 4.4 group — 分组
```javascript
// 单字段分组
var grouped = list.group(department);
// 结果: {dept1: [item1, item2], dept2: [item3]}

// 表达式分组
var grouped = list.group(age >= 18 ? 'adult' : 'child');

// 多列值分组
var grouped = list.group(dept, role);
```

### 4.5 sort — 排序
```javascript
// 单字段排序（升序）
var sorted = list.sort(age);

// 单字段排序（降序）
var sorted = list.sort(age, DESC);

// 字符串列表排序
var sorted = ['b', 'a', 'c'].sort($);

// 逆序
var sorted = ['b', 'a', 'c'].sort(-$);
```

### 4.6 entries — 转分录
```javascript
// Map 转 List<{key, value}>
var list = map.entries();

// 横表转纵表
var list = [{a:1, b:2}, {a:3, b:4}].entries();
```

### 4.7 mapping — 转 Map
```javascript
// 列表转 Map
var map = list.mapping(id, name);
// 结果: {id1: name1, id2: name2}

// 纵表转横表
var map = list.mapping(key, value);
```

### 4.8 split — 拆分
```javascript
// 字符串拆分为列表
var parts = "a,b,c".split(",");
```

### 4.9 concat — 拼接
```javascript
// 列表拼接为字符串
var str = [1, 2, 3].concat(",");  // "1,2,3"

// 分组汇总
var summary = list.group(dept).each(value.concat(name, ","));
```

### 4.10 数值统计
```javascript
list.sum(amount)       // 求和
list.count(amount)     // 计数
list.max(amount)       // 最大值
list.min(amount)       // 最小值
list.avg(amount)       // 平均值
```

---

## 5. 嵌入式 SQL 详解

### 5.1 基本语法
```
SELECT @@variable = expression FROM table WHERE condition;
```

### 5.2 赋值形式
| 形式 | 说明 | 返回 |
|------|------|------|
| `@@id = fid` | 查询单个字段值 | 单值，无结果返回 null |
| `@@list[] = fid` | 查询字段值列表 | List，无结果返回空列表 |
| `@@user = (fid, fname)` | 查询首行多字段 | Map(key小写)，无结果返回 null |
| `@@users[] = (fid, fname)` | 查询多行多字段 | List<Map>，无结果返回空列表 |

### 5.3 表名语法
```
$this.tablename@database   // 当前苍穹环境的表
$src.tablename@database    // 源系统的表
$tar.tablename@database    // 目标系统的表
```

### 5.4 变量引用
```javascript
var number = '34460';
SELECT @@id = fid FROM $this.t_sec_user@basedata WHERE fnumber = @@number;
// @@number 引用脚本变量 number 的值
```

如果脚本变量本身是对象，也可以绑定其属性，例如 `@@src.phone`、`@@tar.number`。这里的 `@@` 是嵌入式 SQL 的变量绑定前缀，不是 XPath 语法。

### 5.5 类型声明
```javascript
// 变量后加 ::TYPE 声明参数类型
SELECT @@users[] = (fid, fname)
    FROM $this.table@db WHERE fid IN (@@ids :: BIGINT);
```

### 5.6 字段别名
```javascript
// AS 重命名字段，返回 Map 的 key 使用别名
SELECT @@user = (fid as id, fnumber as "number", fname as name)
    FROM $this.t_sec_user@basedata WHERE fnumber = '34460';
// 返回: {id: xxx, number: '34460', name: 'xxx'}
```

### 5.7 重要注意事项
- `SELECT` 关键字必须大写
- 等号 `=` 前必须有空格：`@@id = fid`（不是 `@@id=fid`）
- 字段名/表名与 SQL 关键字冲突时用反引号包围
- 字符串比较值用单引号，字段名用双引号
- 子查询中不允许对脚本变量赋值
- IN 条件会自动展开列表为多个参数占位符

---

## 6. XPath 路径访问详解

### 6.1 基本语法
```text
@.                  // 当前环境
@../parentVar       // 上级环境中的变量
@/rootVar           // 根环境中的变量
@order/customer/name  // 在当前环境中按路径访问变量
@persons[1]/name    // 取第一行的 name（XPath 下标从 1 开始）
@persons[-1]/name   // 取倒数第一行的 name
@persons[age >= 18]/name  // 按条件过滤后取值
```

### 6.2 特殊形式
| 写法 | 含义 |
|------|------|
| `@.` | 当前环境 |
| `@../var` | 上级环境中的变量 |
| `@/var` | 根环境中的变量 |

**注意**：
- XPath 使用 `/` 分隔路径，不使用 `.` 作为字段访问分隔符
- XPath 的列表下标从 `1` 开始，`-1` 表示倒数第一行
- `@src.field` / `@tar.field` 不是这里的 XPath 写法

### 6.3 在数据集成脚本中的常见变量
```javascript
// 源单当前行预置变量
src.fieldName

// 目标单当前行预置变量
tar.fieldName

// 源单分录列表
src.entry

// 目标单分录列表
tar.entry
```

如果用户明确说脚本写在“来源数据处理脚本 / 转换脚本 / 目标数据处理脚本 / 值转换规则”中，应优先说明该上下文预置的变量名，例如 `src`、`tar`、`$src`、`$tar`、`$this`，不要把它们误写成 XPath 形式。

---

## 7. 注释

```javascript
// 单行注释
var x = 1; // 行尾注释

// 注意：没有多行注释语法 /* */
```

## 8. 内置决策函数

```javascript
IS_NULL(value, default)     // value 为 null 时返回 default
IS_NULL([v1, v2], default)  // v1 和 v2 都为 null 时返回 default
NULL_IF(v1, v2)             // v1 == v2 时返回 null，否则返回 v1
```
