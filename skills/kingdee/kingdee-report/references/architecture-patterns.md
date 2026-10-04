# 报表架构模式

字段名、实体编码均为占位示例，实际以元数据为准。下列代码用于架构和 API 检索；生成目标实现前按 `../SKILL.md` 核对已确认产品/版本与具体签名，不把未标版本的示例直接当作目标兼容证明。

## 模式 A:Algo Pipeline(查询、关联与聚合)
**何时用**:数据来自 ORM 实体,可表达为 查询→关联→聚合 流水线,无复杂行级转换。
**步骤**:查询各数据源 DataSet → 按保留行要求选择 `leftJoin`/`join` → `groupBy().sum()/max()/min().finish()` → `addField()` 计算列 → 返回。

本例 A 提供维度与 `q1`，B 提供 `q2`，并约定 B 的 `keycol` 唯一；右侧一对多会放大左侧数量，需先按业务统计粒度处理。只选下游需要的列，聚合后的表达式只能使用分组列和聚合输出，不能继续引用已被投影移除的字段。

```java
public DataSet query(ReportQueryParam param, Object o) throws Throwable {
    FilterInfo f = param.getFilter();
    if (f == null) return null;
    Object orgId = parseOrgId(f);
    DataSet a = getDsA(orgId);          // 数据源 A
    DataSet b = getDsB(orgId);          // 数据源 B
    DataSet r = a.leftJoin(b)
        .on("keycol", "keycol")
        .select(new String[]{"dim1", "dim2", "q1"}, new String[]{"q2"})
        .finish();
    r = r.groupBy(new String[]{"dim1", "dim2"}).sum("q1").sum("q2").finish();
    r = r.addField("CASE WHEN q1 IS NULL THEN 0 ELSE q1 END - CASE WHEN q2 IS NULL THEN 0 ELSE q2 END", "balqty");
    return r;
}
```

## 模式 B:Map-Based Assembly(复杂转换)
**何时用**:需逐行复杂转换(单位换算查表、条件分支价格、运行时动态列),DataSet 表达式表达不了。
**步骤**:查询源 DataSet → 逐行转换为独立 `Object[]` → 按输出列的顺序与类型定义 `RowMeta` → 从集合构造返回 DataSet。每个输出列都要赋值；业务允许的空值应明确保留，不能用未赋值数组槽位代替字段映射。

本例约定 `sourceDs` 由本方法独占，`amount`、`unitprice` 已按目标报表口径准备好，只换算 `baseqty`；重新计价须另行确认单位、精度与舍入规则。用 `try-with-resources` 关闭已消费的输入，覆盖转换中途异常；返回的新 DataSet 留给调用方消费。确需保留源数据供其他分支复用时才遍历命名的 `copy()`，并同样保证其关闭，不能无条件复制或提前关闭待返回的数据。

```java
String[] fields = {"dim1", "dim2", "qty", "amount", "unitprice"};
DataType[] types = {DataType.StringType, DataType.StringType,
    DataType.BigDecimalType, DataType.BigDecimalType, DataType.BigDecimalType};
Collection<Object[]> rows = new ArrayList<>();
try (DataSet input = sourceDs) {
    for (Row row : input) {
        BigDecimal qty = getBigDecimalValue(row, "baseqty");
        BigDecimal convertedQty = qty.multiply(
            queryConversionFactor(row.getString("fromunit"), row.getString("tounit")));
        rows.add(new Object[]{row.getString("dim1"), row.getString("dim2"),
            convertedQty, row.getBigDecimal("amount"), row.getBigDecimal("unitprice")});
    }
}
RowMeta meta = RowMetaFactory.createRowMeta(fields, types);
return Algo.create(algoKey + "_assembled").createDataSet(new CollectionInput(meta, rows));
```

依据：[社区列转行案例](https://vip.kingdee.com/article/212653611237578240)（作者 cosmic，开发环境 COSMIC V4.0.010.0，2022-04-14；用于字段映射思路，不作新版本 API 证明）、官方 Cosmic V7.0.1 的 [Algo 高级接口](https://dev.kingdee.com/open/detail/sdk/2077750759931262976)（2025-10-27）与 [DataSet 关闭合同](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/algo/DataSet.html)。本例的集合构造、字段值与异常关闭已用本机 7.0 SDK 实跑；目标项目仍按入口规则核对依赖。

## 模式 C:AlgoX Pipeline(新版成本模块)
**何时用**:成本卷算(CAD 模块)等明确要求 `AlgoX`/`DataSetX`/`JobSession` 的场景;**默认不用**。
以下只展示输入构造，`jobName`、`jobTitle`、`algoKey` 和实体/投影/过滤条件由已确认的任务合同提供：
```java
import kd.bos.algox.AlgoX;
import kd.bos.algox.JobSession;
import kd.bos.algox.DataSetX;
import kd.bos.algo.input.OrmInput;

JobSession session = AlgoX.createSession(jobName, jobTitle);
DataSetX dsX = session.fromInput(
    new OrmInput(algoKey, entityName, selectFields, filters));
```

`createSession()` 返回 `JobSession`；输入经 `fromInput()` 形成 `DataSetX`。不要在 `AlgoX` 或 `JobSession` 上调用不存在的 `queryDataSetX()`。该片段还未配置输出、提交任务或取得最终 `DataSet`，不能直接作为 `query()` 返回结果。完整实现须再按目标版本核对输出、提交超时和结果读取合同。

版本依据：官方 V7.0.1 [AlgoX](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/algox/AlgoX.html) / [JobSession](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/algox/JobSession.html)；本地 7.0/JDK 8 编译通过，未执行集群任务。[云端知识：案例来源、阶段边界与验证](https://chatgpt.com/space/page_437b17ab03748191b0b1187d41a1ac68)。

## 选型速记
ORM 直取 + JOIN/聚合可表达 → A;逐行换算/条件分支/动态列 → B;成本卷算且指定 AlgoX → C。
