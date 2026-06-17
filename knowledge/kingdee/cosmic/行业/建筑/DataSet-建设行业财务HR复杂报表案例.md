# DataSet-建设行业财务HR复杂报表案例

> 来源: `file:/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug`（报表样式与调用方式）
> 来源: `file:/Users/anfeng/utils/cosmic/home/mservice-cosmic/lib/bos/bos-algo-7.0.jar`（API 签名）
> 来源: `file:/Users/anfeng/utils/cosmic/home/static-file-service/devdoc/corelib/algo/README.md`（本地苍穹开发文档）
> 来源: `https://developer.kingdee.com/developer?productLineId=29`
> 日期: 2026-04-13
> 标签: 建设行业, 财务报表, HR 报表, DataSet, 风险看板, 分组聚合, 人效

## 摘要

基于本地 `bos-algo-7.0.jar` 签名与项目内报表插件实践，整理面向建设行业、财务、HR 的 18 个复杂需求。每个需求给出：业务目标、数据输入、DataSet API 使用点、输出字段、异常边界、验收标准、业务链路示例片段、报表取数建议，覆盖 DataSet 全量链路中的关键方法。

## 适用版本

- `bos-algo-7.0`（本地签名源）
- 金蝶云苍穹报表开发运行环境（ztjg 项目各模块）
- 建议配合 `Algo.create(唯一键)`、统一字段别名与时间字段归一化

## 核心概念

- 报表取数默认遵循“标准化字段 → 聚合/筛选 → 多源补齐 → 输出收口”。
- 所有示例均以 DataSet 链式 API 为主，`executeSql` 仅说明平台执行期可替代方案。
- 高复杂度需求优先使用 `join/hashJoin + groupConcat + topBy + splitByFilter` 组合，避免单 SQL 的可读性退化。

## 详细内容

### 示例数据构造（复用）

```java
private DataSet buildDemo(String[][] rows, String[] fields, DataType[] types) {
    Algo algo = Algo.create("dataset-demo");
    Field[] f = new Field[fields.length];
    for (int i = 0; i < fields.length; i++) {
        f[i] = new Field(fields[i], types[i]);
    }
    DataSetBuilder b = algo.createDataSetBuilder(new RowMeta(f));
    for (String[] r : rows) {
        b.append(new Object[] { r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7] });
    }
    return b.build();
}
```

> 上述仅示意字段结构，真实项目请使用 `Object[]` 按字段顺序逐行 append。

### 完整可编译示例索引

本篇 18 个需求中的代码块用于说明业务报表链路，变量名代表对应来源 DataSet；完整可编译版本已在以下示例类中覆盖同类 API 组合：

- `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/fixture/AlgoKnowledgeFixture.java`
- `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/DataSetApiSamples.java`
- `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/GroupByApiSamples.java`
- `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/JoinApiSamples.java`
- `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/HashJoinApiSamples.java`
- `/Users/anfeng/Code/Work/ztjg/code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/CustomFunctions.java`

### 复杂需求清单（18项）

### 1. 建设行业 | 多层级产值与合同履约穿透
- **业务目标**：按组织/项目/年度输出计划产值、已产值、回签产值及履约偏差率，支持按合同分层展示。
- **数据输入**：合同主表、计划产值表、履约里程碑表、回签表，含 `projectId/orgId/year`。
- **DataSet API 使用点**：
  - `where`、`groupBy`、`sum`、`count`
  - `join`（`leftJoin`）+`on`+`select`
  - `addField` 计算偏差率
- **输出字段/指标**：`projectId/orgId/year`、`planAmount`、`outputAmount`、`signedAmount`、`remainAmount`、`fulfillRate`。
- **异常边界**：空组织/空合同、计划金额为 0、重复上报导致去重不足。
- **验收标准**：
  - 目标项目总数与原始单据项目总数一致；
  - 同一项目同一年份仅保留一行汇总；
  - 偏差率不出现 NaN/Infinity。
- **业务链路示例片段**：
```java
DataSet r1 = contractDataSet.where("year = :y and status in ('生效','执行中')")
        .where("projectLevel in ('主体','分部')");
DataSet sum1 = r1.groupBy(new String[]{"orgId","projectId","year"})
        .sum("planAmount","planAmount")
        .sum("planOutput","outputAmount")
        .sum("signedAmount","signedAmount")
        .count("contractId","contractCnt")
        .finish()
        .addField("remainAmount", "planAmount - signedAmount")
        .addField("fulfillRate", "round(signedAmount / nullif(planAmount,0) * 100, 2)");
DataSet result = sum1.leftJoin(planMeta)
        .on("projectId","projectId")
        .select(new String[]{"orgId","projectId","year","planAmount","outputAmount","signedAmount","remainAmount","fulfillRate"},
                new String[]{"contractName","projectManager"});
```
- **报表取数建议**：先按合同口径 `year` 去重，再组装主表明细；复杂公式尽量用 `addField`，避免 SQL UDF 不一致。

