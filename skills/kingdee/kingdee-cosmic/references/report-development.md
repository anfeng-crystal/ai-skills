---
name: 星瀚赋能报表敏捷开发
description: >
  读取开发技术模板，结合内置心智模型 + Algo API 精确签名 + 项目65个报表插件实战模式，
  生成高质量苍穹定制化报表插件。
version: "4.0.0"
user-invocable: true
---

# /kingdee-rpt-gen 报表代码生成 v4.0.0

> 自包含技能：读取开发技术模板，结合内置心智模型 + Algo API 精确签名 + 报表插件实战模式，生成高质量苍穹定制化报表插件。
> 无需依赖其他 Skill 即可独立运行。

---

## 前置条件

- 开发技术模板（Template B）已完整填写
- 所有 [必须] 项均有内容（实体标识、字段Key、关联路径、编码值、公式）
- 如有缺失项，先列出缺失清单，提示用户补充后再生成

---

## 心智模型（报表插件专用，内置5个核心框架）

### 模型1：报表生命周期

报表插件只有**一个核心入口**：`query(ReportQueryParam, Object)`。所有逻辑都挂载在这个方法上。

```
query() 方法执行链：
  解析 FilterInfo → 构建 QFilter[] → 查询多个 DataSet → JOIN/UNION → 聚合 → 添加计算列 → 返回
```

### 模型2：三层数据访问（报表专用）

报表插件**只使用只读查询层**，详见下方「报表插件在苍穹插件体系中的定位 → 三层数据访问」章节。

**核心规则**：禁止 `SaveServiceHelper`、`OperationServiceHelper` — 报表是纯查询，不写库。

### 模型3：无状态设计铁律

```java
// 禁止！所有表单实例共享此类，实例字段会串数据
private Object lastOrgId;
private Map<String, DataSet> cache;

// 正确：所有数据用局部变量 + 方法参数传递
// (注解: 继承自 AbstractReportListDataPlugin 的 query 方法)
public DataSet query(ReportQueryParam reportQueryParam, Object o) {
    FilterInfo filterInfo = reportQueryParam.getFilter();
    Object orgId = parseOrgId(filterInfo);  // 局部变量
    DataSet ds = getMainDs(orgId, ...);     // 方法参数传递
    return ds;
}
```

唯一例外：`private static final` 常量是安全的（类级别，不可变）。

### 模型4：BigDecimal 财务计算铁律

- **禁止** `double` / `float` 运算
- 运算：`.add()` / `.subtract()` / `.multiply()` / `.divide(scale, RoundingMode)`
- 比较：`.compareTo()` — 永远不用 `==` 或 `.equals()`
- 空值：统一用辅助方法 `getBigDecimalValue(row, field)` 返回 `BigDecimal.ZERO`

### 模型5：DataSet 消费陷阱

- DataSet 是**单次消费**的：遍历后数据被消费，不能再读取
- 需要遍历 + 后续使用时，**必须先 `.copy()`**：
  ```java
  for (Row row : ds.copy()) { ... }  // 遍历副本
  return ds;                           // 原始 DataSet 仍可用
  ```
- AlgoKey **必须唯一**：同一插件内多个查询用 `this.getClass().getName() + "_suffix"` 区分
- NULL 比较用 `IS NULL`，**禁止** `= null`（SQL表达式中不生效）

---

## 报表插件在苍穹插件体系中的定位

> 以下上下文帮助理解报表插件在苍穹插件体系中的职责边界。

### 插件类型体系（报表相关行高亮）

| 类型 | 基类 | 典型场景 |
|------|------|---------|
| **报表插件** | **AbstractReportListDataPlugin** | **报表取数逻辑（本Skill唯一目标）** |
| 报表表单插件 | AbstractReportFormPlugin | 报表过滤面板联动（非本Skill范围） |
| 表单插件 | AbstractBillPlugIn | 单据字段联动 |
| 操作插件 | AbstractOperationServicePlugIn | 保存校验、审核后处理 |
| 列表插件 | AbstractListPlugin | 列表过滤、格式化 |

