# DataSet-高级取数与组合计算

> 来源: `file:/Users/anfeng/utils/cosmic/home/mservice-cosmic/lib/bos/bos-algo-7.0.jar`（本地签名）
> 来源: `file:/Users/anfeng/utils/cosmic/home/static-file-service/devdoc/corelib/algo/README.md`（本地苍穹开发文档）
> 来源: `https://developer.kingdee.com/developer?productLineId=29`
> 日期: 2026-04-13
> 标签: DataSet, 报表开发, 高级聚合, join, 分组, map, reduce, 缓存

## 摘要

本篇聚焦“可落地到报表插件”的高级取数方案：从基础查询到多层聚合、跨表关联、分桶、窗口替代、排序分页、缓存与自定义函数的完整链路。所有方法均依据本地 `javap` 签名与项目报表插件实践整理。

## 适用版本

- `bos-algo-7.0` 及其所在运行时平台
- 与现有 `ztjg-*` 报表插件风格一致

## 核心概念

- **先筛选后聚合**：`where/filter -> groupBy -> finish/select`
- **先聚合后关联**：减少内存占用和行数膨胀
- **按用途做索引化分桶**：`splitByFilter/splitByGroup` 替代多段循环查询
- **按场景选 join 方式**：`join` 与 `hashJoin` 按数据规模和稳定性取舍
- **可观察性优先**：`setId/setIterateTimeout/addListener` 支持调优与排障

## 详细内容

### 1. 多口径并行汇总（union + 分支聚合）

适用于将同一类型多个单据源（年度/季度/月度）统一口径后统一展示。

```java
DataSet unioned = invoiceDataSet.union(creditNoteDataSet, adjustDataSet);
DataSet aggregated = unioned
    .groupBy(new String[]{"projectId", "orgId"})
    .sum("taxAmount", "taxAmountSum")
    .sum("excludeTaxAmount", "netAmountSum")
    .count("billId", "docCnt")
    .finish();
```

### 2. 条件过滤：字符串表达式 + 参数映射

```java
Map<String, Object> p = new HashMap<>();
p.put("start", java.sql.Date.valueOf("2026-01-01"));
p.put("end", java.sql.Date.valueOf("2026-03-31"));
DataSet period = planDataSet.where("planDate >= :start and planDate <= :end", p);
```

### 3. 字段标准化：addField/addFields/updateField

```java
DataSet norm = source
    .addField("ztjg_year", "year(planDate)")
    .addField("ztjg_month", "month(planDate)")
    .updateFields(new String[]{"status"}, new String[]{"CASE WHEN status=1 THEN '正常' ELSE '异常' END"});
```

### 4. 缺省字段增强：addNullField/addBalanceField

```java
DataSet fillNull = source
    .addNullField("riskScore")
    .addBalanceField("planAmount", "planBalance")
    .addBalanceField("actualAmount", "actualBalance");
```

### 5. 精准筛选与自定义过滤器

```java
DataSet filtered = source.where("orgId is not null and state in ('执行中','整改中')");
DataSet fnFilter = filtered.filter(new FilterFunction() {
    @Override public boolean test(Row row) {
        BigDecimal remain = row.getBigDecimal("remainAmount");
        return remain != null && remain.compareTo(BigDecimal.ZERO) > 0;
    }
});
```

### 6. 多表穿透：join + select + hint

```java
JoinHint hint = new JoinHint();
hint.setUseMerge(true);
DataSet enriched = projectData
    .leftJoin(deptData)
    .hint(hint)
    .on("deptId", "deptId")
    .select(new String[]{"projectId", "amount", "status"}, new String[]{"deptName"})
    .finish();
```

### 7. 全量节点关联：rightJoin/fullJoin/cross

