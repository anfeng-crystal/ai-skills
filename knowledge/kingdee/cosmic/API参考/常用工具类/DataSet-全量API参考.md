# DataSet-全量API参考

> 来源: `file:/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug`（项目报表实现参考）
> 来源: `file:/Users/anfeng/utils/cosmic/home/mservice-cosmic/lib/bos/bos-algo-7.0.jar`（`javap` 签名）
> 来源: `file:/Users/anfeng/utils/cosmic/home/static-file-service/devdoc/corelib/algo/README.md`（本地苍穹开发文档）
> 来源: `https://developer.kingdee.com/developer?productLineId=29`
> 日期: 2026-04-13
> 标签: DataSet, kd.bos.algo, 数据报表, 分组聚合, 关联查询, 分页, 缓存

## 摘要

本文按 `bos-algo-7.0.jar` 的实际签名构建 DataSet 全量 API 参考，覆盖 `DataSet/GroupbyDataSet/JoinDataSet/HashJoinDataSet` 及核心辅助类型（`RowMeta/Field/DataType/FilterFunction/MapFunction/ReduceGroupFunction/CustomAggFunction`）。并结合项目中 `ztjg-cosmic-debug` 与多模块报表插件的可执行模式，给出报表场景下的链路组合与边界建议，支持建设行业、财务、HR 报表的复杂组合计算。

## 适用版本

- `bos-algo-7.0.jar` 本地签名文件（当前项目依赖）
- 示例报表以 `ztjg-*` 各模块内现有 Java 报表插件风格为准
- 适用于金蝶云苍穹平台报表取数开发（本地 JAR 级签名为准）

## 核心概念

- **DataSet**：链式执行模型，支持筛选、投影、分组、排序、关联、分页等。
- **GroupbyDataSet**：在分组窗口内进行聚合，最终通过 `finish()` 回到 DataSet。
- **JoinDataSet/HashJoinDataSet**：`join` 与 `hashJoin` 两类关联策略，前者面向一般关系集成，后者面向大表探测与左侧主控。
- **RowMeta/Field**：定义字段元数据与类型体系，是内存构造 DataSet 的基础。
- **函数类（FilterFunction/MapFunction/ReduceGroupFunction）**：用于高级条件、列衍生、分组压缩逻辑。
- **缓存与执行提示**：`CacheHint/SqlHint/JoinHint` 用于高负载场景性能控制。

## 详细内容

### A. DataSet 全量方法

以下为 `javap` 在 `bos-algo-7.0.jar` 中确认的 `kd.bos.algo.DataSet` 方法：

#### 元信息与迭代
- `getRowMeta()`
- `iterator()` / `hasNext()` / `next()` / `isEmpty()`
- `close()`

#### 投影与字段扩展
- `select(String...)`
- `select(boolean, String...)`
- `select(String)`
- `addField(String, String)`
- `addFields(String[], String[])`
- `updateField(String, String)`（默认方法）
- `updateFields(String[], String[])`
- `addNullField(String...)`
- `addNullField(String)`
- `addBalanceField(String, String)`
- `removeFields(String...)`

#### 筛选
- `filter(String)`
- `filter(String, Map<String, Object>)`
- `filter(FilterFunction)`
- `where(String)`（默认，等价于 filter(String)）
- `where(String, Map<String, Object>)`（默认，等价于 filter(String, Map)）
- `where(FilterFunction)`（默认）

#### 排序与分组
- `orderBy(String[])`
- `groupBy()`
- `groupBy(String[])`
- `groupBy(String[], boolean[])`
- `splitByGroup(String[])`
- `splitByFilter(String[], boolean)`

#### 关联
- `toHashTable(String)`
- `hashJoin(HashTable, String, String[])`
- `hashJoin(HashTable, String, String[], boolean)`
- `join(DataSet)`
- `join(DataSet, JoinHint)`
- `join(DataSet, JoinType)`
- `join(DataSet, JoinType, JoinHint)`
- `leftJoin(DataSet)` / `leftJoin(DataSet, JoinHint)`（默认）
- `rightJoin(DataSet)` / `rightJoin(DataSet, JoinHint)`（默认）
- `fullJoin(DataSet)` / `fullJoin(DataSet, JoinHint)`（默认）

#### 集合与分页
- `union(DataSet)`
- `union(DataSet...)`
- `top(int)`
- `range(int, int)`
- `limit(int, int)`（默认）
- `topBy(int, String[])`
- `copy()`
- `count(String, boolean)`

