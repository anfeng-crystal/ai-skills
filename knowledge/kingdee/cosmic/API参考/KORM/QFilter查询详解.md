# QFilter 查询详解

> 来源: https://vip.kingdee.com/article/829723040165553920, https://vip.kingdee.com/article/269488809916386048, 基于平台API整理
> 日期: 2026-04-12
> 标签: QFilter, 查询过滤, QCP, QueryServiceHelper, 数据查询

---

## 摘要
QFilter 是金蝶云苍穹 KORM 框架的核心查询过滤机制，通过树形结构表达 SQL 的 WHERE 条件，支持多条件组合、嵌套括号、子查询等复杂查询模式，是数据查询、列表过滤、报表取数的基础工具。

## 适用版本
- 金蝶云苍穹 V5.0+

## 核心概念

### QFilter 本质

QFilter 是一棵条件树，嵌套即括号：

```
        AND
       /   \
      A    OR
          /  \
         B    C
```

等价 SQL：`A AND (B OR C)`

### 基本构造

```java
// 基本语法：new QFilter(字段标识, 比较操作符, 值)
QFilter filter = new QFilter("billno", QCP.equals, "BILL-001");
```

### QCP 操作符一览

| 操作符 | 说明 | SQL 等价 |
|--------|------|----------|
| `QCP.equals` | 等于 | `= value` |
| `QCP.not_equals` | 不等于 | `<> value` |
| `QCP.like` | 模糊匹配 | `LIKE value` |
| `QCP.not_like` | 不模糊匹配 | `NOT LIKE value` |
| `QCP.large_than` | 大于 | `> value` |
| `QCP.large_equals` | 大于等于 | `>= value` |
| `QCP.less_than` | 小于 | `< value` |
| `QCP.less_equals` | 小于等于 | `<= value` |
| `QCP.in` | 在集合中 | `IN (...)` |
| `QCP.not_in` | 不在集合中 | `NOT IN (...)` |
| `QCP.is_null` | 为空 | `IS NULL` |
| `QCP.is_not_null` | 不为空 | `IS NOT NULL` |

## 详细内容

### 一、基本用法

#### 1.1 单条件查询

```java
// 等值查询
QFilter f1 = new QFilter("billstatus", QCP.equals, "C");

// 模糊查询
QFilter f2 = new QFilter("billno", QCP.like, "%2026%");

// 范围查询
QFilter f3 = new QFilter("amount", QCP.large_than, new BigDecimal("1000"));

// IN 查询
QFilter f4 = new QFilter("billstatus", QCP.in, new String[]{"A", "B", "C"});

// 空值判断
QFilter f5 = new QFilter("description", QCP.is_null, null);

// 不为空
QFilter f6 = new QFilter("org", QCP.is_not_null, null);
```

#### 1.2 多条件 AND 组合

```java
// 方式1：数组传参（默认 AND）
QFilter[] filters = new QFilter[]{
    new QFilter("billstatus", QCP.equals, "C"),
    new QFilter("amount", QCP.large_than, new BigDecimal("1000"))
};
// 等价 SQL: billstatus = 'C' AND amount > 1000

// 方式2：链式调用 .and()
QFilter filter = new QFilter("billstatus", QCP.equals, "C")
    .and(new QFilter("amount", QCP.large_than, new BigDecimal("1000")));
```

#### 1.3 OR 组合

```java
// 方式1：使用 .or() 方法
QFilter filter = new QFilter("billstatus", QCP.equals, "A")
    .or(new QFilter("billstatus", QCP.equals, "B"));
// 等价 SQL: billstatus = 'A' OR billstatus = 'B'

// 方式2：使用静态方法 QFilter.or()
QFilter filter = QFilter.or(
    new QFilter("billstatus", QCP.equals, "A"),
    new QFilter("billstatus", QCP.equals, "B")
);
```

### 二、嵌套括号（核心重点）

#### 2.1 A AND (B OR C)

```java
QFilter A = new QFilter("name", QCP.like, "%A%");
QFilter B = new QFilter("number", QCP.equals, "001");
QFilter C = new QFilter("number", QCP.equals, "002");

QFilter filter = QFilter.and(
    A,
    QFilter.or(B, C)
);
// SQL: name LIKE '%A%' AND (number = '001' OR number = '002')
```

#### 2.2 (A OR B) AND (C OR D)

