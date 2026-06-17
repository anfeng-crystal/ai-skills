# 报表核心心智模型

## 1. 单一入口生命周期
报表取数插件只有一个核心方法 `query(ReportQueryParam, Object) → DataSet`,所有逻辑挂在此。执行链:
解析 `FilterInfo` → 构建 `QFilter[]` → 查询多个 DataSet → JOIN/UNION → `groupBy().sum().finish()` → `addField()` 计算列 → 返回最终 DataSet。

## 2. 三层数据访问(报表只读)
| 层级 | Helper | 用途 |
|---|---|---|
| 只读主力 | `QueryServiceHelper.queryDataSet()` | 返回 DataSet,支持 Algo 链式;约 90% 查询 |
| 只读小型 | `QueryServiceHelper.query()` | 返回 `DynamicObjectCollection`,辅助查找(期间/组织) |
| 缓存 | `BusinessDataServiceHelper.loadSingleFromCache()` | 只读基础资料缓存 |

铁律:报表禁用 `SaveServiceHelper` / `OperationServiceHelper`,不写库。

## 3. 无状态设计
实例字段会导致多用户并发串数据。所有数据用局部变量 + 方法参数传递;唯一例外 `private static final` 常量。

```java
// ❌ private Object lastOrgId; private Map<String,DataSet> cache;
// ✓ Object orgId = parseOrgId(param.getFilter()); DataSet ds = getMainDs(orgId, periodId);
```

## 4. BigDecimal 财务计算
- 禁 `double`/`float` 运算。
- 运算 `.add()/.subtract()/.multiply()/.divide(scale, RoundingMode)`。
- 比较永远用 `.compareTo()`,禁 `==` / `.equals()`。
- 空值统一辅助方法返回 `BigDecimal.ZERO`。

## 5. DataSet 单次消费
- DataSet 单次消费:遍历后即被消费。需遍历后再复用时先 `.copy()`(遍历副本,原 DataSet 仍可返回)。
- AlgoKey 必须唯一:同插件多查询用 `this.getClass().getName() + "_suffix"` 区分。
- 表达式里 NULL 比较用 `IS NULL`,禁 `= null`。
