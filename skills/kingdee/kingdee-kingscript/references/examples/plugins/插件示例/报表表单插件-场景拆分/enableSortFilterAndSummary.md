# enableSortFilterAndSummary - 排序过滤与已有合计的格式化

## 场景与原能力

保留报表列头排序、过滤，以及金额、数量、加权均价和非空单号结果行计数。列头默认由平台自动处理，控件需已开启相应能力且满足类型、数据源绑定及行数条件；合计部分按目标7.0的真实 `setFloatButtomData` 事件实现。

## 数据与列合同

- 在既有取数的最终明细输出调用 `withBillNumberCount(data, "billno")`，把非null单号贡献转成1/0；`getColumns` 只添加一次 `billNumberCountColumn()`。重复单号各行分别计，空字符串也非null，不是去重单据数。若结果已分组，先在明细生成贡献，再按原分组sum带出，不能给每个组补1。
- 既有 `kdec_total_amount/kdec_total_qty/kdec_avg_price` 必须是可汇总数值列并设 `summary=1`；新增的 `kdec_billno_count` 只是结果列。真实实体字段和查询权限仍使用项目已确认映射，不在此另造业务实体或SQL。
- 平台已先求sum；回调只设置 `formatSummaryValue`。均价使用同范围金额合计/数量合计，不能求各行均价的平均。缺分子/分母或分母0显示“—”，展示为2位HALF_UP；原合计值不变。

## KingScript 示例

```typescript
import { AbstractReportFormPlugin } from "@cosmic/bos-core/kd/bos/report/plugin";
import { SummaryEvent } from "@cosmic/bos-core/kd/bos/report/events";
import { DataSet } from "@cosmic/bos-core/kd/bos/algo";
import { DecimalReportColumn, ReportColumn } from "@cosmic/bos-core/kd/bos/entity/report";
import { LocaleString } from "@cosmic/bos-core/kd/bos/dataentity/entity";
import { BigDecimal, RoundingMode } from "@cosmic/bos-script/java/math";

interface SummaryFields {
  amount: string;
  qty: string;
  price: string;
  cost?: string;
  profitRate?: string;
  count?: string;
}

/** 接入既有query的最终明细输出；按非null单号计结果行，重复单号各行分别计数。 */
function withBillNumberCount(data: DataSet, billField: "kdec_billno" | "billno" = "kdec_billno"): DataSet {
  if (billField !== "kdec_billno" && billField !== "billno") throw new Error("未知单号别名");
  return data.addField("CASE WHEN " + billField + " IS NULL THEN 0 ELSE 1 END", "kdec_billno_count");
}

/** 在既有getColumns中只添加一次；这是数值贡献的sum列，不把文本billno当数值合计列。 */
function billNumberCountColumn(): DecimalReportColumn {
  const column = new DecimalReportColumn();
  column.setFieldKey("kdec_billno_count");
  column.setDateIndex("kdec_billno_count");
  column.setFieldType(ReportColumn.TYPE_DECIMAL);
  column.setCaption(new LocaleString("非空单号结果行数"));
  column.setScale(0);
  column.setSummary(1);
  return column;
}

/** 源汇总为空/无法无损解读时保持未知，不把缺值或已丢精度的JS浮点补成0。 */
function decimalSummary(value: unknown): BigDecimal | null {
  if (value == null) return null;
  if (typeof value === "number" && !Number.isSafeInteger(value)) return null;
  const text = String(value);
  if (!/^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$/.test(text)) return null;
  try { return new BigDecimal(text); } catch (_) { return null; }
}

/** 两遍读取本次源合计，再改展示值；金额/数量/成本必须同一范围、币种和单位口径。 */
function formatReportTotals(events: $.java.util.List, fields: SummaryFields): void {
  const totals = new Map<string, BigDecimal | null>();
  const needed = new Set<string>([fields.amount, fields.qty]);
  if (fields.cost != null) needed.add(fields.cost);
  if (fields.count != null) needed.add(fields.count);
  for (let i = 0; i < events.size(); i++) {
    const event = events.get(i) as SummaryEvent;
    const key = event.getColumnName();
    if (!needed.has(key)) continue;
    if (totals.has(key)) throw new Error("汇总列标识重复：" + key);
    totals.set(key, decimalSummary(event.getSrcSummaryValue()));
  }
  const amount = totals.get(fields.amount);
  const qty = totals.get(fields.qty);
  const cost = fields.cost == null ? null : totals.get(fields.cost);
  const zero = new BigDecimal("0");
  for (let i = 0; i < events.size(); i++) {
    const event = events.get(i) as SummaryEvent;
    const key = event.getColumnName();
    if (key === fields.amount || key === fields.qty || key === fields.count) {
      const value = totals.get(key);
      if (value != null) event.setFormatSummaryValue(value.toPlainString());
    } else if (key === fields.price) {
      event.setFormatSummaryValue(amount == null || qty == null || qty.compareTo(zero) === 0
        ? "—" : amount.divide(qty, 2, RoundingMode.HALF_UP).toPlainString());
    } else if (fields.profitRate != null && key === fields.profitRate) {
      event.setFormatSummaryValue(amount == null || cost == null || amount.compareTo(zero) === 0
        ? "—" : amount.subtract(cost).multiply(new BigDecimal("100"))
          .divide(amount, 2, RoundingMode.HALF_UP).toPlainString() + "%");
    }
  }
}

/** 排序过滤保留原有入口；同步合计只格式化已计算值。 */
class EnableSortFilterAndSummaryPlugin extends AbstractReportFormPlugin {
  setFloatButtomData(events: $.java.util.List): void {
    super.setFloatButtomData(events);
    formatReportTotals(events, {
      amount: "kdec_total_amount", qty: "kdec_total_qty", price: "kdec_avg_price", count: "kdec_billno_count"
    });
  }
}
const plugin = new EnableSortFilterAndSummaryPlugin();
export { plugin, EnableSortFilterAndSummaryPlugin, formatReportTotals, withBillNumberCount, billNumberCountColumn };
```

## 真实消费边界

目标7.0的拼写是 `setFloatButtomData`；`SummaryEvent` 使用 `getColumnName/getSrcSummaryValue/setFormatSummaryValue`。只有平台已为Decimal数值列产生合计，且 `summary==1` 时才有对应事件；不存在 `setSummaryType("sum"/"avg"/"count")` 来配置算法或给文本单号计数的能力。异步总计路径会跳过此同步回调。

存在查询插件时 `setFilter(true)/setSort(true)` 声明插件接管；本例未提供接管所需的取数映射，因此不重写该事件，保留平台自动能力和其他插件既有处理。要禁止指定列或真正接管，按[第26节](../报表表单插件.md#26-setsortandfilter---设置过滤排序列)配置最终策略及取数消费者。列头过滤后的计数来自贡献列重新汇总，不能复用过滤前缓存的统计。此格式化不改导出/打印的数据或业务记录；分批、二次过滤、异步合计和文件导出要按各自消费者验收。相关完整说明见 [报表表单插件第28节](../报表表单插件.md#28-setfloatbuttomdata---格式化已有合计值)。