#### 输入输出与执行
- `executeSql(String)`
- `executeSql(String, SqlHint)`
- `cache(CacheHint)`
- `cacheBuilder(CacheHint)`
- `print(boolean)`
- `addListener(DataSet.Listener)`
- `setId(String)`
- `setIterateTimeout(int)`（默认）

#### 映射与自定义聚合
- `map(MapFunction)`
- `reduceGroup(ReduceGroupFunction)`
- `reduceGroup(ReduceGroupFunctionWithCollector)`
- `distinct()`

#### 其他
- `close()`（见上）

### B. DataSetBuilder 与构建器

- `DataSetBuilder.append(Object[])`
- `DataSetBuilder.append(Row)`
- `DataSetBuilder.build()`

### C. GroupbyDataSet 聚合方法
- `sum(String)` / `sum(String,String)`
- `avg(String)` / `avg(String,String)`
- `max(String)` / `max(String,String)`
- `min(String)` / `min(String,String)`
- `maxP(String,String)` / `maxP(String,String,String)`
- `minP(String,String)` / `minP(String,String,String)`
- `count()`
- `count(String)`
- `countDistinct(String[])` / `countDistinct(String[], String)`
- `groupConcat(String)` / `groupConcat(String,String)` / `groupConcat(String,String,String)`
- `agg(CustomAggFunction<?>, String, String)`
- `finish()`
- `reduceGroup(ReduceGroupFunction)` / `reduceGroup(ReduceGroupFunctionWithCollector)`

### D. JoinDataSet/HashJoinDataSet
- `JoinDataSet.on(String, String)`
- `JoinDataSet.select(String[], String[])`
- `JoinDataSet.select(String...)`
- `JoinDataSet.hint(JoinHint)`
- `JoinDataSet.finish()`
- `HashJoinDataSet.addHashTable(HashTable, String, String[])`
- `HashJoinDataSet.addHashTable(HashTable, String, String[], boolean)`
- `HashJoinDataSet.selectLeftFields(String[])`
- `HashJoinDataSet.hint(JoinHint)`
- `HashJoinDataSet.finish()`

### E. 核心类型（签名要点）
- `RowMeta(String[], DataType[])`
- `RowMeta(Field...)`
- `RowMeta.getField(String)` / `getFieldCount()` / `getFieldIndex(String)` / `toMap(Row, Map)` / `fromResultSet(ResultSet)` 等
- `Field(String, DataType)` / `Field(String, String, DataType, boolean)` / `deriveAlias` / `deriveName` / `derive`
- `DataType` 的数值/文本/时间/布尔等常量族与类型读写接口
- `FilterFunction.test(Row)`
- `MapFunction.map(Row)`
- `ReduceGroupFunction.reduce(Iterator<Row>)`
- `ReduceGroupFunctionWithCollector.reduce(Iterator<Row>, Collector)`
- `CustomAggFunction`：`newAggValue/addValue/combineAggValue/getResult`
- `CacheHint`：超时、页大小、缓存ID、行数上限、溢出策略
- `SqlHint`：自定义聚合函数注册容器
- `JoinHint`：`setUseMerge/setUseHHJ/setUseNest/setNullAsZero`
- `JoinType`：`INNER/LEFT/RIGHT/FULL/CROSS`

## 典型报表链路模板（实际项目常见）

#### 1）多维过滤 + 条件聚合 + 维表补齐
`where`/`groupBy`/`sum`/`count`/`leftJoin`/`select` 形成「筛选→汇总→补齐」链路。

#### 2）多源纵向并集 + 明细/汇总统一口径
`union`/`addField`/`select` 对不同单据源做口径统一后并集，便于后续统一分组。

#### 3）节点明细聚合 + 异常文本收敛
`groupBy` + `maxP`/`minP` + `groupConcat` 在同一维度下取最新/最早记录与关联人/问题列表。

#### 4）跨表关联
`join(leftJoin/rightJoin/fullJoin)` 搭配 `on` 与 `select(左字段,右字段)` 落字段治理。

#### 5）大表字典增强
`toHashTable` + `hashJoin` + `addHashTable` 完成“主表主键驱动 + 小字典左补齐”。

## 报表取数建议

- 先用 `select` 收敛字段，再 `groupBy`，避免在宽表上大量聚合字段导致内存激增。
- 大于一层 `union` 的场景统一加 `select` 投影到同一字段别名，降低后续 `select`/`distinct` 复杂度。
- 明确排序字段与空值策略；`orderBy` 中建议显式使用 `... asc/desc`，避免数据库默认顺序变化。
- `splitByFilter` 适合异常分桶（如逾期/预警）与非预警共存展示；`splitByGroup` 适合按组织/项目等维度分支复用同一后续链。
- 缓存优先用于重算成本高且口径固定的中间集，需设置 `CacheHint` 限流参数，避免一次拉爆内存。
- `map` 与 `reduceGroup` 适合“轻量列加工”和“行内状态累加”；复杂规则优先先清洗源数据再映射，避免反复转换。
- 对 SQL 下推能力有限或数据库兼容性差异明显的场景，优先在 DataSet 中实现逻辑，`executeSql` 仅用于平台能力明确且可复用 SQL 的场景。
- `setIterateTimeout` 与 `setId` 在链路追踪与超时控制时可提升排障体验。