**报表插件职责**：只实现 `query(ReportQueryParam, Object)` 方法，纯只读查询，不写库。

### 三层数据访问（报表专用精简版）

| 层级 | 接口 | 报表中用途 | 何时用 |
|------|------|----------|-------|
| 只读查询（主力） | `QueryServiceHelper.queryDataSet()` | 返回 DataSet，支持 Algo API 链式操作 | 90%的报表查询 |
| 只读查询（小型） | `QueryServiceHelper.query()` | 返回 DynamicObjectCollection，用于基础资料查找 | 查辅助表（核算期间等） |
| 缓存查询（辅助） | `BusinessDataServiceHelper.loadSingleFromCache()` | 查找基础资料缓存 | 组织、核算期间等缓存数据 |

**禁止**在报表插件中使用 `SaveServiceHelper`、`OperationServiceHelper` — 报表是纯查询，不写库。

---

## 三种报表架构模式（从实战插件提炼）

根据 Template B 的复杂度，选择合适的架构：

### 模式A：Algo Pipeline（推荐，90%场景）

适用：数据来自 ORM 实体，可表达为查询→关联→聚合流水线。

```java
// (继承自 AbstractReportListDataPlugin 的 query 方法)
public DataSet query(ReportQueryParam reportQueryParam, Object o) throws Throwable {
    FilterInfo filterInfo = reportQueryParam.getFilter();
    if (filterInfo == null) return null;

    // 1. 解析过滤
    Object orgId = parseOrgId(filterInfo);
    Object periodId = parsePeriodId(filterInfo);

    // 2. 查询各数据源
    DataSet balDs = getBalanceDs(orgId, periodId);
    DataSet costDs = getCostRecordDs(orgId, periodId);

    // 3. 关联
    DataSet result = balDs.leftJoin(costDs)
        .on("invorg", "invorg")
        .on("product", "product")
        .select(balDs.getRowMeta().getFieldNames(), costDs.getRowMeta().getFieldNames())
        .finish();

    // 4. 添加计算列
    result = result.addField(
        "CASE WHEN startinvqty IS NULL THEN 0 ELSE startinvqty END"
        + " + CASE WHEN adjustinqty IS NULL THEN 0 ELSE adjustinqty END"
        + " - CASE WHEN endinvqty IS NULL THEN 0 ELSE endinvqty END",
        "balqty");

    return result;
}
```

### 模式B：Map-Based Assembly（复杂转换场景）

适用：需要逐行复杂转换（如动态列、单位换算查表），无法用 DataSet 表达式完成。

```java
// 定义结果集结构
String[] fields = {"invorg", "product", "qty", "amount"};
DataType[] types = {DataType.StringType, DataType.StringType, DataType.BigDecimalType, DataType.BigDecimalType};

// 查询源数据
DataSet sourceDs = QueryServiceHelper.queryDataSet(algoKey, entity, selectFields, filters, null);

// 逐行转换
Collection<Object[]> rows = new ArrayList<>();
for (Row row : sourceDs.copy()) {
    Object[] arr = new Object[fields.length];
    arr[0] = row.getString("invorg");
    arr[1] = row.getString("product");
    BigDecimal qty = getBigDecimalValue(row, "baseqty");
    arr[2] = qty.multiply(conversionFactor);  // 单位换算
    arr[3] = qty.multiply(unitPrice);
    rows.add(arr);
}

// 组装新 DataSet
RowMeta rowMeta = RowMetaFactory.createRowMeta(fields, types);
CollectionInput inputs = new CollectionInput(rowMeta, rows);
return Algo.create(algoKey + "_assembled").createDataSet(inputs);
```

### 模式C：AlgoX Pipeline（新API，成本报表专用）

适用：使用 `AlgoX` / `DataSetX` / `JobSession` 的新版成本报表。

```java
// 仅当 Template B 明确指定使用 AlgoX 时使用
AlgoX algoX = AlgoX.createSession(simpleName, simpleName);
DataSetX dsX = algoX.queryDataSetX(entityName, selectFields, filters);
```

