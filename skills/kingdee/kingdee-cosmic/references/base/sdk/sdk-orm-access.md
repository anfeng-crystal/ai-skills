# ORM、QFilter 与底层数据库查询

详细知识与证据边界见 [云端 ORM 查询知识](https://chatgpt.com/space/page_f18eec3cfaa48191a6483231e000ea9c)。

## 选路与版本

按实体元数据查询优先使用 ORM/QFilter；需要底层数据库访问时，再核定路由、KSQL 或数据库方言。以下重载来自实际 7.0 的 `bos-ormengine`、`bos-dataentity`、`bos-algo`、`bos-dbengine`；公开 V7.0.1 文档辅助核对。

精确 API 用 [SDK Helper](../../../../kingdee-sdk-helper/SKILL.md) 的查询脚本、目标项目依赖或官方版本文档核验，不依赖某个宿主独有工具名称。实体属性先按真实元数据确认；报表取数、DataSet 流水线另看 [查询与 DataSet](../../adv/query-dataset.md)。

## ORM：保留真实重载，控制查询范围

|调用|返回/边界|
|---|---|
|`queryOne(String entityName, QFilter[] filters)`|真实存在，返回 `DynamicObject`；本地实现会加载全列及关联数据，查询简单实体且明确需要完整对象时再用。|
|`queryOne(String entityName, String selectFields, QFilter[] filters)`|返回 `DynamicObject`；无记录可为 null，不替调用方验证业务条件唯一性。|
|`query(String entityName, String selectFields, QFilter[] filters)`|返回 `DynamicObjectCollection`，按需选择字段。|
|`queryDataSet(String algoKey, String entityName, String selectFields, QFilter[] filters, String orderBys)`|返回 `DataSet`；消费完成后关闭，不凭返回类型保证比集合查询更快。|

```java
import kd.bos.orm.ORM;
import kd.bos.orm.query.QFilter;
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.dataentity.entity.DynamicObjectCollection;
import kd.bos.algo.DataSet;
import java.util.function.Consumer;

public final class OrmExamples {
    public static DynamicObject one(String entityName, String fields, QFilter[] filters) {
        return ORM.create().queryOne(entityName, fields, filters);
    }
    public static DynamicObjectCollection list(String entityName, String fields, QFilter[] filters) {
        return ORM.create().query(entityName, fields, filters);
    }
    public static void dataSet(String algoKey, String entityName, String fields,
            QFilter[] filters, Consumer<DataSet> consume) {
        try (DataSet ds = ORM.create().queryDataSet(algoKey, entityName, fields, filters, "id desc")) {
            consume.accept(ds);
        }
    }
}
```

调用方提供真实实体、字段、排序属性和限定范围；上例假定实体有 `id`，仅用于已限定规模的结果。大量数据应按实际重载设置分页/数量限制，避免 `*` 和一次连接多个大分录。回调在 DataSet 关闭前完成消费，不能把资源带到异步线程或留待稍后使用。

## QFilter：组合会改变对象，通配符取决于入口

- 比较常量：`QCP.equals`、`not_equals`、`large_than`、`less_than`、`large_equals`、`less_equals`；集合使用 `in` / `not_in`。实际 7.0 没有 `QCP.between`，闭区间用 `>=` 与 `<=` 组合。
- `and(QFilter)` / `or(QFilter)` 会修改当前实例并返回它。要从同一基础条件建立不同分支，使用独立条件或 `copy()`；不要复用已被追加的实例。
- `new QFilter(property, QCP.like, value)` 保留调用方的模式，例如 `"C%"`。自动补前后 `%` 属于静态 `QFilter.like(property, value)` / `notLike`。这里存在版本依据差异：官方 V7.0.1 注释称值不含 `%` / `_` 才补齐；本机 7.0 的 `QMatches.appendWildcard` 仅检查未转义的 `%`，仅含 `_` 仍会补齐。需要精确模式时显式传入，并按目标依赖核对转义规则，不能把通配符默认当普通字符。
- `QFilter.of(String, Object...)` 支持表达式参数；没有单参数 `and(String)`。表达式字段来自已核元数据，外部值走参数，不能拼接成表达式文本。

```java
import kd.bos.orm.query.QFilter;
import kd.bos.orm.query.QCP;

public final class FilterExamples {
    public static QFilter approvedAbove(String status, Number threshold) {
        return QFilter.of("status = ?", status)
                .and(QFilter.of("amt > ?", threshold));
    }
    public static QFilter independentBranch(QFilter base, Number threshold) {
        return base.copy().and("amt", QCP.large_than, threshold);
    }
    public static QFilter approvedOrType(String status, String type) {
        return new QFilter("status", QCP.equals, status)
                .or(new QFilter("type", QCP.equals, type));
    }
    public static QFilter closedRange(Number lower, Number upper) {
        return new QFilter("amt", QCP.large_equals, lower)
                .and("amt", QCP.less_equals, upper);
    }
    public static QFilter customerPrefix() {
        return new QFilter("customer.number", QCP.like, "C%");
    }
    public static QFilter customerContains() {
        return QFilter.like("customer.number", "C");
    }
}
```

这些字段是示意，基础资料属性可用 `customer.number`、分录属性可用 `entryentity.material` 这类路径，但必须在目标实体存在。官方 QFilter 文档提示不存在的引用属性可能退化为恒真条件；使用 QFilter 不等于自动验证元数据或业务权限。大量同字段 OR 可评估 IN，仍需结合真实数据规模与执行计划判断。

## KSQL、原生 SQL 与 DBRoute

`kd.bos.servicehelper.DBServiceHelper` 的实际 7.0 API 是主键/序列相关服务，没有旧卡列出的 `executeQuery` / `executeUpdate`。底层查询与更新可使用 `kd.bos.db.DB` 的真实重载：

|调用|返回值|
|---|---|
|`DB.queryDataSet(String algoKey, DBRoute route, String sql, Object[] params)`|`DataSet`，及时关闭|
|`DB.update(DBRoute route, String sql, Object[] params)`|`int`，影响行数|
|`DB.execute(DBRoute route, String sql, Object[] params)`|`boolean`，执行结果标记；不是影响行数|

```java
import kd.bos.db.DB;
import kd.bos.db.DBRoute;
import kd.bos.algo.DataSet;
import java.util.function.Consumer;

public final class DbExamples {
    public static void query(String algoKey, String routeKey, String sql,
            Object[] params, Consumer<DataSet> consume) {
        try (DataSet ds = DB.queryDataSet(algoKey, DBRoute.of(routeKey), sql, params)) {
            consume.accept(ds);
        }
    }
    public static int update(String routeKey, String sql, Object[] params) {
        return DB.update(DBRoute.of(routeKey), sql, params);
    }
    public static boolean execute(String routeKey, String sql, Object[] params) {
        return DB.execute(DBRoute.of(routeKey), sql, params);
    }
}
```

`routeKey` 必须是目标环境已核定的路由；SQL 中的表/列和语句结构由开发者确认，外部值用 `?` 与 `Object[]` 参数绑定。KSQL 与原生 SQL 语法不同；本地 7.0 转换实现识别以 `/*dialect*/` 开头的语句后跳过常规 KSQL 翻译，前置扩展处理仍可能执行。它不是绕过整个平台处理流程或跨数据库兼容的保证。不能把集成云连接器的 `@fi` / `query_list` 写法直接套进 Java。三参 `ORM.queryDataSet(algoKey, text, params)` 在本地实现解析的是 OQL，不能见到文本参数就当作 KSQL。

底层 DML 不替代保存/操作服务的业务校验、插件与事务合同。业务单据更新优先沿用已确认的业务服务；确需底层写入时明确已有授权、事务、影响范围与缓存处理。以上方法示例只保留调用能力，没有执行数据库操作。

## 依据与验证范围

- [ORM查询性能避坑指南](https://vip.kingdee.com/knowledge/606855826359280384)，更新 2026-07-30，无版本；性能建议不等于 API 废弃或不存在。
- [数据库操作服务帮助类](https://vip.kingdee.com/knowledge/255632464692472832)，更新 2024-04-17，无版本；API 归属另由实际 7.0 签名与编译确认。
- [QFilter · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/orm/query/QFilter.html)、[DB · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/db/DB.html)。公开文档未列出某重载不等于实际依赖没有。
- [当前账套连接器执行SQL场景](https://vip.kingdee.com/knowledge/611122490491598848)，更新 2026-07-30，无版本；仅借此说明 KSQL/方言边界，不外推其连接器或存储过程合同。

Java 编译验证只覆盖类型/签名，不验证字符串中的 SQL/KSQL、元数据、路由、权限、实际查询结果或事务效果。
