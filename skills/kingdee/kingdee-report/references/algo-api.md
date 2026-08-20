# Algo API 精确签名集

报表取数 Algo/DataSet 常用 API 的精确签名,按功能分组。本文件为报表签名的单一权威来源;与项目实际依赖版本不一致时以项目 jar/Javadoc 为准并标注。

## 工厂 `kd.bos.algo.Algo`
```java
static Algo create(String algoKey)
static AlgoContext newContext()
DataSet createDataSet(Collection<Object[]> rowList, RowMeta rowMeta)
DataSet createDataSet(Iterator<Object[]> it, RowMeta rowMeta)
DataSet createDataSet(ResultSet rs, RowMeta rowMeta)
DataSet createDataSet(Input[] inputs)            // OrmInput/CollectionInput
DataSetBuilder createDataSetBuilder(RowMeta rowMeta)
```

## 资源作用域 `kd.bos.algo.AlgoContext`
```java
interface AlgoContext extends java.io.Closeable, java.lang.AutoCloseable
void close()
```
`Algo.newContext()` 创建当前 Algo 资源作用域；离开 try-with-resources 时会关闭该作用域内创建的 `DataSet`。适合一个方法产生多个派生 DataSet 的异常安全收口：
```java
try (AlgoContext ignored = Algo.newContext()) {
    DataSet source = QueryServiceHelper.queryDataSet(...);
    DataSet result = source.filter(...).groupBy(...).sum(...).finish();
    // 使用 result；正常返回或抛异常都会由上下文统一释放资源。
}
```

## 查询 `kd.bos.servicehelper.QueryServiceHelper`
```java
static DataSet queryDataSet(String algoKey, String entityName,
        String selectFields, QFilter[] filters, String orderBy)
static DynamicObjectCollection query(String entityName,
        String[] selectFields, QFilter[] filters)
```
`selectFields` 语法:`"field"`、`"field alias"`、`"material.number no"`(ORM 路径+别名)、`"'PCS' unit"`(字符串常量)、`"0.0 rate"`(数字常量)、`"CASE WHEN ... END x"`。

## DataSet `kd.bos.algo.DataSet`
字段:
```java
DataSet addField(String expr, String alias)
DataSet addFields(String[] exprs, String[] aliases)
DataSet updateField(String field, String expr)
DataSet removeFields(String[] fields)
DataSet addNullField(String alias)
```
关联(返回 `JoinDataSet`,链式 `.on(l,r).select(lFields[], rFields[]).finish()`):
```java
JoinDataSet leftJoin(DataSet right)
JoinDataSet join(DataSet right)                  // 内连接
JoinDataSet join(DataSet right, JoinType type)
JoinDataSet rightJoin(DataSet right)
JoinDataSet fullJoin(DataSet right)
```
分组(返回 `GroupbyDataSet`):
```java
GroupbyDataSet groupBy()
GroupbyDataSet groupBy(String[] groupFields)
GroupbyDataSet groupBy(String[] groupFields, boolean[] orderByDescs)
```
过滤/选择/合并/排序:
```java
DataSet filter(String expr)
DataSet filter(String expr, Map<String,Object> params)
DataSet where(String expr)
DataSet select(String[] exprs)
DataSet select(boolean distinct, String[] exprs)
DataSet union(DataSet other)
DataSet union(DataSet[] dataSets)
DataSet orderBy(String[] fields)                 // "field desc"/"field asc"
DataSet top(int n)
DataSet topBy(int top, String[] orderBy)
DataSet distinct()
DataSet[] splitByFilter(String[] exprs, boolean includeOthers)
```
状态/元数据:
```java
RowMeta getRowMeta()
boolean isEmpty()
DataSet copy()                                   // 遍历前必须 copy
void close()
```

## GroupbyDataSet `kd.bos.algo.GroupbyDataSet`
```java
GroupbyDataSet sum(String field)
GroupbyDataSet max(String field)
GroupbyDataSet min(String field)
GroupbyDataSet avg(String field)
GroupbyDataSet count(String field)
GroupbyDataSet countDistinct(String field)
GroupbyDataSet maxP(String orderField, String valueField)   // 按 orderField 最大行的 valueField
GroupbyDataSet minP(String orderField, String valueField)
GroupbyDataSet groupConcat(String srcField, String alias, String separator)
GroupbyDataSet agg(String expr, String alias)
DataSet finish()
```

## Row `kd.bos.algo.Row`
```java
BigDecimal getBigDecimal(String field)           // 数值取值最常用
String getString(String field)
Boolean getBoolean(String field)
Date getDate(String field)
Integer getInteger(String field)
Long getLong(String field)
Object get(String field)
```

## RowMeta / RowMetaFactory / DataType
```java
static RowMeta RowMetaFactory.createRowMeta(String[] fieldNames, DataType[] dataTypes)
String[] RowMeta.getFieldNames()
int RowMeta.getFieldIndex(String nameOrAlias)
// DataType 常量:StringType / BigDecimalType / IntegerType / LongType /
//   DoubleType / BooleanType / DateType / TimestampType
DataType DataType.createBigDecimalType(int precision, int scale)
```

## FilterInfo `kd.bos.entity.report.FilterInfo`
```java
DynamicObject getDynamicObject(String field)             // F7 单选
DynamicObjectCollection getDynamicObjectCollection(String field) // F7 多选
Date getDate(String field)
String getString(String field)
boolean getBoolean(String field)
long getLong(String field)
List<FilterItemInfo> getFilterItems()
FilterItemInfo getFilterItem(String field)               // .getValue()/.getCompareType()/.getPropName()
```

## QFilter `kd.bos.orm.query.QFilter`
```java
new QFilter(String field, String op, Object value)       // op: "=","!=","in",">",">=","<","<=","like"
QFilter and(String field, String op, Object value)
QFilter and(QFilter other)
QFilter or(QFilter other)
```
组装推荐:`List<QFilter>` 动态收集后 `.toArray(new QFilter[0])`;可选条件按需 add。

## 标准 import 集
```java
import kd.bos.algo.Algo;
import kd.bos.algo.AlgoContext;
import kd.bos.algo.DataSet;
import kd.bos.algo.DataType;
import kd.bos.algo.GroupbyDataSet;
import kd.bos.algo.JoinDataSet;
import kd.bos.algo.Row;
import kd.bos.algo.RowMeta;
import kd.bos.algo.RowMetaFactory;
import kd.bos.algo.input.CollectionInput;
import kd.bos.entity.report.AbstractReportListDataPlugin;
import kd.bos.entity.report.FilterInfo;
import kd.bos.entity.report.FilterItemInfo;
import kd.bos.entity.report.ReportQueryParam;
import kd.bos.orm.query.QFilter;
import kd.bos.servicehelper.QueryServiceHelper;
import kd.bos.servicehelper.BusinessDataServiceHelper;
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.dataentity.entity.DynamicObjectCollection;
import kd.bos.logging.Log;
import kd.bos.logging.LogFactory;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.*;
```