**默认使用模式A**，仅在 Template B 中有特殊要求时切换。

---

## 完整代码生成规范

### Import 标准集

```java
// Algo/DataSet 核心
import kd.bos.algo.Algo;
import kd.bos.algo.DataSet;
import kd.bos.algo.DataType;
import kd.bos.algo.GroupbyDataSet;
import kd.bos.algo.Row;
import kd.bos.algo.RowMeta;
import kd.bos.algo.RowMetaFactory;
import kd.bos.algo.input.CollectionInput;

// 报表框架
import kd.bos.entity.report.AbstractReportListDataPlugin;
import kd.bos.entity.report.FilterInfo;
import kd.bos.entity.report.FilterItemInfo;
import kd.bos.entity.report.ReportQueryParam;

// 查询
import kd.bos.orm.query.QCP;
import kd.bos.orm.query.QFilter;
import kd.bos.servicehelper.QueryServiceHelper;
import kd.bos.servicehelper.BusinessDataServiceHelper;

// 数据实体
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.dataentity.entity.DynamicObjectCollection;

// 日志
import kd.bos.logging.Log;
import kd.bos.logging.LogFactory;

// Java标准库
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;
import java.util.stream.Collectors;
```

### FilterInfo 完整解析 API

```java
FilterInfo filterInfo = reportQueryParam.getFilter();
if (filterInfo == null) return null;

// 1. 基础资料（F7单选）
DynamicObject orgObj = filterInfo.getDynamicObject("orgf");
Object orgId = orgObj != null ? orgObj.getPkValue() : null;

// 2. 基础资料（F7多选）
DynamicObjectCollection products = filterInfo.getDynamicObjectCollection("productf");
Set<Object> productIds = new HashSet<>();
if (products != null) {
    for (DynamicObject prod : products) {
        productIds.add(prod.getPkValue());
    }
}

// 3. 日期
Date startDate = filterInfo.getDate("startdate");

// 4. 字符串
String billNo = filterInfo.getString("ezob_billno");

// 5. 布尔
boolean includeAll = filterInfo.getBoolean("inclall");

// 6. 长整型
long auxPropId = filterInfo.getLong("ezob_auxpropertyid");

// 7. 通用 FilterItem（兜底）
Object value = filterInfo.getFilterItem("customfield").getValue();

// 8. 遍历所有过滤项
List<FilterItemInfo> items = filterInfo.getFilterItems();
for (FilterItemInfo item : items) {
    String propName = item.getPropName();
    Object val = item.getValue();
}
```

### QFilter 构建三种模式

```java
// 模式1：链式 and（推荐，简单场景）
QFilter filter = new QFilter("billstatus", "=", "C");
filter.and("org", "=", orgId);
if (periodId != null) filter.and("period", "=", periodId);
DataSet ds = QueryServiceHelper.queryDataSet(algoKey, entity, fields, filter.toArray(), null);

// 模式2：List 动态组装（推荐，条件可选）
List<QFilter> filters = new ArrayList<>();
filters.add(new QFilter("billstatus", "=", "C"));
if (orgId != null) filters.add(new QFilter("org", "=", orgId));
if (!productIds.isEmpty()) filters.add(new QFilter("entry.material", "in", productIds.toArray()));
DataSet ds = QueryServiceHelper.queryDataSet(algoKey, entity, fields,
    filters.toArray(new QFilter[0]), null);

// 模式3：内联数组（简洁，条件固定）
DataSet ds = QueryServiceHelper.queryDataSet(algoKey, entity, fields, new QFilter[]{
    new QFilter("billstatus", "=", "C"),
    orgId == null ? null : new QFilter("org", "=", orgId),
}, "");
```

### Algo API 精确签名参考（从 cosmic-dev 注入，自包含）

> 以下签名来自苍穹 8.0.1 框架源码，报表插件开发时直接参考，无需查阅其他 Skill。

#### 1. Algo 工厂类 `kd.bos.algo.Algo`