```java
QFilter A = new QFilter("f1", QCP.equals, 1);
QFilter B = new QFilter("f1", QCP.equals, 2);
QFilter C = new QFilter("f2", QCP.equals, 3);
QFilter D = new QFilter("f2", QCP.equals, 4);

QFilter filter = QFilter.and(
    QFilter.or(A, B),
    QFilter.or(C, D)
);
// SQL: (f1 = 1 OR f1 = 2) AND (f2 = 3 OR f2 = 4)
```

#### 2.3 复杂嵌套：(A AND B) OR (C AND D)

```java
QFilter filter = QFilter.or(
    QFilter.and(
        new QFilter("a", QCP.equals, 1),
        new QFilter("b", QCP.equals, 2)
    ),
    QFilter.and(
        new QFilter("c", QCP.equals, 3),
        new QFilter("d", QCP.equals, 4)
    )
);
// SQL: (a = 1 AND b = 2) OR (c = 3 AND d = 4)
```

### 三、动态拼装

#### 3.1 动态 OR 条件

```java
List<QFilter> orList = new ArrayList<>();
orList.add(new QFilter("number", QCP.equals, "001"));
orList.add(new QFilter("number", QCP.equals, "002"));
orList.add(new QFilter("number", QCP.equals, "003"));

// 将 List 转为 QFilter 数组传入 or()
QFilter orGroup = QFilter.or(orList.toArray(new QFilter[0]));

// 与其他条件组合
QFilter finalFilter = QFilter.and(
    new QFilter("name", QCP.like, "%A%"),
    orGroup
);
```

#### 3.2 条件动态构建

```java
/**
 * 根据查询参数动态构建 QFilter
 */
public QFilter[] buildFilters(Map<String, Object> queryParams) {
    List<QFilter> filters = new ArrayList<>();

    // 日期范围
    if (queryParams.containsKey("startDate")) {
        filters.add(new QFilter("bizdate", QCP.large_equals, queryParams.get("startDate")));
    }
    if (queryParams.containsKey("endDate")) {
        filters.add(new QFilter("bizdate", QCP.less_equals, queryParams.get("endDate")));
    }

    // 状态筛选（多选）
    if (queryParams.containsKey("statusList")) {
        Object[] statusArr = ((List<?>) queryParams.get("statusList")).toArray();
        filters.add(new QFilter("billstatus", QCP.in, statusArr));
    }

    // 关键字搜索（模糊匹配多个字段）
    if (queryParams.containsKey("keyword")) {
        String keyword = "%" + queryParams.get("keyword") + "%";
        QFilter keywordFilter = QFilter.or(
            new QFilter("billno", QCP.like, keyword),
            new QFilter("name", QCP.like, keyword),
            new QFilter("description", QCP.like, keyword)
        );
        filters.add(keywordFilter);
    }

    return filters.toArray(new QFilter[0]);
}
```

### 四、常用查询模式

#### 4.1 配合 QueryServiceHelper 查询

```java
// 查询指定字段
String entityName = "your_entity";
String selectFields = "id,billno,name,amount,billstatus";
QFilter[] filters = new QFilter[]{
    new QFilter("billstatus", QCP.equals, "C"),
    new QFilter("org.id", QCP.equals, orgId)
};

// 普通查询
DynamicObjectCollection result = QueryServiceHelper.query(
    entityName, selectFields, filters, "createtime desc"
);

// 查询单条
DynamicObject one = QueryServiceHelper.queryOne(
    entityName, selectFields, filters
);

// 流式查询（大数据量推荐）
DataSet dataSet = QueryServiceHelper.queryDataSet(
    "myQuery", entityName, selectFields, filters, "createtime desc"
);

// 判断是否存在
boolean exists = QueryServiceHelper.exists(entityName, filters);

// 查询数量
int count = QueryServiceHelper.queryCount(entityName, filters);
```

#### 4.2 配合 BusinessDataServiceHelper 加载

```java
// 加载完整的单据数据（可保存）
DynamicObject bill = BusinessDataServiceHelper.loadSingle(
    entityName, new QFilter[]{new QFilter("billno", QCP.equals, "BILL-001")}
);

// 批量加载
DynamicObject[] bills = BusinessDataServiceHelper.load(
    entityName, "id,billno,name", filters
);
```

#### 4.3 引用对象字段查询（多层级）