### 2. 建设行业 | 进度-产值-资源偏差预警
- **业务目标**：按项目输出进度偏差排名，按风险等级输出预警。
- **数据输入**：计划进度、实际完成、资源投入、项目字典。
- **DataSet API 使用点**：
  - `orderBy`、`topBy`
  - `join`（`join(JoinType)`）
  - `groupBy` + `avg` + `sum`
  - `maxP` 取最近更新时间
- **输出字段/指标**：`projectId`、`planProgress`、`realProgress`、`resourceEfficiency`、`delayDays`、`riskLevel`、`latestUpdateId`。
- **异常边界**：进度缺失、资源空值、跨期重复快照。
- **验收标准**：
  - 只返回偏差绝对值≥阈值的项目；
  - 风险项按 `delayDays desc` 有序前 N 名；
  - 每个项目只保留最近快照。
- **业务链路示例片段**：
```java
DataSet delay = baseData.where("planProgress is not null and realProgress is not null")
    .groupBy(new String[]{"projectId", "deptId"})
    .avg("planProgress", "planProgress")
    .avg("realProgress", "realProgress")
    .avg("resourceRate", "resourceEfficiency")
    .maxP("updateTime", "updateId", "latestUpdateId")
    .finish()
    .addField("delayDays", "realProgress - planProgress")
    .addField("riskLevel", "case when abs(realProgress - planProgress) > 10 then '高风险' when abs(realProgress - planProgress) > 5 then '中风险' else '低风险' end")
    .topBy(30, new String[]{"delayDays desc"});
DataSet joined = delay.leftJoin(orgDS).on("deptId", "deptId")
    .select(new String[]{"projectId", "deptId", "planProgress", "realProgress", "resourceEfficiency", "delayDays", "riskLevel", "latestUpdateId", "deptName"});
```
- **报表取数建议**：偏差排名场景优先 `topBy`，比先 `orderBy+top` 更直观。

### 3. 建设行业 | 变更签证索赔结算风险
- **业务目标**：识别高金额变更、长期未处理签证与结算差异，支持按项目经理负责人追踪。
- **数据输入**：签证表、变更单、结算表、项目责任人表。
- **DataSet API 使用点**：
  - `where` + `filter(FilterFunction)`
  - `union`
  - `groupBy` + `sum` + `count` + `max`
  - `leftJoin` + `select`
- **输出字段/指标**：`projectId`、`changeAmt`、`claimCnt`、`settleCnt`、`remainRiskAmt`、`managerId`。
- **异常边界**：重复索赔单、未通过单据状态、币种混用。
- **验收标准**：
  - 结算缺口为负或零时置为 0；
  - 风险金额按照结算状态过滤。
- **业务链路示例片段**：
```java
DataSet risk = changeData.where("status in ('待审批','在办')")
    .groupBy(new String[]{"projectId","managerId"})
    .sum("changeAmount", "changeAmt")
    .count("id","changeCnt")
    .finish();
DataSet settle = settleData.groupBy(new String[]{"projectId","managerId"})
    .sum("settleAmount", "settleAmt")
    .count("id","settleCnt")
    .finish();
DataSet result = risk.leftJoin(settle).on("projectId","projectId").on("managerId","managerId")
    .select(new String[]{"projectId","managerId","changeAmt","changeCnt","settleAmt","settleCnt","changeAmt-settleAmt remainRiskAmt"});
```
- **报表取数建议**：风险口径中“未审批”与“已关闭”必须显式分桶，可结合 `splitByFilter` 进一步输出异常态。

### 4. 建设行业 | 重大项目风险整改闭环
- **业务目标**：按项目输出整改状态、整改次数、最新整改节点、问题清单聚合。
- **数据输入**：重大问题库、整改记录、责任部门字典。
- **DataSet API 使用点**：
  - `groupBy` + `count` + `maxP` + `groupConcat`
  - `join`（`fullJoin`）
  - `groupBy` + `addNullField` + `removeFields`