```java
// 创建 Algo 上下文（algoKey 必须全局唯一）
Algo algo = Algo.create(String algoKey);

// 创建 DataSet（6种重载）
DataSet createDataSet(Collection<Object[]> rowList, RowMeta rowMeta)
DataSet createDataSet(Iterator<Object[]> iterator, RowMeta rowMeta)
DataSet createDataSet(Iterable<Object[]> iterable, RowMeta rowMeta)
DataSet createDataSet(ResultSet rs)
DataSet createDataSet(ResultSet rs, RowMeta rowMeta)
DataSet createDataSet(Input[] inputs)              // OrmInput/DbInput等

// 创建 DataSetBuilder
DataSetBuilder createDataSetBuilder(RowMeta rowMeta)

// 缓存相关
CachedDataSet getCacheDataSet(String cacheId)
void removeCacheDataSet(String cacheId)
static void closeAllDataSet()                      // 危险：关闭当前线程所有DataSet
```

#### 2. DataSet 完整方法签名 `kd.bos.algo.DataSet`

```java
// ── 字段操作 ──
DataSet addField(String expr, String alias)         // 新增字段（最常用）
DataSet addFields(String[] exprs, String[] aliases) // 批量新增
DataSet addBalanceField(String expr, String alias)  // 余额字段（从上往下累加）
DataSet addNullField(String alias)                  // 新增空字段
DataSet addNullField(String[] aliases)              // 批量新增空字段
DataSet updateField(String field, String expr)      // 更新字段表达式
DataSet updateFields(String[] fields, String[] exprs) // 批量更新
DataSet removeFields(String[] fields)               // 删除字段

// ── 查询（ORM → DataSet）──
// QueryServiceHelper.queryDataSet(algoKey, entityName, selectFields, QFilter[], orderBy)
// selectFields 语法：
//   "field"              → 直接取字段
//   "field alias"        → 取字段并命名别名
//   "material.number no" → 支持ORM路径 + 别名
//   "'PCS' unit"         → 字符串常量
//   "0.0 rate"           → 数字常量
//   "CASE WHEN ... END x" → CASE 表达式

// ── 关联（返回 JoinDataSet）──
JoinDataSet leftJoin(DataSet right)                 // 左连接（报表最常用）
JoinDataSet leftJoin(DataSet right, JoinHint hint)
JoinDataSet join(DataSet right)                     // 内连接
JoinDataSet join(DataSet right, JoinType type)      // 指定JoinType
JoinDataSet join(DataSet right, JoinType type, JoinHint hint)
JoinDataSet rightJoin(DataSet right)                // 右连接
JoinDataSet fullJoin(DataSet right)                 // 全连接
JoinDataSet fullJoin(DataSet right, JoinHint hint)
// JoinDataSet 链式：.on("k1","k1").on("k2","k2").select(leftFields, rightFields).finish()

// ── 分组聚合（返回 GroupbyDataSet）──
GroupbyDataSet groupBy()                            // 无分组字段，默认一组
GroupbyDataSet groupBy(String[] groupFields)        // 按字段分组（升序）
GroupbyDataSet groupBy(String[] groupFields, boolean[] orderByDescs) // 按字段分组+排序方向
// GroupbyDataSet 链式：.sum("qty").sum("amount").max("price").maxP("time","val")
//                      .groupConcat("type","type",",").finish()

// ── 过滤 ──
DataSet filter(String expr)                         // 表达式过滤
DataSet filter(String expr, Map<String,Object> params) // 带参数过滤
DataSet filter(FilterFunction func)                 // 自定义过滤函数
DataSet where(String expr)                          // 等同 filter
DataSet where(String expr, Map<String,Object> params)
DataSet where(FilterFunction func)

// ── 投影/选择 ──
DataSet select(String[] exprs)                      // 多表达式选择（支持四则运算、常量、宏NULL/TRUE/FALSE）
DataSet select(boolean distinct, String[] exprs)    // 去重选择
DataSet select(String expr)                         // 单/逗号分隔表达式

// ── 合并 ──
DataSet union(DataSet other)                        // 两个DataSet合并
DataSet union(DataSet[] dataSets)                   // 多个DataSet合并

// ── 排序/截取 ──
DataSet orderBy(String[] fields)                    // 排序："field desc"/"field asc"
DataSet top(int length)                             // 取前N条
DataSet topBy(int top, String[] orderBy)            // 排序后取前N条
DataSet limit(int start, int length)                // 分页取数据
DataSet range(int start, int length)                // 范围取数据

// ── 聚合函数（不分组） ──
int count(String field, boolean distinct)            // 计数

// ── 去重/分割 ──
DataSet distinct()                                   // 去重
DataSet[] splitByFilter(String[] filterExprs, boolean includeOthers) // 按条件分割
DataSet[] splitByGroup(String[] groupFields)         // 按分组字段分割

// ── 自定义处理 ──
DataSet reduceGroup(ReduceGroupFunction fun)         // 自定义reduce
DataSet reduceGroup(ReduceGroupFunctionWithCollector fun) // 带Collector的reduce
DataSet map(MapFunction function)                    // 自定义map
DataSet executeSql(String sql)                       // SQL方式处理
DataSet executeSql(String sql, SqlHint hint)         // SQL+优化提示

// ── 状态/元数据 ──
RowMeta getRowMeta()                                 // 获取元数据
boolean isEmpty()                                    // 是否为空
boolean hasNext()                                    // 是否有下一行
Row next()                                           // 获取下一行
DataSet copy()                                       // 复制（遍历前必须copy）
void close()                                         // 关闭释放资源
void print(boolean copy)                             // 打印调试

// ── Hash关联 ──
HashJoinDataSet hashJoin(HashTable hashTable, String leftJoinKeyField, String[] hashTableSelectFields)
HashJoinDataSet hashJoin(HashTable hashTable, String leftJoinKeyField, String[] hashTableSelectFields, boolean includeNotExist)
HashTable toHashTable(String keyField)               // DataSet转HashTable

// ── 缓存 ──
CachedDataSet cache(CacheHint cacheHint)
CachedDataSet.Builder cacheBuilder(CacheHint hint)
```