```java
DataSet right = dimProject.join(factProject, JoinType.RIGHT, new JoinHint()).on("projectId", "projectId").finish();
DataSet full = factProject.fullJoin(dimProject).on("projectId", "projectId").finish();
DataSet cross = factProject.join(dimProject, JoinType.CROSS).finish(); // 小规模交叉场景
```

### 8. Hash Join 加速大字典补齐

```java
HashTable deptHash = deptBase.toHashTable("deptId");
DataSet result = planData
    .hashJoin(deptHash, "deptId", new String[]{"deptName", "leaderName"})
    .addHashTable(deptHash, "deptId", new String[]{"orgLevel"})
    .hint(new JoinHint())
    .finish();
```

### 9. 分组聚合全集（sum/avg/max/min/maxP/minP/countDistinct/groupConcat）

```java
DataSet grouped = factData.groupBy(new String[]{"projectId", "orgId"})
    .sum("planAmount", "planSum")
    .avg("riskDelayDays", "riskAvg")
    .max("planDate", "latestPlan")
    .min("planDate", "earliestPlan")
    .maxP("updateTime", "latestDataId", "latestDataId")
    .minP("updateTime", "latestDataId", "earliestDataId")
    .countDistinct(new String[]{"responsibleUser"}, "respDistinctCnt")
    .groupConcat("issueDetail", "issueList", " | ")
    .finish();
```

### 10. 取样与去重：top/topBy/range/limit/distinct

```java
DataSet topDelay = source.orderBy(new String[]{"riskScore desc"}).top(200);
DataSet topByMonth = source.topBy(20, new String[]{"orgId", "riskScore desc"});
DataSet slice = source.orderBy(new String[]{"planDate asc"}).range(0, 50); // 第1页
DataSet safePage = source.orderBy(new String[]{"planDate asc"}).limit(50, 2); // 兼容 limit 行为
DataSet dedup = source.distinct();
```

### 11. 自定义 map 计算

```java
DataSet derived = source.map(new MapFunction() {
    @Override
    public Object[] map(Row row) {
        BigDecimal plan = row.getBigDecimal("planAmount");
        BigDecimal actual = row.getBigDecimal("actualAmount");
        BigDecimal gap = (plan == null ? BigDecimal.ZERO : plan)
                .subtract(actual == null ? BigDecimal.ZERO : actual);
        return new Object[]{row.get("projectId"), gap};
    }
});
```

### 12. 分组 reduce 自定义累计（含 Collector）

```java
DataSet reduced = source.groupBy(new String[]{"projectId"}).reduceGroup(
    new ReduceGroupFunctionWithCollector() {
        @Override
        public void reduce(Iterator<Row> rows, Collector collector) {
            BigDecimal sum = BigDecimal.ZERO;
            String proj = null;
            while (rows.hasNext()) {
                Row r = rows.next();
                proj = (String) r.getString("projectId");
                BigDecimal v = r.getBigDecimal("riskLoss");
                if (v != null) sum = sum.add(v);
            }
            collector.collect(new Object[]{proj, sum});
        }
    }
).select("projectId", "riskLossTotal");
```

### 13. splitByGroup / splitByFilter 的并行分桶模式

```java
DataSet[] groups = source.splitByGroup(new String[]{"orgId", "projectType"});
DataSet[] statusBuckets = source.splitByFilter(
    new String[]{"riskScore >= 80", "riskScore between 50 and 79", "riskScore < 50"},
    true
);
```

### 14. 取首条/区间统计：copy + addFields 保护源数据

```java
DataSet src = source.copy().addField("isLatest", "1");
DataSet base = src.where("isLatest = 1");
```

### 15. count 与 exists 场景

```java
int warningCount = source.where("riskScore > 80").count("riskId", false);
```

### 16. executeSql 与 SqlHint（仅在平台可执行场景）

```java
SqlHint sqlHint = SqlHint.DEFAULT;
DataSet dbSet = source.executeSql("select projectid, sum(amount) total from xxx where tenantid = ?", sqlHint);
```