- **输出字段/指标**：`projectId`、`issueCnt`、`closedCnt`、`latestIssueId`、`issueList`、`closeRate`。
- **异常边界**：同一问题多次整改更新、关闭时间为空、责任人为空。
- **验收标准**：
  - 每个项目一行；
  - `issueList` 包含异常状态问题；
  - 闭环率与历史汇总一致。
- **业务链路示例片段**：
```java
DataSet issueAgg = issueData.groupBy(new String[]{"projectId"})
    .count("issueId","issueCnt")
    .count("if(state='已关闭','id',null)","closedCnt")
    .maxP("gmtModified","issueId","latestIssueId")
    .groupConcat("issueNo", "issueList", ",")
    .finish();
DataSet result = issueAgg.fullJoin(deptData).on("projectId", "projectId")
    .select(new String[]{"projectId","issueCnt","closedCnt","latestIssueId","issueList","deptName"});
```
- **报表取数建议**：`groupConcat` 对明细量大时可能较重，建议先去重再聚合。

### 5. 建设行业 | 项目群应收产值链路
- **业务目标**：项目群口径下追踪应收、已收、逾期金额与产值挂钩关系。
- **数据输入**：项目群关系、应收账款、开票/回款记录、产值认定表。
- **DataSet API 使用点**：
  - `groupBy` + `sum`
  - `leftJoin` 多级串联
  - `countDistinct`
  - `splitByFilter`
- **输出字段/指标**：`groupId`、`totalReceivable`、`receivedAmount`、`overdueAmount`、`outputAmount`、`collectRate`。
- **异常边界**：项目群映射缺失、应收/回款金额不同币种。
- **验收标准**：
  - group 与项目关系可回溯；
  - 应收=应收期初+新增-冲销；
  - 逾期金额与账龄规则一致。
- **业务链路示例片段**：
```java
DataSet overdue = arData.where("overdueDays > 30");
DataSet[] overdueBucket = overdue.splitByFilter(new String[]{
    "overdueDays between 31 and 60",
    "overdueDays between 61 and 90",
    "overdueDays > 90"
}, true);
DataSet overdueAgg = overdueBucket[0].union(overdueBucket[1], overdueBucket[2], overdueBucket[3])
    .groupBy(new String[]{"groupId", "projectId"})
    .sum("amount", "overdueAmount")
    .finish();
DataSet receipt = receiveData.groupBy(new String[]{"groupId"}).sum("receivedAmount","receivedAmount").finish();
DataSet output = outputData.groupBy(new String[]{"groupId"}).sum("outputAmount","outputAmount").finish();
DataSet result = output.leftJoin(receipt).on("groupId","groupId").leftJoin(overdueAgg).on("groupId","groupId")
    .select(new String[]{"groupId","outputAmount","receivedAmount","overdueAmount"});
```
- **报表取数建议**：`splitByFilter` 分桶后应保留 `includeOthers=true`，补出不在标准档期的数据。

### 6. 财务 | 营收确认与履约进度联动
- **业务目标**：按项目同步营收确认金额与履约进度，形成偏差预警看板。
- **数据输入**：合同收入、确认规则、进度里程碑、验收记录。
- **DataSet API 使用点**：
  - `groupBy` + `sum` + `maxP`
  - `where` + `distinct`
  - `join` + `select`
  - `orderBy`
- **输出字段/指标**：`projectId`、`recognizeAmount`、`progressRate`、`revenueGap`、`latestMilestoneId`。
- **异常边界**：项目验收状态冲突、同一期重复确认。
- **验收标准**：
  - 进度分母不为 0，若为 0 显式输出 0；
  - `revenueGap = recognizeAmount - 计划含税金额*progressRate`。
- **业务链路示例片段**：
```java
DataSet rev = revenueData.where("status='已确认'")
    .groupBy(new String[]{"projectId"})
    .sum("recognizeAmount", "recognizeAmount")
    .count("billId", "billCnt")
    .finish();
DataSet prog = mileData.groupBy(new String[]{"projectId"})
    .maxP("milestoneDate", "progressRate", "progressRate")
    .maxP("milestoneDate", "milestoneId", "latestMilestoneId")
    .finish();
DataSet result = rev.leftJoin(prog).on("projectId","projectId")
    .addField("revenueGap", "recognizeAmount - budgetAmount * progressRate")
    .select(new String[]{"projectId","recognizeAmount","progressRate","revenueGap","latestMilestoneId","billCnt"});
```
- **报表取数建议**：核算口径变化时将 `where` 条件显式传入参数，避免硬编码开始时间导致回溯不可控。