#### 3. GroupbyDataSet 链式方法

```java
// groupBy() 返回后可链式调用以下方法，最后 .finish() 返回 DataSet
GroupbyDataSet sum(String field)                     // 求和
GroupbyDataSet max(String field)                     // 最大值
GroupbyDataSet min(String field)                     // 最小值
GroupbyDataSet avg(String field)                     // 平均值
GroupbyDataSet maxP(String orderField, String valueField) // 条件最大值（取orderField最大行的valueField）
GroupbyDataSet minP(String orderField, String valueField) // 条件最小值
GroupbyDataSet groupConcat(String srcField, String alias, String separator) // 字符串聚合
GroupbyDataSet agg(String expr, String alias)        // 自定义聚合表达式
GroupbyDataSet customAgg(String field, CustomAggFunction func, String alias) // 自定义聚合函数
DataSet finish()                                     // 结束分组，返回DataSet
```

#### 4. Row 行数据 `kd.bos.algo.Row`

```java
// 通用取值
Object get(int index)
Object get(String field)

// 类型安全取值（报表插件核心操作）
BigDecimal getBigDecimal(int index)
BigDecimal getBigDecimal(String field)               // 报表数值取值最常用
String getString(int index)
String getString(String field)                       // 报表文本取值最常用
Boolean getBoolean(int index)
Boolean getBoolean(String field)
Date getDate(int index)
Date getDate(String field)
Double getDouble(int index)
Double getDouble(String field)
Integer getInteger(int index)
Integer getInteger(String field)
Long getLong(int index)
Long getLong(String field)
Timestamp getTimestamp(int index)
Timestamp getTimestamp(String field)
int size()                                           // 列数
```

#### 5. RowMeta / RowMetaFactory

```java
// RowMetaFactory — 创建元数据
RowMeta RowMetaFactory.createRowMeta(String[] fieldNames, DataType[] dataTypes)

// RowMeta — 读取元数据
String[] getFieldNames()                             // 所有字段别名
Field[] getFields()
Field getField(String nameOrAlias)
Field getField(int index)
int getFieldIndex(String nameOrAlias)
DataType getFieldDataType(int index)
DataType getDataType(int index)
int getFieldCount()
boolean isNullable(int index)
```