### 17. 缓存策略（cache / cacheBuilder）

```java
CacheHint hint = new CacheHint();
hint.setCacheId("project_report_cache_v1");
hint.setTimeout(15, TimeUnit.MINUTES);
CachedDataSet cached = source.cache(hint);
DataSet fromCache = cached.toDataSet(Algo.create("cache-reader"), true);

CachedDataSet.Builder cb = source.cacheBuilder(hint);
DataSet cacheReplay = cb.build().toDataSet(Algo.create("cache-reader"), true);
```

### 18. 监听与调度

```java
source.setId("report_output_trace");
source.addListener(new DataSet.Listener() {
    @Override
    public void beforeClosed() {
        // 记录查询起始信息
    }

    @Override
    public void afterClosed() {
        // 记录返回行数、耗时、内存趋势
    }
});
DataSet traced = source;
```

### 19. 关联字段对齐工具

```java
DataSet cleaned = source.removeFields("tmpField1", "tmpField2");
```

## 注意事项

- `cross` join 仅用于小表或必须的笛卡尔场景，避免膨胀。
- `hashJoin` 对 key 类型要求严格，建议预先 `select` 统一类型。
- `executeSql` 的 SQL 方言依赖数据库与平台版本，不要在基础示例里强耦合数据库函数。
- `cache` 要配 `allowMaxRows` 与异常回退策略，避免热数据无限制堆积。
- `splitByFilter` 的 includeOthers 为 `true` 时会补充“未命中桶”，便于审计；`false` 用于纯闭合桶模型。
- `top` 和 `limit` 在某些数据源排序不确定时需先显式 `orderBy`，否则分页结果易抖动。

## 编译与校验记录

- 验证时间：2026-04-13
- 执行环境：本地 `ztjg` 工程，Java 8 编译目标，依赖 `bos-algo-7.0.jar`
- 完整可编译示例：`ztjg.cosmic.debug.algo.knowledge.sample.*`
- 执行命令：

```bash
javac -source 8 -target 8 -encoding UTF-8 -cp /Users/anfeng/utils/cosmic/home/mservice-cosmic/lib/bos/bos-algo-7.0.jar -d /tmp/dataset-advanced-lab/classes code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/fixture/AlgoKnowledgeFixture.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/CustomFunctions.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/DataSetApiSamples.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/GroupByApiSamples.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/JoinApiSamples.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/HashJoinApiSamples.java
./gradlew --no-parallel :ztjg-cosmic-debug:compileJava --console=plain -Dorg.gradle.jvmargs=-Xmx4g
```

- 输出摘要：新增示例类与目标模块编译通过。
- 退出码：0

## 相关链接

- `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/DataSetApiSamples.java`
- `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/GroupByApiSamples.java`
- `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/JoinApiSamples.java`
- `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/HashJoinApiSamples.java`
- `/Users/anfeng/utils/cosmic/home/static-file-service/devdoc/corelib/algo/README.md`
- `/Users/anfeng/Code/Work/ztjg/code/sqm/ztjg-sqm-safequality/src/main/java/ztjg/sqm/safequality/plugin/report/CancheckRPTQueryPlugin.java`
- `/Users/anfeng/Code/Work/ztjg/code/sqm/ztjg-sqm-safequality/src/main/java/ztjg/sqm/safequality/plugin/report/CraneQueryRPTPlugin.java`
- `/Users/anfeng/Code/Work/ztjg/code/promise/ztjg-promise-appointment/src/main/java/ztjg/promise/appointment/plugin/report/RailMajorSecureNewRPTPlugin.java`
- `/Users/anfeng/Code/Work/ztjg/code/sqm/ztjg-sqm-safequality/src/main/java/ztjg/sqm/safequality/plugin/report/RiskScoreRPTQueryPlugin.java`
- `file:/tmp/dataset-advanced-lab/evidence/dataset-api-signatures.txt`