### 7. 财务 | 应收账龄穿透
- **业务目标**：输出应收账龄分布（30/60/90/120+）与项目负责人责任归集。
- **数据输入**：应收单据、客户主数据、账龄规则、项目基础资料。
- **DataSet API 使用点**：
  - `splitByFilter`
  - `groupBy` + `sum` + `countDistinct`
  - `leftJoin`
  - `orderBy`
- **输出字段/指标**：`projectId`、`agingBucket`、`arAmount`、`customerCnt`、`ownerUser`。
- **异常边界**：账龄日字段为空、负值金额、币种未统一。
- **验收标准**：
  - 账龄桶边界严格按规则；
  - 桶内金额与账龄总额一致；
  - 同一客户重复单据按 `countDistinct` 合理去重。
- **业务链路示例片段**：
```java
DataSet[] buckets = arData.splitByFilter(new String[]{
    "agingDays <= 30",
    "agingDays > 30 and agingDays <= 60",
    "agingDays > 60 and agingDays <= 90",
    "agingDays > 90"
}, true);
DataSet aging = buckets[0].union(buckets[1], buckets[2], buckets[3])
    .addField("agingBucket", "case when agingDays<=30 then '30天内' when agingDays<=60 then '31-60天' else '90天+' end")
    .groupBy(new String[]{"projectId","agingBucket"})
    .sum("arAmount","arAmount")
    .countDistinct(new String[]{"customerId"}, "customerCnt")
    .finish()
    .orderBy(new String[]{"projectId","agingBucket"});
```
- **报表取数建议**：账龄分桶应尽量下沉至 SQL，但若数据库差异导致表达式不可用，使用 `addField` 或 `map` 做兼容处理。

### 8. 财务 | 现金流预测与实际偏差
- **业务目标**：比较未来 12 期现金流预测与实际发生，输出偏差 Top。
- **数据输入**：预算现金流、历史到账记录、月度维度计划表。
- **DataSet API 使用点**：
  - `union`、`groupBy`、`avg`、`sum`、`orderBy`、`topBy`、`range`
- **输出字段/指标**：`month`、`planCash`、`actualCash`、`diff`、`diffRate`。
- **异常边界**：重复月度、跨周期冲销。
- **验收标准**：
  - 未来 12 期完整输出；
  - 差异值与单期明细核对一致。
- **业务链路示例片段**：
```java
DataSet plan12 = planData.where("bizMonth>= :m and bizMonth<= :m2").groupBy(new String[]{"bizMonth"})
    .sum("planAmount","planCash").finish();
DataSet act12 = actualData.where("bizMonth>= :m and bizMonth<= :m2").groupBy(new String[]{"bizMonth"})
    .sum("actualAmount","actualCash").finish();
DataSet merged = plan12.union(act12);
DataSet result = merged.groupBy(new String[]{"bizMonth"})
    .sum("planCash","planCash")
    .sum("actualCash","actualCash")
    .addField("diff", "actualCash - planCash")
    .addField("diffRate", "case when planCash=0 then 0 else round((actualCash-planCash)/planCash*100,2) end")
    .finish()
    .orderBy(new String[]{"bizMonth"})
    .topBy(12, new String[]{"abs(diff) desc"});
```
- **报表取数建议**：预测与实际表先分别聚合后再 union，避免月维度重复导致加总误差。

### 9. 财务 | 成本预算毛利偏差
- **业务目标**：按项目/组织展示预算与实际成本、收入、毛利偏差与毛利率趋势。
- **数据输入**：预算表、实际成本表、收入核算表、项目字典。
- **DataSet API 使用点**：
  - `groupBy` + `sum` + `min` + `max`
  - `leftJoin` + `on` + `select`
- **输出字段/指标**：`projectId`、`budgetCost`、`actualCost`、`grossMargin`、`variance`、`grossRate`。
- **异常边界**：多币种混列、同项目多版本预算。
- **验收标准**：
  - 毛利率公式统一；
  - 预算成本/实际成本字段来源一致，时间粒度对齐。
- **业务链路示例片段**：
```java
DataSet budget = budgetData.groupBy(new String[]{"projectId","orgId"})
    .sum("budgetCost", "budgetCost").sum("budgetIncome","budgetIncome").finish();
DataSet actual = costData.groupBy(new String[]{"projectId"})
    .sum("actualCost","actualCost").sum("actualIncome","actualIncome").finish();
DataSet margin = budget.leftJoin(actual).on("projectId","projectId")
    .select(new String[]{"projectId","orgId","budgetCost","budgetIncome","actualCost","actualIncome","budgetIncome-actualIncome","budgetCost-actualCost"});
```
- **报表取数建议**：用 `addField` 生成 `grossMargin`，避免 SQL 侧硬编码 `CASE` 引起兼容差异。

