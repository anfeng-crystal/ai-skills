# 内存计算框架（DataSet / Algo）

## 入口与版本

用于过滤、排序、聚合、关联和流式结果消费；报表完整取数合同与精确 API 路由到 [kingdee-report](../../../../kingdee-report/SKILL.md)，简单 ORM 取数见 [sdk-orm-access.md](sdk-orm-access.md)。Algo 是进程内计算引擎，不能代替所有 `DynamicObject` 业务操作，也不能保证任意数据规模都不会 OOM。

以下方法以实际 `bos-algo-7.0.jar` 与官方 V7.0.1 Javadoc 互核。社区入门/接口正文提供用法合同，不据文章更新时间推 SDK 版本。类均位于 `kd.bos.algo`。

|能力|真实入口与结果|
|---|---|
|选择/派生/过滤|`select(String)`、`addField(String,String)`、`where(String)` 返回 `DataSet`。|
|排序/合并|`orderBy(String[])`、`union(DataSet)` 返回 `DataSet`；排序元素如 `total desc`，不是单个逗号串重载。|
|分组|`groupBy(String[])` 返回 `GroupbyDataSet`；接 `sum(String,String)` 等聚合，最后 `finish()` 返回 `DataSet`。|
|普通关联|`join` / `leftJoin` 返回 `JoinDataSet`，配置关联与输出后 `finish()`。|
|哈希关联|`toHashTable(String)` 返回 `HashTable`；`hashJoin(HashTable,String,String[])` 及带末尾 `boolean` 的重载返回 `HashJoinDataSet`。|
|非空值计数|`count(String field, boolean distinct): int`，统计字段非 null 值并消费/关闭数据集；不是总行数的无参 `count()`。|
|重复消费|需要复用时，在消费前保留 `copy()` 得到的独立数据集；复制有资源成本。|

实际 7.0 `DataSet` 无 `toCollection()`；需要 Java 结果列表时逐行提取稳定值。需要 `DynamicObjectCollection` 时按已确认实体模型逐项映射，或在业务允许时选 ORM 对象查询，不能假设存在自动转换 API。缓存合同见 [DataSet 缓存](../../adv/query-dataset.md)，不将 `cache` 等同于固定 Redis 存储。

## HashJoin 的必要条件

右侧 `HashTable` 使用唯一单字段键，适合能放入内存的小维表；明细的 `order_id` 通常重复，不能不校验就拿来作键。数据量、重复键和 null 语义按实际输入核验，不把“小于固定行数”当内存安全保证。

`hashJoin` 返回构造器，实际 7.0 必须调用 `selectLeftFields(String[])` 指定左列，再 `finish()`。仅补 `finish()` 虽可编译，缺左列仍会在运行时抛错。末尾 `includeNotExist=true` 保留左侧未匹配行，右侧输出为 null；默认效果类似内连接。输出同名时在构造器选择列并显式别名，不假设任意数据集名都能作 SQL 表别名。

## 可编译示例

字段均是示例输入结构，使用时换成已确认字段。下列方法接管并消费输入，调用后不再复用这些实例。HashTable 为本方法从默认 `toHashTable` 创建的专属表，不接管他人共享表。每段派生结果分别绑定资源，回调抛异常或提前退出也会关闭已创建的 DataSet。

