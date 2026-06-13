# 报表架构模式

字段名、实体编码均为占位示例,实际以元数据为准。

## 模式 A:Algo Pipeline(推荐,约 90% 场景)
**何时用**:数据来自 ORM 实体,可表达为 查询→关联→聚合 流水线,无复杂行级转换。
**步骤**:查询各数据源 DataSet → 链式 `leftJoin`(首选)/`join` → `groupBy().sum()/max()/min().finish()` → `addField()` 计算列 → 返回。

```java
public DataSet query(ReportQueryParam param, Object o) throws Throwable {
    FilterInfo f = param.getFilter();
    if (f == null) return null;
    Object orgId = parseOrgId(f);
    DataSet a = getDsA(orgId);          // 数据源 A
    DataSet b = getDsB(orgId);          // 数据源 B
    DataSet r = a.leftJoin(b)
        .on("keycol", "keycol")
        .select(a.getRowMeta().getFieldNames(), b.getRowMeta().getFieldNames())
        .finish();
    r = r.groupBy(new String[]{"dim1", "dim2"}).sum("qty").sum("amount").finish();
    r = r.addField("CASE WHEN q1 IS NULL THEN 0 ELSE q1 END - CASE WHEN q2 IS NULL THEN 0 ELSE q2 END", "balqty");
    return r;
}
```

## 模式 B:Map-Based Assembly(复杂转换)
**何时用**:需逐行复杂转换(单位换算查表、条件分支价格、运行时动态列),DataSet 表达式表达不了。
**步骤**:查询源 DataSet → 逐行遍历(`for (Row row : ds.copy())`)手工转 `Object[]` → `RowMetaFactory.createRowMeta(fields, types)` 定义结构 → `Algo.create(key).createDataSet(new CollectionInput(rowMeta, rows))`。

```java
String[] fields = {"dim1", "dim2", "qty", "amount", "unitprice"};
DataType[] types = {DataType.StringType, DataType.StringType,
    DataType.BigDecimalType, DataType.BigDecimalType, DataType.BigDecimalType};
Collection<Object[]> rows = new ArrayList<>();
for (Row row : sourceDs.copy()) {
    Object[] arr = new Object[fields.length];
    arr[0] = row.getString("dim1");
    BigDecimal qty = getBigDecimalValue(row, "baseqty");
    arr[2] = qty.multiply(queryConversionFactor(row.getString("fromunit"), row.getString("tounit")));
    rows.add(arr);
}
RowMeta meta = RowMetaFactory.createRowMeta(fields, types);
return Algo.create(algoKey + "_assembled").createDataSet(new CollectionInput(meta, rows));
```

## 模式 C:AlgoX Pipeline(新版成本模块)
**何时用**:成本卷算(CAD 模块)等明确要求 `AlgoX`/`DataSetX`/`JobSession` 的场景;**默认不用**。
```java
AlgoX algoX = AlgoX.createSession(name, name);
DataSetX dsX = algoX.queryDataSetX(entityName, selectFields, filters);
```

## 选型速记
ORM 直取 + JOIN/聚合可表达 → A;逐行换算/条件分支/动态列 → B;成本卷算且指定 AlgoX → C。