### 10. 财务 | 税金进销项税负分析
- **业务目标**：按项目/月份归集进项税、销项税、税负率及异常税码。
- **数据输入**：票据明细、税码字典、项目关联关系。
- **DataSet API 使用点**：
  - `where` + `filter` + `distinct`
  - `groupBy` + `sum` + `avg`
  - `groupConcat`
  - `join` + `select`
- **输出字段/指标**：`projectId`、`inputTax`、`outputTax`、`taxRate`、`abnormalTaxCodes`。
- **异常边界**：税率为 0 或 null、税码未维护。
- **验收标准**：
  - 税负率计算异常记录可追溯税码；
  - 税码清单可读且不重复。
- **业务链路示例片段**：
```java
DataSet taxBase = invoiceData.where("bizType in ('销项','进项')");
DataSet dedup = taxBase.distinct();
DataSet summary = dedup.groupBy(new String[]{"projectId","taxMonth","bizType"})
    .sum("taxAmount","taxSum")
    .avg("taxRate","avgTaxRate")
    .countDistinct(new String[]{"taxCode"}, "taxCodeCnt")
    .finish();
DataSet codes = dedup.groupBy(new String[]{"projectId","taxMonth"})
    .groupConcat("taxCode","taxCodes",",")
    .finish();
DataSet result = summary.leftJoin(codes).on("projectId","projectId").select("projectId","taxMonth","taxSum","avgTaxRate","taxCodes");
```
- **报表取数建议**：税码先 `distinct` 再 `groupConcat`，避免同一票据重复注入串行号。

### 11. 财务 | 合同履约成本义务往来综合看板
- **业务目标**：按项目输出履约金额、预付款/进度款、待处理款项与风险敞口。
- **数据输入**：合同主表、应付应收往来、付款计划、工程结算。
- **DataSet API 使用点**：
  - `toHashTable` + `hashJoin` + `addHashTable`
  - `selectLeftFields` + `leftJoin` + `select`
- **输出字段/指标**：`projectId`、`contractAmt`、`paidAmt`、`certifyAmt`、`payableExposure`。
- **异常边界**：主辅表 key 不一致、缺少履约计划版本。
- **验收标准**：
  - 合同外键映射完整；
  - 应收应付不应出现负值（除负向冲销记录外）。
- **业务链路示例片段**：
```java
HashTable ct = contractData.toHashTable("projectId");
DataSet settle = settleAgg.groupBy(new String[]{"projectId"}).sum("settleAmount","certifyAmt").finish();
DataSet paid = paidData.groupBy(new String[]{"projectId"}).sum("paidAmount","paidAmt").finish();
DataSet base = contractData.groupBy(new String[]{"projectId"}).sum("contractAmount","contractAmt").finish();
DataSet joined = base.hashJoin(ct, "projectId", new String[]{"orgId","owner"})
    .addHashTable(ct, "projectId", new String[]{"owner"})
    .selectLeftFields(new String[]{"projectId","contractAmt","orgId","owner"})
    .finish();
DataSet result = joined
    .leftJoin(settle).on("projectId", "projectId")
    .leftJoin(paid).on("projectId", "projectId")
    .addField("payableExposure", "contractAmt - paidAmt")
    .select(new String[]{"projectId", "orgId", "owner", "contractAmt", "paidAmt", "certifyAmt", "payableExposure"});
```
- **报表取数建议**：对大项目字典优先使用 `hashJoin`，比逐行 `join` 更稳定，注意 key 类型一致。

### 12. 财务 | 票据差异核销风险
- **业务目标**：识别票据金额差异、缺失核销记录、异常状态变更。
- **数据输入**：票据表、核销记录表、单据附件表。
- **DataSet API 使用点**：
  - `join`（`leftJoin`） + `on` + `select`
  - `groupBy` + `sum` + `count`
  - `filter(FilterFunction)`（业务判定）
- **输出字段/指标**：`billNo`、`billAmt`、`reconAmt`、`diffAmt`、`reconState`、`riskTag`。
- **异常边界**：多币种、重复核销记录、挂起单据。
- **验收标准**：
  - 差异非零的票据都能落在异常列表；
  - 风险标签与差异量级一致。
