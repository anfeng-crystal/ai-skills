# 报表核心心智模型

以下平台类与调用链用于解释报表结构；生成或修改代码前按 `../SKILL.md` 核对目标版本与本次具体 API，不用未标版本的概览替代目标依赖证据。

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
- `Row` 是行访问器，不能把迭代所得的 `Row` 引用缓存成结果列表；需要保留时复制本次所需字段值。`count`、`cache` 等 Action 会消费并关闭相应 DataSet，返回给报表引擎的结果不能提前消费；分清输入、派生结果与最终返回值的资源所有权。
- AlgoKey 必须唯一:同插件多查询用 `this.getClass().getName() + "_suffix"` 区分。
- 表达式里 NULL 比较用 `IS NULL`,禁 `= null`。

本节 `Row`/Action 语义来自 [Algo简介](https://dev.kingdee.com/open/detail/sdk/2377816588901431296)（Cosmic V8.0.1，更新于 2026-06-16，2026-09-26 已读正文）。该页区分单 Java 进程 Algo 与分布式 AlgoX；不要据支持 MapReduce 就把 Algo 当成分布式执行。目标版本仍按入口核验，此页不替代逐个重载和报表引擎资源交接的目标合同。
