# 实体查询与 DataSet 计算

## 选型与边界

- 单条、集合与 DataSet 实体查询使用 `QueryServiceHelper`；基础资料按需要使用 `BusinessDataServiceHelper.loadFromCache`。
- 项目已有 `QueryUtils` / `AlgoUtils` 时优先复用。它们属于 `kd.cd.common` 项目封装，不是平台通用 API；方法与依赖先按目标工程核验。[封装参考](adv/query-dataset.md)保留查询、过滤、聚合、转换、数据集创建、行元数据及调试接口，不在此重复维护清单。
- 报表取数、复杂 JOIN/UNION、分组聚合及 Algo API 精确签名交 [kingdee-report](../../kingdee-report/SKILL.md)。
- 保留入口“不直接 SQL”的业务实现边界。实体查询无法表达不自动获得裸 SQL 授权；独立只读核对或另有明确批准的 SQL 场景见下文。

查询定义可查[官方 Cosmic V7.0.1 QueryServiceHelper](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/servicehelper/QueryServiceHelper.html)。本页原生签名以 7.0 依赖核验，不据文档版本推定该依赖的具体补丁号或其他版本兼容；生成目标代码仍按入口核对实际依赖。

## 平台查询入口

`kd.bos.servicehelper.QueryServiceHelper`：

```java
static DynamicObject queryOne(String entityName, String selectFields, QFilter[] filters)
static boolean exists(String entityName, QFilter[] filters)
static DynamicObjectCollection query(String entityName, String selectFields, QFilter[] filters)
static DynamicObjectCollection query(String entityName, String selectFields, QFilter[] filters, String orderBys)
static DataSet queryDataSet(String algoKey, String entityName, String selectFields, QFilter[] filters, String orderBys)
static DataSet queryDataSet(String algoKey, String entityName, String selectFields, QFilter[] filters, String orderBys, int top)
```

`algoKey` 是查询标识，`entityName` 才是实体编码；两者都是 `String`，传反仍可能编译成功。示例使用不同值，不能把两处都写成实体名来掩盖顺序。`selectFields` 是逗号分隔的字段字符串；字段、分录路径及状态编码须由目标元数据确认。

该 7.0 依赖将上述 `queryDataSet` 重载标为弃用但仍提供它们。优先采用目标工程已验证的封装或替代接口；不能仅凭弃用标记猜测新重载，或将另一版本签名直接用于当前工程。

`query` 返回扁平查询结果，不用于直接修改、保存；要更新实体时先查询主键，再按目标加载完整实体包。只判断存在时用 `exists`。

## 原生 DataSet 示例

示例同时计算已审核单据金额合计和高金额单据 ID；没有项目封装时使用此原生写法。多分支读取先复制，独占消费的结果不必无条件再复制。

```java
package kd.cd.common.demo;

import kd.bos.algo.DataSet;
import kd.bos.algo.Row;
import kd.bos.orm.query.QCP;
import kd.bos.orm.query.QFilter;
import kd.bos.servicehelper.QueryServiceHelper;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

public class QueryDemo {
    public void execute() {
        QFilter filter = new QFilter("status", QCP.equals, "C");
        String algoKey = QueryDemo.class.getName() + "_approved";
        try (DataSet ds = QueryServiceHelper.queryDataSet(
                     algoKey, "my_bill", "id,totalamount", filter.toArray(), null);
             DataSet dsForSum = ds.copy();
             DataSet filtered = ds.filter("totalamount > 1000")) {
            BigDecimal sum = BigDecimal.ZERO;
            for (Row row : dsForSum) {
                BigDecimal amount = row.getBigDecimal("totalamount");
                if (amount != null) {
                    sum = sum.add(amount);
                }
            }
            List<Object> ids = new ArrayList<>();
            for (Row row : filtered) {
                ids.add(row.get("id"));
            }
            // 在此使用 sum 和 ids；离开作用域释放本方法拥有的数据集。
        }
    }
}
```

### 小型查询

```java
public void quickQuery() {
    DynamicObject row = QueryServiceHelper.queryOne("my_bill", "id,name",
            new QFilter[]{new QFilter("number", QCP.equals, "BILL001")});
    boolean exists = QueryServiceHelper.exists("my_bill",
            new QFilter[]{new QFilter("number", QCP.equals, "BILL001")});
    QFilter filter = new QFilter("status", QCP.equals, "C");
    DynamicObjectCollection rows = QueryServiceHelper.query("my_bill", "id,name", filter.toArray());
}
```

此片段还需导入 `kd.bos.dataentity.entity.DynamicObject` 与 `DynamicObjectCollection`。

## 已批准 SQL 场景的入口

`QueryServiceHelper` 不提供 `DBRoute` SQL 取数重载。明确批准的原生 SQL 取数使用目标已核验的 `kd.bos.db.DB`：

```java
static DataSet queryDataSet(String algoKey, DBRoute dbRoute, String sql)
static DataSet queryDataSet(String algoKey, DBRoute dbRoute, String sql, Object[] params)
```

需要绑定参数时保留参数数组；不拼接 SQL/KSQL 条件。路由、表和字段来自已确认的目标合同，以下占位示例本身不授权查询：

```java
public List<Object> sqlQuery(DBRoute dbRoute) {
    String sql = "SELECT id, name FROM my_table WHERE status = ?";
    List<Object> ids = new ArrayList<>();
    try (DataSet ds = DB.queryDataSet(
            "approved_readonly_lookup", dbRoute, sql, new Object[]{"C"})) {
        for (Row row : ds) {
            ids.add(row.get("id"));
        }
    }
    return ids;
}
```

此片段使用 `kd.bos.db.DB`、`kd.bos.db.DBRoute` 及前例的 DataSet、Row、集合导入。

## 资源与性能

- 只选必要字段，在查询阶段使用结构化过滤；数据量、分录展开和关联方式决定成本，不预设 DataSet 一定快于对象集合。
- 方法独占的数据集用 `try-with-resources` 或 `finally` 关闭；需要返回给报表引擎的 DataSet 不在返回前关闭。多分支副本也要明确拥有者并释放。
- 行访问器不缓存成结果列表；保留所需字段值。金额使用 `BigDecimal`，空值按业务口径处理，不能一律假定等于零。
- 复用模型已有数据，避免循环查库或重复取数；确需批量查询时限定字段和范围。