- **业务链路示例片段**：
```java
DataSet r = billData.leftJoin(reconData).on("billId", "billId")
    .select(new String[]{"billId","billNo","billAmount","reconAmount","currency","status","reconTime"});
DataSet filtered = r.filter(new FilterFunction() {
    public boolean test(Row row) {
        BigDecimal a = row.getBigDecimal("billAmount");
        BigDecimal b = row.getBigDecimal("reconAmount");
        return a != null && b != null && a.compareTo(b) != 0;
    }
});
DataSet result = filtered.groupBy(new String[]{"billNo"})
    .sum("billAmount","billAmount")
    .sum("reconAmount","reconAmount")
    .count("status","reconCnt").finish()
    .addField("diffAmt", "billAmount - reconAmount");
```
- **报表取数建议**：先按单据去重再核算，避免主明细重复膨胀。

### 13. HR | 项目组织与班子配置合规
- **业务目标**：校验项目组织中关键角色是否到位，输出缺失风险与替补建议。
- **数据输入**：组织表、岗位表、任职表、项目关系表。
- **DataSet API 使用点**：
  - `groupBy` + `countDistinct`
  - `where` + `distinct`
  - `leftJoin` + `select`
  - `count(String, boolean)`（阈值判断）
- **输出字段/指标**：`projectId`、`requiredRoleCnt`、`filledRoleCnt`、`missingRoleCnt`、`complianceRate`。
- **异常边界**：岗位分类标准变化、临时组织未同步。
- **验收标准**：
  - 关键岗位缺失率 = `(required - filled)/required`；
  - 关键岗位缺失项目标识明确。
- **业务链路示例片段**：
```java
DataSet required = roleStandardData.groupBy(new String[]{"projectId","roleCode"}).count("roleCode","requiredRoleCnt").finish();
DataSet actual = personRoleData.where("state='在岗'")
    .groupBy(new String[]{"projectId","roleCode"})
    .countDistinct(new String[]{"personId"}, "filledRoleCnt")
    .finish();
DataSet result = required.leftJoin(actual).on("projectId","projectId").on("roleCode","roleCode")
    .select(new String[]{"projectId","roleCode","requiredRoleCnt","filledRoleCnt"});
```
- **报表取数建议**：角色缺失可额外写入 `leftJoin` 到组织主数据，支持到项目经理视图。

### 14. HR | 人员配置效率与岗位负荷
- **业务目标**：分析项目部岗位配备、单人负荷和人均产出，识别过载岗位。
- **数据输入**：人员工时、岗位映射、项目任务工时计划。
- **DataSet API 使用点**：
  - `groupBy` + `sum` + `avg`
  - `topBy`
  - `splitByGroup`
- **输出字段/指标**：`projectId`、`jobCode`、`personCnt`、`avgHours`、`loadRate`、`overloadFlag`。
- **异常边界**：工时重复登记、岗位代码未标准化。
- **验收标准**：
  - 每岗位仅一行汇总；
  - 超过阈值项有明确标记并可追溯证据行。
- **业务链路示例片段**：
```java
DataSet load = workHourData.where("workHours > 0").groupBy(new String[]{"projectId","jobCode"})
    .sum("workHours","totalHours")
    .countDistinct(new String[]{"personId"},"personCnt")
    .finish();
DataSet ratio = load.addField("avgHours", "totalHours / personCnt")
    .addField("overloadFlag", "case when totalHours/personCnt > 220 then '重载' else '正常' end");
DataSet top = ratio.topBy(20, new String[]{"avgHours desc"});
```
- **报表取数建议**：先按月/项目聚合后再做岗位排名，避免原始明细重复导致平均值失真。

### 15. HR | 证书有效性与任职合规
- **业务目标**：监控人员岗位证书在岗期有效性，输出即将到期/过期名单。
- **数据输入**：人员证书库、岗位匹配规则、项目任职表。
- **DataSet API 使用点**：
  - `where` + `splitByFilter`
  - `groupBy` + `count`
  - `join` + `select`
- **输出字段/指标**：`personId`、`projectId`、`certName`、`validDays`、`riskLevel`、`gapDays`。
- **异常边界**：证书缺失、有效期为空、岗位要求变更。
- **验收标准**：
  - 到期前 30 天以内标黄/红；
  - 证书为空时给出 `缺失` 标签。