```java
// 查询关联对象的字段（用 . 连接）
// 如查询组织名称含"研发"的单据
QFilter filter = new QFilter("org.name", QCP.like, "%研发%");

// 两层引用
QFilter filter2 = new QFilter("org.parent.name", QCP.equals, "总公司");

// 分录字段查询
QFilter entryFilter = new QFilter("entryentity.material.number", QCP.equals, "M001");
```

> **注意**：访问字段应避免4层及以上，层数过多容易产生笛卡尔积，导致性能骤降

#### 4.4 列表过滤方案转 QFilter

```java
import kd.bos.entity.filter.FilterScheme;
import kd.bos.servicehelper.filter.FilterServiceHelper;

// 获取指定单据的默认过滤方案
FilterScheme defaultScheme = FilterServiceHelper.getDefaultScheme("your_entity");

// 根据过滤方案转换为 QFilter
QFilter qFilter = FilterServiceHelper.getQFilterByFilterScheme(
    defaultScheme, "your_entity", null
);

// 获取嵌套过滤条件
List<QFilter.QFilterNest> nests = qFilter.getNests(true);
for (QFilter.QFilterNest nest : nests) {
    QFilter filter = nest.getFilter();
    // 处理每个过滤条件
}

// 获取所有过滤方案
List<FilterScheme> schemeList = FilterServiceHelper.getSchemeList("your_entity");
```

### 五、封装推荐

```java
/**
 * QFilter 工具类
 * 简化复杂条件构造
 */
public class Filters {

    public static QFilter and(QFilter... fs) {
        return QFilter.and(fs);
    }

    public static QFilter or(QFilter... fs) {
        return QFilter.or(fs);
    }

    public static QFilter eq(String field, Object value) {
        return new QFilter(field, QCP.equals, value);
    }

    public static QFilter neq(String field, Object value) {
        return new QFilter(field, QCP.not_equals, value);
    }

    public static QFilter like(String field, String value) {
        return new QFilter(field, QCP.like, "%" + value + "%");
    }

    public static QFilter in(String field, Object... values) {
        return new QFilter(field, QCP.in, values);
    }

    public static QFilter gt(String field, Object value) {
        return new QFilter(field, QCP.large_than, value);
    }

    public static QFilter gte(String field, Object value) {
        return new QFilter(field, QCP.large_equals, value);
    }

    public static QFilter lt(String field, Object value) {
        return new QFilter(field, QCP.less_than, value);
    }

    public static QFilter lte(String field, Object value) {
        return new QFilter(field, QCP.less_equals, value);
    }

    public static QFilter isNull(String field) {
        return new QFilter(field, QCP.is_null, null);
    }

    public static QFilter notNull(String field) {
        return new QFilter(field, QCP.is_not_null, null);
    }
}

// 使用示例
QFilter filter = Filters.and(
    Filters.eq("billstatus", "C"),
    Filters.or(
        Filters.like("billno", "2026"),
        Filters.like("name", "测试")
    ),
    Filters.gte("amount", new BigDecimal("1000"))
);
```

## 注意事项

### 常见陷阱

1. **数组默认 AND**：`QFilter[]` 数组中的条件默认以 AND 连接，不会自动加括号
2. **无法混用 AND/OR 不分组**：`QFilter.and(A, B, C, D)` 无法表达 `(A AND B) OR (C AND D)`，必须使用嵌套
3. **性能警告**：避免4层及以上的引用字段访问（如 `a.b.c.d.name`），容易产生笛卡尔积
4. **大数据查询**：必须添加过滤条件，禁止无条件全表查询
5. **查询方法选择**：
   - 大数据表查询用 `QueryServiceHelper.queryDataSet`
   - 不查大量数据用 `QueryServiceHelper.query`
   - 需要保存回数据库时才用 `BusinessDataServiceHelper.load`
   - 判断是否存在时用 `QueryServiceHelper.exists`，不要用 `queryOne` 再判空
6. **IN 查询限制**：IN 列表不宜过大，超过一定数量应考虑分批查询或子查询

## 相关链接
- [苍穹 QFilter 如何加括号](https://vip.kingdee.com/article/829723040165553920)
- [列表过滤方案转 QFilter](https://vip.kingdee.com/article/269488809916386048)
- [列表插件过滤数据踩坑](https://vip.kingdee.com/article/215919955156451072)
- [通用报表快速过滤](https://vip.kingdee.com/article/226348071360198656)
- [QueryServiceHelper 使用规范](https://vip.kingdee.com/knowledge/498888207505798912)