#### 6. DataType 枚举值 `kd.bos.algo.DataType`

```java
// 常用类型（报表插件）
DataType.StringType                                  // 字符串
DataType.BigDecimalType                              // BigDecimal（金额、数量）
DataType.IntegerType                                 // 整数
DataType.LongType                                    // 长整型
DataType.DoubleType                                  // 双精度
DataType.BooleanType                                 // 布尔
DataType.DateType                                    // 日期
DataType.TimestampType                               // 时间戳

// 带精度的 BigDecimal
DataType.createBigDecimalType(int precision)
DataType.createBigDecimalType(int precision, int scale)
```

#### 7. ReduceGroupFunction 接口 `kd.bos.algo.ReduceGroupFunction`

```java
// 用途：分组后对每组数据进行自定义处理（如复杂聚合、多列组合计算）
public abstract Iterator<Object[]> reduce(Iterator<Row> iter)
// iter: 分组后每组数据的迭代器
// 返回: 处理后的 Object[] 迭代器（每组返回一行或多行）

// 使用方式
DataSet result = ds.groupBy(new String[]{"org","material"})
    .finish()
    .reduceGroup(iter -> {
        BigDecimal totalQty = BigDecimal.ZERO;
        BigDecimal totalAmt = BigDecimal.ZERO;
        while (iter.hasNext()) {
            Row row = iter.next();
            totalQty = totalQty.add(getBigDecimalValue(row, "qty"));
            totalAmt = totalAmt.add(getBigDecimalValue(row, "amount"));
        }
        List<Object[]> out = new ArrayList<>();
        out.add(new Object[]{/*分组key*/, totalQty, totalAmt});
        return out.iterator();
    });
```

#### 8. CustomAggFunction 接口 `kd.bos.algo.CustomAggFunction`

```java
// 用途：在 groupBy 链中实现自定义聚合逻辑
public abstract T newAggValue()                      // 创建初始聚合值
public abstract T addValue(T aggValue, Object value) // 累加一个原始值
public abstract T combineAggValue(T aggValue1, T aggValue2) // 合并两个聚合值
public abstract Object getResult(T aggValue)         // 获取最终结果
public DataType getResultDataType()                  // 结果数据类型
public String getFunName()                           // 函数名称
```

#### 9. Collector 接口 `kd.bos.algo.Collector`

```java
// 用途：reduceGroup 的输出收集器
void collect(Object[] values)                        // 收集一行数据
```

#### 10. JoinType 枚举 `kd.bos.algo.JoinType`

```java
// 支持的连接类型（通过 join(DataSet, JoinType) 使用）
// 内部类型：inner join, left join, right join, full join, cross join
// 实际使用时推荐直接用 leftJoin()/join()/rightJoin()/fullJoin() 方法
```

### 辅助方法模板

```java
private static final Log logger = LogFactory.getLog(ClassName.class);

/** 安全取 BigDecimal 值，null 返回 ZERO */
private BigDecimal getBigDecimalValue(Row row, String field) {
    Object val = row.get(field);
    if (val == null) return BigDecimal.ZERO;
    if (val instanceof BigDecimal) return (BigDecimal) val;
    try {
        return new BigDecimal(val.toString());
    } catch (NumberFormatException e) {
        return BigDecimal.ZERO;
    }
}

/** 安全取字符串值 */
private String getStringValue(Row row, String field) {
    Object val = row.get(field);
    return val != null ? val.toString() : "";
}

/** 空DataSet安全返回 */
private DataSet emptyDs(String algoKey) {
    return DataSet.createEmpty(algoKey);
}

/** 批量添加空值保护列 */
private DataSet addNullSafeFields(DataSet ds, String[] fields) {
    for (String f : fields) {
        ds = ds.addField("CASE WHEN " + f + " IS NULL THEN 0 ELSE " + f + " END", f);
    }
    return ds;
}
```

---

## 工作流程

### 步骤1：读取技术模板

