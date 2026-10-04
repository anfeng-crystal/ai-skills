# 项目查询与 DataSet 计算 (QueryUtils & AlgoUtils)

详细知识、官方来源与验证边界：[云端专题](https://chatgpt.com/space/page_152cbf0974d08191b86a51e503a3fae0)。

## TL;DR
- 适用：已有 `kd.cd.common` 依赖的单值/批量查询、DataSet 过滤、聚合和转换。
- `QueryUtils` 负责取数，`AlgoUtils` 负责计算；它们是项目封装，不是平台通用 API。
- 原生查询、`algoKey`、资源所有权和查询结果边界见 [实体查询与 DataSet 计算](../query-dataset.md)；报表流水线交 `kingdee-report`。
- 实体查询无法表达，不等于获得直接 SQL 授权；下面 SQL 入口只用于已明确允许的场景。基础资料缓存加载须按目标缓存合同选择。

## 适用版本与执行合同

本页依据 `kd-cd-cosmic-commons` 的 `RELEASE-26-0424`（声明 Cosmic 7.0+）及本机 7.0 SDK；生成代码前确认目标项目有此构件，其他版本重核签名和行为。实体、字段、编码及状态值均以目标元数据为准。

- **单值与顺序**：`querySingle` 实际以 `orderBys=null, top=1` 查询，无行返回 null；也可能读到字段 null。它不检查唯一性。需要稳定首条时用带业务排序及必要唯一排序键的 `queryDataSet`，再读取所需值。`queryPkByNumber` 使用元数据中的编码/主键字段，不保证编码唯一。
- **集合与映射**：List 保留遇到的行顺序和重复值，Set 去重但不承诺迭代顺序；无排序查询本身不保证顺序。`queryAsMap` 重复键以后遇到的值覆盖，null value 会使其收集器失败，不能用它表示含空值的映射；须明确过滤空值或自行收集并定义冲突规则。泛型返回值不替代字段类型核验。
- **资源**：QueryUtils 的单值/List/Set/Map 帮助方法内部关闭查询集；返回 DataSet 的重载由调用方按所有权释放。`stream` 是顺序流，没有 DataSet 的关闭回调；关闭 Stream 不能代替关闭 DataSet。`listOf`、`setOf`、`dump` 不显式关闭输入，`sumOf` 关闭其内部聚合结果，输入仍按所有权管理。多分支消费沿用 `copy()` 规则；不要把游标 Row 留存为行快照。
- **空值与规模**：先定义空值业务含义，再决定保留、排除或转换。`sumOf` 对空数据集返回零，非空时直接返回聚合字段，不保证非 null；`nullToZero` 只适用于明确把所选字段的空值当零的计算。List/Set/Map/dump 会收集数据，按字段、过滤条件和结果规模控制开销，不能保证 DataSet 在所有场景都更快。

## QueryUtils API 方法

### 1. 单值查询
- `querySingle(String entityId, String field, QFilter... filters)`: 返回首条记录的字段值；无行返回 null，不检查唯一性。
- `querySingleByPk(String entityId, Object pkValue, String field)`: 根据主键获取指定字段数据。
- `queryPkByNumber(String entityId, String number)`: 根据编码查询主键值。

### 2. 集合查询
- `queryAsList(String entityId, String field, QFilter... filters)`: 查询字段值并收集为 List。
- `queryAsSet(String entityId, String field, QFilter... filters)`: 查询字段值并收集为 Set。
- `queryAsMap(String entityId, String keyField, String valueField, QFilter... filters)`: 查询两字段并收集为 Map。
- `queryMatchedPk(String entityId, QFilter... filters)`: 查询满足条件的数据主键数组。
- `queryMatchedPkList(String entityId, QFilter... filters)`: 查询满足条件的数据主键 List。
- `queryMatchedPkSet(String entityId, QFilter... filters)`: 查询满足条件的数据主键 Set。

### 3. 数据集查询
- `queryDataSet(String entityId, String selectFields, QFilter... filters)`: **最常用**。执行实体查询并返回数据集。
- `queryDataSet(String entityId, String selectFields, String orderBys, QFilter... filters)`: 带排序的查询。
- `queryDataSet(String entityId, String selectFields, String orderBys, int top, QFilter... filters)`: 带排序和条数限制。
- `queryDataSet(DBRoute dbRoute, String sql)`: 原生 SQL 查询。
- `queryDataSet(DBRoute dbRoute, String sql, Object[] params)`: 带参数的原生 SQL 查询。
- `queryDataSet(DBRoute dbRoute, SqlBuilder sb)`: 使用 SqlBuilder 的查询。

## AlgoUtils API 方法

### 1. 流处理
- `stream(DataSet dataSet)`: 提供对 DataSet 的 Stream 流支持。

### 2. 过滤与转换
- `filter(DataSet dataSet, Predicate<Row> filter)`: 把 Predicate 委托给 DataSet.filter，返回过滤数据集。
- `nullToZero(DataSet dataSet, String... fields)`: 通过 updateFields 返回转换结果；未指定字段时原样返回输入。

### 3. 聚合计算
- `sumOf(DataSet dataSet, String field)`: 通过 groupBy().sum(field).finish() 聚合并返回 BigDecimal；空集为零，非空聚合值可能为 null。
- `listOf(DataSet dataSet, String field)`: 将数据集的一列提取为 List。
- `listOf(DataSet dataSet, Function<Row, T> function)`: 自定义函数提取为 List。
- `setOf(DataSet dataSet, String field)`: 将数据集的一列提取为 Set。
- `setOf(DataSet dataSet, Function<Row, T> function)`: 自定义函数提取为 Set。

### 4. 信息获取
- `fieldsOf(DataSet dataSet)`: 获取 DataSet 中字段数组。
- `sizeOf(DataSet dataSet)`: 遍历并关闭内部 copy 后返回行数，不是常数时间的元数据读取。
- `dump(DataSet dataSet, String... fields)`: 返回 Map<String, List<Object>>，键是列名、值是该列逐行的值，不是按字段值分组；null 输入或无行返回空 Map。

### 5. 数据集创建
- `newDataSet(DynamicObjectCollection coll)`: 从 DynamicObjectCollection 创建 DataSet。
- `newDataSet(Map<String, DataType> metaMap, List<Object[]> seqRows)`: 按 Map 迭代顺序定义列，Object[] 必须使用相同列序；需要固定列序时使用 LinkedHashMap 或数组重载。
- `newDataSet(String[] fields, DataType[] dataTypes, List<Object[]> seqRows)`: 根据字段定义创建。
- `newDataSet(RowMeta rowMeta, List<Object[]> seqRows)`: 根据 RowMeta 创建。
- `emptyDataSet(Map<String, DataType> metaMap, int initialSize)`: 创建 initialSize 条全 null 行；initialSize 是行数，不是容量。
- `emptyDataSet(RowMeta rowMeta, int initialSize)`: 按 RowMeta 创建 initialSize 条全 null 行。
- `appendNullRow(DataSet dataSet, int size)`: 构造 size 条全 null 行；非空输入的副本与新行调用 union，返回结果集。

### 6. 行元数据操作
- `rowAddField(Row row, String field, DataType dataType, Object value)`: 返回追加字段后的新 Row，不原地修改；实现要求输入是 AbstractRow，任意 Row 实现并不适用。
- `rowMetaAddField(RowMeta rowMeta, String field, DataType dataType)`: 返回追加字段后的新 RowMeta；原字段按原顺序保留。
- `dumpRowMeta(RowMeta rowMeta)`: 返回字段名到 DataType 的 HashMap，不承诺原列顺序。

### 7. 调试输出
- `print(DataSet dataSet)`: 对副本打印全部数据；大结果应指定 top 并控制输出范围。
- `print(DataSet dataSet, int top)`: 打印前 N 条。
- `print(DataSet dataSet, int top, boolean withJavaType)`: 带类型打印。

## 示例代码

### DataSet 组合查询与计算
```java
package kd.cd.common.demo;

import kd.cd.common.util.QueryUtils;
import kd.cd.common.util.AlgoUtils;
import kd.bos.algo.DataSet;
import kd.bos.orm.query.QCP;
import kd.bos.orm.query.QFilter;
import java.math.BigDecimal;
import java.util.List;

public class QueryDemo {
    public void execute() {
        // 1. 查询已审核单据及其金额
        QFilter filter = new QFilter("status", QCP.equals, "C");
        try (DataSet ds = QueryUtils.queryDataSet("my_bill", "id,totalamount", filter.toArray());
             DataSet dsForSum = ds.copy();
             DataSet filtered = AlgoUtils.filter(ds, row -> {
                 // 本场景排除未知金额，不把它改写为零
                 BigDecimal amount = row.getBigDecimal("totalamount");
                 return amount != null && amount.compareTo(BigDecimal.valueOf(1000)) > 0;
             })) {
            // 2. 保留聚合返回值；非空集的合计仍可能为 null
            BigDecimal sum = AlgoUtils.sumOf(dsForSum, "totalamount");

            // 3. 提取高金额单据ID
            List<Object> ids = AlgoUtils.listOf(filtered, "id");
        }
    }
}
```

### 快速查询示例
```java
import kd.cd.common.util.QueryUtils;
import kd.bos.orm.query.QFilter;
import kd.bos.orm.query.QCP;
import java.util.Map;
import java.util.Set;

public class QuickQueryDemo {
    public void quickQuery() {
        Object pk = QueryUtils.queryPkByNumber("my_bill", "BILL001");
        if (pk != null) {
            String name = QueryUtils.querySingleByPk("my_bill", pk, "name");
        }
        QFilter filter = new QFilter("status", QCP.equals, "C");
        Set<String> names = QueryUtils.queryAsSet("my_bill", "name", filter.toArray());

        // 本映射明确排除 name 为 null 的行；若业务需保留，改为手动收集
        QFilter namePresent = new QFilter("name", QCP.is_notnull, null);
        Map<Object, String> pkNameMap = QueryUtils.queryAsMap(
            "my_bill", "id", "name", filter, namePresent);
    }
}
```

### 已授权的 SQL 查询

此例保留参数化 SQL 入口，不构成直接 SQL 授权；先确认路由、表和字段。字符串重载经过项目 `DbUtils.fitSql` 后委托 `DB.queryDataSet`，不要假定 SQL 会逐字原样提交。

```java
import kd.cd.common.util.QueryUtils;
import kd.cd.common.util.AlgoUtils;
import kd.bos.algo.DataSet;
import kd.bos.db.DBRoute;
import java.util.List;

public class SqlQueryDemo {
    public void sqlQuery(DBRoute dbRoute) {
        String sql = "SELECT id, name FROM my_table WHERE status = ?";
        try (DataSet ds = QueryUtils.queryDataSet(dbRoute, sql, new Object[]{"C"})) {
            List<Object> ids = AlgoUtils.listOf(ds, "id");
        }
    }
}
```

## 实践建议

- 只选择必要字段，在查询阶段过滤；需要限制数量时使用明确的 top/排序重载。DataSet、实体加载和结果集合的选择取决于业务与规模，性能结论须在目标环境测量。
- 在调用方持有并消费的范围内用 try-with-resources 关闭 DataSet。资源未释放有泄露风险，不等于必然 OOM；返回给报表引擎消费的 DataSet 不能在返回前关闭。
- `nullToZero`、`rowAddField`、`rowMetaAddField` 等返回结果须接住，不能仅调用后假定原对象已修改；无字段的 `nullToZero` 返回原输入，注意别名和所有权。
- 优先复用界面模型已有数据，避免循环和重复查询；确需分批时按业务范围、必要字段及有界结果设计。SQL 的业务值使用参数，不能拼接未经确认的标识符。