- **业务链路示例片段**：
```java
DataSet valid = certData.where("expireDate is not null");
DataSet[] bucket = valid.splitByFilter(new String[]{
    "datediff(day, current_date, expireDate) <= 30",
    "datediff(day, current_date, expireDate) > 30 and datediff(day, current_date, expireDate)<=90",
    "datediff(day, current_date, expireDate) > 90"
}, true);
DataSet result = bucket[0].union(bucket[1], bucket[2]).groupBy(new String[]{"personId","projectId","certName"})
    .count("id","certCnt").finish()
    .addField("riskLevel", "case when datediff(day, current_date, expireDate) <= 30 then '高' when datediff(day,current_date,expireDate)<=90 then '中' else '低' end");
```
- **报表取数建议**：高风险名单需关联组织/负责人，支持 `leftJoin` 呈现到项目负责人。

### 16. HR | 人员流动交接与断档预警
- **业务目标**：识别关键岗位离岗后的交接缺口与断档时长。
- **数据输入**：岗位任职变更、交接记录、关键人目录。
- **DataSet API 使用点**：
  - `orderBy` + `maxP` + `minP`
  - `groupBy` + `count`
  - `map` + `splitByFilter`
- **输出字段/指标**：`personId`、`projectId`、`leaveDate`、`handoverDate`、`gapDays`、`impactLevel`。
- **异常边界**：交接记录滞后、同人多岗位。
- **验收标准**：
  - 关键岗位离岗有明确断档状态；
  - gapDays 统一秒/天单位。
- **业务链路示例片段**：
```java
DataSet latest = assignData.groupBy(new String[]{"personId","projectId"})
    .maxP("startDate", "assignId", "latestAssign")
    .minP("endDate", "assignId", "firstEnd")
    .finish();
DataSet handover = handoverData.groupBy(new String[]{"personId","projectId"})
    .maxP("handoverDate","handoverId","handoverDateMax")
    .finish();
DataSet risk = latest.leftJoin(handover).on("personId","personId").on("projectId","projectId")
    .addField("gapDays", "datediff(day, latestAssign, handoverDateMax)")
    .splitByFilter(new String[]{"gapDays > 7","gapDays between 1 and 7","gapDays <= 1"}, true)[0]
    .select(new String[]{"personId","projectId","latestAssign","handoverDateMax","gapDays"});
```
- **报表取数建议**：离岗时点尽量基于任职结束记录，避免从审批时间推算导致误差。

### 17. HR | 人员绩效排名与组织贡献度
- **业务目标**：按组织和个人汇总任务履约、考核分、奖金池占比。
- **数据输入**：绩效打分、任务完成率、奖金发放记录。
- **DataSet API 使用点**：
  - `groupBy` + `sum` + `avg`
  - `topBy` + `orderBy`
  - `reduceGroup`/`reduceGroupWithCollector`
- **输出字段/指标**：`orgId`、`personId`、`perfScore`、`contribIndex`、`bonusRate`、`rankNo`。
- **异常边界**：评分缺失、任务为空、奖金与绩效维度口径不一致。
- **验收标准**：
  - 同组织排名可重复运行一致；
  - 贡献度总和与组织累计奖金匹配。
- **业务链路示例片段**：
```java
DataSet agg = perfData.groupBy(new String[]{"orgId","personId"})
    .sum("taskScore","taskScore")
    .avg("rate","avgScore")
    .sum("bonusAmount","bonusTotal")
    .finish();
DataSet ranked = agg.addField("contribIndex", "taskScore*0.6 + avgScore*0.4")
    .topBy(100, new String[]{"contribIndex desc", "orgId"});
DataSet reduced = ranked.groupBy(new String[]{"orgId"}).reduceGroup(new ReduceGroupFunction() {
    @Override
    public java.util.Iterator<Object[]> reduce(java.util.Iterator<Row> it) {
        BigDecimal total = BigDecimal.ZERO;
        List<Object[]> rows = new java.util.ArrayList<>();
        while (it.hasNext()) {
            Row r = it.next();
            rows.add(new Object[]{r.get("orgId"), r.getBigDecimal("contribIndex"), total});
            total = total.add(r.getBigDecimal("contribIndex") == null ? BigDecimal.ZERO : r.getBigDecimal("contribIndex"));
        }
            return rows.iterator();
        }
    });
```
- **报表取数建议**：性能敏感的排名建议分页加载，通过 `range` 拆分。

### 18. HR | 关键岗位连续性与薪资影响
- **业务目标**：结合关键岗位断档与离职/入职时点，评估对薪酬结构的冲击。
- **数据输入**：薪资历史、岗位调整记录、关键岗清单、项目组织。
- **DataSet API 使用点**：
  - `cache`/`cacheBuilder`
  - `groupBy` + `sum` + `countDistinct`
  - `copy` + `addBalanceField`
  - `join` + `select`