**支持格式**：`.doc`、`.docx`、`.xlsx`、`.csv`、`.tsv`、`.md`

**首选方式：使用内置文档读取脚本**

```bash
python <skill_dir>/scripts/doc_reader.py "<用户提供的 Template B 文件路径>"
```

脚本会自动检测文件格式并提取内容，自动安装所需依赖（python-docx、openpyxl、pywin32）。
- `.doc` 文件：Windows 下优先使用 win32com，其他平台尝试 LibreOffice 转换
- `.docx` 文件：使用 python-docx
- `.xlsx` 文件：使用 openpyxl
- `.csv`/`.tsv` 文件：自动检测编码
- `.md` 文件：也可直接用 Read 工具读取

### 步骤2：解析技术规格

| 提取项 | 对应章节 | 用途 |
|--------|---------|------|
| 实体标识列表 | 第一部分 | queryDataSet 的 entityName |
| 字段Key映射 | 第二部分 | selectFields 和别名 |
| 关联路径 | 第三部分 | leftJoin/join 链 |
| 过滤编码值 | 第四部分 | QFilter 参数 |
| 取值逻辑 | 第五部分 | 数据源方法逻辑 |
| 常量定义 | 第六部分 | static final 常量 |
| 计算公式 | 第七部分 | addField 表达式 / BigDecimal 方法 |
| 插件结构 | 第八部分 | 类名、包名、基类 |

### 步骤3：检查完整性

必须项缺失时**不生成代码**，列出缺失清单：

- [ ] 报表标识（.dym）
- [ ] 至少一个实体标识
- [ ] 过滤条件字段 key + 编码值
- [ ] 列字段 key 映射
- [ ] 公式列的表达式

### 步骤3.5：元数据验证（推荐，大幅提升代码正确率）

在生成代码前，用内置元数据查询脚本**验证 Template B 中的实体标识和字段 Key 是否真实存在**。
这一步能避免生成包含错误字段名的代码，减少多轮修正。

> **前置检查**：先读取 `<skill_dir>/config.json` 中的 `enabled` 字段。
> - `enabled: true` → 执行以下验证步骤
> - `enabled: false`（默认）→ 跳过验证，在输出中提示"元数据验证已跳过（config.json 中 enabled 为 false），如需验证请修改配置"

#### 验证实体标识是否存在

```bash
python <skill_dir>/scripts/fetch_metadata.py getEntityType <实体标识> --config <skill_dir>/config.json
```

- 实体存在 → 提取字段列表，与 Template B 第二部分的字段 Key 交叉对比
- 实体不存在 → 标识可能有误，暂停生成并提示用户修正

#### 用业务名称反查实体编码

Template B 中如果只写了中文名称没有实体编码：

```bash
python <skill_dir>/scripts/fetch_metadata.py queryFormMeta --name "中文实体名" --config <skill_dir>/config.json
```

#### 验证字段 Key 是否在实体中存在

对每个实体查询字段列表，逐一检查 Template B 填写的字段 Key：

```bash
python <skill_dir>/scripts/fetch_metadata.py getEntityType <实体标识> --config <skill_dir>/config.json
```

验证规则：
- 字段 Key 在输出中存在 → 确认正确
- 字段 Key 不存在但类似名称存在 → 建议修正（如 `material.number` vs `material.name`）
- 字段 Key 完全不存在 → 标记为错误，提示用户修正 Template B

#### 验证 ORM 路径

检查关联路径中涉及的中间实体和字段是否有效：

```bash
# 例如验证 entry.material.group.number 路径
python <skill_dir>/scripts/fetch_metadata.py getEntityType <实体标识> --config <skill_dir>/config.json
# 检查是否有 entry 分录，entry 下是否有 material 字段，material 是否为基础资料类型
```

#### 查询数据库物理信息（可选）

确认字段对应的数据库表名和列名：

```bash
python <skill_dir>/scripts/db_query.py --entity <实体标识> --config <skill_dir>/config.json --limit 1
```

这能帮助验证分表策略（TableGroup）和字段映射是否正确。

### 步骤4：生成代码