```java
import kd.bos.algo.DataSet;
import kd.bos.algo.HashTable;
import kd.bos.algo.Row;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.function.BiConsumer;

public final class AlgoExamples {
    private AlgoExamples() { }

    // 输入含 id/qty/price；本方法接管并消费 source。
    public static void consumeTotals(DataSet source,
            BiConsumer<Long, BigDecimal> consumer) {
        try (DataSet owned = source;
             DataSet amount = owned.addField("qty * price", "amount");
             DataSet filtered = amount.where("amount > 1000");
             DataSet totals = filtered.groupBy(new String[]{"id"})
                     .sum("amount", "total").finish();
             DataSet result = totals.orderBy(new String[]{"total desc", "id asc"})) {
            while (result.hasNext()) {
                Row row = result.next();
                consumer.accept(row.getLong("id"), row.getBigDecimal("total"));
            }
        }
    }

    // products 的 product_id 唯一，含 product_name；sales 含 product_id。
    // 本方法接管两个输入；回调只收到标量值，不保留 Row。
    public static void consumeProductNames(DataSet sales, DataSet products,
            java.util.function.Consumer<String> consumer) {
        try (DataSet ownedSales = sales; DataSet ownedProducts = products) {
            HashTable productTable = ownedProducts.toHashTable("product_id");
            try {
                try (DataSet joined = ownedSales.hashJoin(productTable, "product_id",
                        new String[]{"product_name"}, true)
                        .selectLeftFields(new String[]{"product_id"}).finish()) {
                    while (joined.hasNext()) {
                        consumer.accept(joined.next().getString("product_name"));
                    }
                }
            } finally {
                productTable.close();
            }
        }
    }

    // 只计 field 非 null 的值；distinct 控制去重。
    public static int countValues(DataSet source, String field, boolean distinct) {
        try (DataSet owned = source) {
            return owned.count(field, distinct);
        }
    }

    // 逐行计数，包含业务字段为空的行。
    public static long countRows(DataSet source) {
        long count = 0L;
        try (DataSet owned = source) {
            while (owned.hasNext()) {
                owned.next();
                count++;
            }
        }
        return count;
    }

    // 有上限的标量收集，保留 null 和重复 ID，不保存 Row 游标。
    public static List<Long> collectIds(DataSet source, int maxRows) {
        try (DataSet owned = source) {
            if (maxRows <= 0) {
                throw new IllegalArgumentException("maxRows must be positive");
            }
            List<Long> ids = new ArrayList<Long>();
            while (owned.hasNext()) {
                if (ids.size() == maxRows) {
                    throw new IllegalStateException("row limit exceeded");
                }
                ids.add(owned.next().getLong("id"));
            }
            return ids;
        }
    }
}
```

`countRows` 与 `countValues` 的 null/去重语义不同；若计数后还要读数据，先按复用合同复制，不能在已消费的同一实例上继续遍历。`collectIds` 超限会抛异常，避免悄悄截断；更大规模使用逐行消费者，需物化其他结果时复制对应标量或 DTO，不能把 `Row` 游标保存到 List。

## 资源与使用边界

- 完整迭代结束会自动关闭；异常、提前退出仍需显式关闭。方法返回 DataSet 给上层时应移交资源责任，不能在返回前关闭结果或它依赖的作用域。
- `HashTable` 有 `close()`，但不实现 `AutoCloseable`，不能直接作为 try 资源声明。本机 7.0 的默认 `SmartHashTable` 路径可重复关闭，且 joined 关闭会关闭关联表；示例额外 finally 覆盖构建失败。此为已核默认实现行为，不保证自定义 HashTable 幂等或允许共享表随意复用。
- `Algo.newContext()` 可收口在其资源环境内创建的数据集；对外部传入的 DataSet，不能在方法内临时新建 Context 就假定所有派生结果迁入新环境。跨线程移交也不能仅凭可传对象就认为资源安全；先核目标线程/资源合同。
- 能过滤时及早过滤、按列裁剪；普通 Join 的左右选择按算法与真实数据规模评估，不把右表一定物化或“大表驱动小表”写成所有 Join 的保证。
- `QFilter.toString()` 不是 Algo 表达式转换合同；ORM 的特殊运算符不一定被 Algo 支持。

## 依据

- [Algo 入门篇](https://vip.kingdee.com/knowledge/354624329809788160)，更新 2026-07-30：转换/消费、迭代关闭、QFilter 边界。
- [Algo 接口说明](https://vip.kingdee.com/knowledge/272106534551799808)，更新 2026-07-29；当前分类为金蝶 AI 套件，正文写 bos-algo-1.0，HashJoin/排序/计数合同与本次 7.0 依赖互核后使用。
- [DataSet](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/algo/DataSet.html)、[HashJoinDataSet](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/algo/HashJoinDataSet.html)、[HashTable](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/algo/HashTable.html) · 官方 V7.0.1 Javadoc。

最终示例用实际 7.0/JDK 8 最小依赖离线编译；尚未执行平台数据、关联结果或内存压力测试。