## 编译与校验记录

- 验证时间：2026-04-13
- 执行环境：本地 `ztjg` 工程，Java 8 编译目标，依赖 `bos-algo-7.0.jar`
- 签名证据：`file:/tmp/dataset-advanced-lab/evidence/dataset-api-signatures.txt`
- 完整可编译示例：
  - `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/fixture/AlgoKnowledgeFixture.java`
  - `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/DataSetApiSamples.java`
  - `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/GroupByApiSamples.java`
  - `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/JoinApiSamples.java`
  - `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/HashJoinApiSamples.java`
  - `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/CustomFunctions.java`
- 执行命令：

```bash
javac -source 8 -target 8 -encoding UTF-8 -cp /Users/anfeng/utils/cosmic/home/mservice-cosmic/lib/bos/bos-algo-7.0.jar -d /tmp/dataset-advanced-lab/classes code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/fixture/AlgoKnowledgeFixture.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/CustomFunctions.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/DataSetApiSamples.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/GroupByApiSamples.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/JoinApiSamples.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/HashJoinApiSamples.java
./gradlew --no-parallel :ztjg-cosmic-debug:compileJava --console=plain -Dorg.gradle.jvmargs=-Xmx4g
```

- 输出摘要：两条命令均编译通过；Gradle 首次默认并行编译曾因上游依赖模块堆内存不足失败，调整为 `--no-parallel` 与 `-Xmx4g` 后模块编译通过。
- 退出码：0

## 注意事项

- 先做字段映射，再计算 KPI；避免在 `groupBy` 前混入字符串拼接表达式导致类型漂移。
- `union` 后如需总计行，优先 `groupBy().count().sum()` 方式重算，不建议先 `union` 后直接手工加总列值。
- 使用 `count("alias")` 与 `countDistinct` 时明确分母口径，避免重复行导致的计数虚高。
- `hashJoin` 对源侧字段类型敏感，`toHashTable(keyField)` 的 key 必须与 `addHashTable` 键同类型同语义。
- `join`/`leftJoin` 与 `hashJoin` 混用时需验证重复主键语义，防止“放大/收缩”异常。
- `close()` 与平台缓存关闭分离：`CachedDataSet.close()`、`DataSet` 自动生命周期建议由查询容器控制，手工关闭在插件末尾统一收口。

## 相关链接

- `https://developer.kingdee.com/developer?productLineId=29`
- `/Users/anfeng/utils/cosmic/home/static-file-service/devdoc/corelib/algo/README.md`
- `/Users/anfeng/Code/Work/ztjg/code/promise/ztjg-promise-appointment/src/main/java/ztjg/promise/appointment/plugin/report/EngineProjectRPTPlugin.java`
- `/Users/anfeng/Code/Work/ztjg/code/promise/ztjg-promise-appointment/src/main/java/ztjg/promise/appointment/plugin/report/LevelNodeWarnRPTPlugin.java`
- `/Users/anfeng/Code/Work/ztjg/code/promise/ztjg-promise-appointment/src/main/java/ztjg/promise/appointment/plugin/report/OutputProRPTPlugin.java`
- `/Users/anfeng/Code/Work/ztjg/code/promise/ztjg-promise-appointment/src/main/java/ztjg/promise/appointment/plugin/report/RailMajorSecureNewRPTPlugin.java`
- `/Users/anfeng/Code/Work/ztjg/code/sqm/ztjg-sqm-safequality/src/main/java/ztjg/sqm/safequality/plugin/report/CancheckRPTQueryPlugin.java`
- `/Users/anfeng/Code/Work/ztjg/code/dswpt/ztjg-dswpt-dsw/src/main/java/ztjg/dswpt/dsw/wzgl/report/LimitMaterialLedgerReportListDataPlugin.java`
- `/Users/anfeng/Code/Work/ztjg/code/sqm/ztjg-sqm-safequality/src/main/java/ztjg/sqm/safequality/plugin/report/RiskScoreRPTQueryPlugin.java`
- `file:/tmp/dataset-advanced-lab/evidence/dataset-api-signatures.txt`