按以下顺序生成：

1. **包声明 + Import 标准集**
2. **类定义** — `extends AbstractReportListDataPlugin`
3. **Logger** — `private static final Log logger`
4. **常量区** — 从 Template B 第六部分提取
5. **query() 方法** — 主入口，解析过滤→调用数据源→关联→计算→返回
6. **过滤解析方法** — 按类型拆分（基础资料/日期/多选/字符串）
7. **数据源方法** — 每个实体一个方法，含 QFilter 构建 + queryDataSet + 聚合
8. **公式计算方法** — 如需逐行计算（无法用 addField 表达式完成）
9. **辅助方法** — getBigDecimalValue、getStringValue、emptyDs、addNullSafeFields

### 步骤5：编码规范强制检查

| 规范项 | 检查 | 修复 |
|--------|------|------|
| 无实例字段 | 搜索 `private` 非 static final | 改为局部变量 |
| BigDecimal | 搜索 double/float 运算 | 替换为 BigDecimal |
| AlgoKey 唯一 | 每个查询不同后缀 | 加 `_suffix` |
| 空值安全 | Row.get() 后检查 | getBigDecimalValue |
| NULL 比较 | 搜索 `= null` | 改为 `IS NULL` |
| 日志 | catch 块有 logger.error | 添加 |
| 包路径 | 与项目包命名一致 | 修正 |

### 步骤6：输出

1. 完整 Java 文件（含所有 import）
2. 文件存放路径建议
3. `// TODO:` 标注待确认项

---

## 项目现有报表插件参考（references/ 目录包含完整源码）

> 生成代码时，**优先参考同模块的现有插件风格**。所有源码在 `references/` 目录中，可读取学习。

| 模块 | 代表插件 | 复杂度 | 架构模式 | 源码文件 |
|------|---------|--------|---------|---------|
| macc | `FinProdQtyRptListPlugin` | 高（8数据源+多级JOIN） | Algo Pipeline | `references/FinProdQtyRptListPlugin.java.txt` |
| macc | `ProductStdCostSumRptListPlugin` | 高（动态列+单位换算） | Map-Based Assembly | `references/ProductStdCostSumRptListPlugin.java.txt` |
| macc | `EffectiveCalcResultReportPlugin` | 高（成本子要素透视） | Algo Pipeline | `references/EffectiveCalcResultReportPlugin.java.txt` |
| mmc | `MftOrderSummaryRptListPlugin` | 高（多表关联+行号+排序） | Algo Pipeline | `references/MftOrderSummaryRptListPlugin.java.txt` |
| scmc | `SalorReportListDataPlugin` | 中（汇总+Reduce） | Algo Pipeline | `references/SalorReportListDataPlugin.java.txt` |
| scmc | `SalesRevenueRptListDataPlugin` | 高（Map组装） | Map-Based Assembly | `references/SalesRevenueRptListDataPlugin.java.txt` |
| qmc | `OverallYieldRptListPlugin` | 中（良率计算） | Algo Pipeline | `references/OverallYieldRptListPlugin.java.txt` |
| tpvwm | `ThroughProdReportListDataPlugin` | 中（穿透查询） | Algo Pipeline | `references/ThroughProdReportListDataPlugin.java.txt` |
| tpvwm | `MiManageReportListDataPlugin` | 高（动态字段） | Algo Pipeline | `references/MiManageReportListDataPlugin.java.txt` |

---

## 表达 DNA

- **语气**：直接、明确、不废话
- **决策**：用「必须/禁止/推荐」表达确定性
- **代码**：先展示骨架，再填充细节
- **术语**：精确使用 DataSet/QFilter/FilterInfo/RowMeta，不用模糊描述
- **错误提示**：明确指出原因和解决方案

---

## 生成后验证清单

生成代码后，建议用户：

1. 确认报表元数据字段 key 与代码别名一致
2. 确认实体标识在 BOS 平台可用
3. 确认过滤编码值在基础资料中存在
4. 编译确认无语法错误
5. 部署测试环境验证数据正确性（对照 Template A 的业务校验规则）