- **输出字段/指标**：`projectId`、`keyRolePersonCnt`、`salaryImpact`、`continuousRate`、`riskLevel`。
- **异常边界**：断档期缺薪资记录、岗位代码变更。
- **验收标准**：
  - 缓存命中后再次计算结果一致；
  - 连续率/薪资影响与历史明细核对一致。
- **业务链路示例片段**：
```java
DataSet base = keyRoleData.groupBy(new String[]{"projectId","personId"})
    .sum("salary", "salarySum")
    .countDistinct(new String[]{"personId"}, "personCnt")
    .finish()
    .addBalanceField("salarySum", "salaryBalance");
CacheHint ch = new CacheHint();
ch.setCacheId("hr-key-role-cache");
CachedDataSet cached = base.cache(ch);
DataSet fromCache = cached.toDataSet(Algo.create("hr-from-cache"), true)
    .addField("riskLevel", "case when salaryBalance > 100000 then '高' else '低' end");
DataSet result = fromCache.leftJoin(orgMeta).on("projectId","projectId")
    .select(new String[]{"projectId","personCnt","salaryBalance","riskLevel","orgName"});
```
- **报表取数建议**：对长期看板页启用缓存，结合 `cacheId` + 分页参数，避免重复计算波动。

## 注意事项

- 18 个场景优先按“字段标准化 -> 聚合 -> 关联 -> 派生 -> 分桶/分页”顺序实现，便于单元调试与回溯。
- 所有表达式示例默认按项目当前数据库方言执行，若数据库函数不一致请在 `addField` 层统一兼容处理。
- `splitByFilter` 与 `map` 适合复杂规则，但对大表建议配合 `setId` 与监听埋点核查行数与耗时。
- 风险预警口径应先固定“阈值常量表”，避免硬编码导致版本差异不可追踪。

## 编译与校验记录

- 验证时间：2026-04-13
- 执行环境：本地 `ztjg` 工程，Java 8 编译目标，依赖 `bos-algo-7.0.jar`
- 签名证据：`file:/tmp/dataset-advanced-lab/evidence/dataset-api-signatures.txt`
- 完整可编译示例：`ztjg.cosmic.debug.algo.knowledge.fixture` 与 `ztjg.cosmic.debug.algo.knowledge.sample`
- 执行命令：

```bash
javac -source 8 -target 8 -encoding UTF-8 -cp /Users/anfeng/utils/cosmic/home/mservice-cosmic/lib/bos/bos-algo-7.0.jar -d /tmp/dataset-advanced-lab/classes code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/fixture/AlgoKnowledgeFixture.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/CustomFunctions.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/DataSetApiSamples.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/GroupByApiSamples.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/JoinApiSamples.java code/ztjg-cosmic-debug/src/main/java/ztjg/cosmic/debug/algo/knowledge/sample/HashJoinApiSamples.java
./gradlew --no-parallel :ztjg-cosmic-debug:compileJava --console=plain -Dorg.gradle.jvmargs=-Xmx4g
```

- 输出摘要：新增可编译示例覆盖 18 个需求所用的主要 DataSet API 组合，模块编译通过。
- 退出码：0

## 相关链接

- 本地签名：`file:/tmp/dataset-advanced-lab/evidence/dataset-api-signatures.txt`
- 本地苍穹开发文档：`file:/Users/anfeng/utils/cosmic/home/static-file-service/devdoc/corelib/algo/README.md`
- 开发者社区：`https://developer.kingdee.com/developer?productLineId=29`
- 报表参考源码：
  - `/Users/anfeng/Code/Work/ztjg/code/promise/ztjg-promise-appointment/src/main/java/ztjg/promise/appointment/plugin/report/EngineProjectRPTPlugin.java`
  - `/Users/anfeng/Code/Work/ztjg/code/promise/ztjg-promise-appointment/src/main/java/ztjg/promise/appointment/plugin/report/DeliverProjectRPTPlugin.java`
  - `/Users/anfeng/Code/Work/ztjg/code/promise/ztjg-promise-appointment/src/main/java/ztjg/promise/appointment/plugin/report/LevelNodeWarnRPTPlugin.java`
  - `/Users/anfeng/Code/Work/ztjg/code/promise/ztjg-promise-appointment/src/main/java/ztjg/promise/appointment/plugin/report/RailMajorSecureNewRPTPlugin.java`
  - `/Users/anfeng/Code/Work/ztjg/code/dswpt/ztjg-dswpt-dsw/src/main/java/ztjg/dswpt/dsw/hr/coreman/rpt/IdentityEmpReportPlugin.java`
