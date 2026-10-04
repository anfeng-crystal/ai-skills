# propertyChanged - 字段值改变与完整金额重算

来源：从 [表单插件.md](../表单插件.md#2-propertychanged) 拆出。

`propertyChanged(e: PropertyChangedArgs)` 通知当前字段发生变化；字段名来自 `e.getProperty().getName()`，各条 `ChangeData` 提供行索引、数据包和新旧值。手工输入先执行该字段实体服务规则，再到插件；初始化赋值走独立路径，不能声称普通事件覆盖初始化、后台导入或所有保存入口。

## 业务与接入合同

保留销售订单数量×单价、含税金额、税额以及三项头合计。下例明确采用两位 `ROUND_HALF_UP` 逐行舍入、税率百分数（13表示13%）、税率除100保留六位；这只是本例已选口径，不能覆盖项目币种精度或税额引擎。

- `qty` 或 `price` 为空：三项行金额均清空；仅 `taxrate` 为空：仍算未税金额，含税金额/税额清空。未知不当免税；零数量、零单价、零税率仍按明确数值计算。
- 对应头金额只在全部行该金额已知时汇总，否则清空；空表合计为0。若项目规定空值为0或保留人工金额，应替换整套明确规则，不能局部 `return` 留旧值。
- 工厂参数 `validate` 是项目只读接入合同，不是平台API：核普通 `billentry` 全量有序行、输入字段归属、所有六个输出允许null且精度匹配，以及本例独占这些计算结果、不存在结果反写输入的循环。分批、子分录、多币种、人工覆盖或折扣等口径未满足时改接项目已有计算引擎，不传空函数冒充核验。

## 完整示例代码

```typescript
import { AbstractBillPlugIn } from "@cosmic/bos-core/kd/bos/bill";
import { IDataModel } from "@cosmic/bos-core/kd/bos/entity/datamodel";
import { PropertyChangedArgs } from "@cosmic/bos-core/kd/bos/entity/datamodel/events";
import { BigDecimal } from "@cosmic/bos-script/java/math";

/** 本例采用完整普通分录、可空金额、两位逐行四舍五入和百分税率。
 * validate 是项目只读核验：字段归属/允许空/精度、完整范围及唯一金额计算所有者。
 * 不满足本例合同须接入已有金额引擎，不能以空实现跳过核验。
 */
function createSalesAmountPlugin(validate: (model: IDataModel) => void): AbstractBillPlugIn {
  type Money = BigDecimal | null;
  const inputs = ["qty", "price", "taxrate"];
  const outputs = ["amount", "taxincamount", "taxamount"];
  const totals = ["totalamount", "totaltaxincamount", "totaltaxamount"];

  /** 数值等价即可，null 与 0 保持不同；非法数值类型直接报错。 */
  function equal(a: Money, b: Money): boolean {
    return a === null || b === null ? a === b : a.compareTo(b) === 0;
  }
  function decimal(value: unknown): Money {
    if (value == null) return null;
    if (!(value instanceof BigDecimal)) throw new Error("金额输入必须为BigDecimal");
    return value;
  }
  /** 三个目标都生成新值；清空输入绝不保留上一次计算结果。 */
  function calculate(v: Money[]): Money[] {
    const [qty, price, rate] = v;
    if (qty === null || price === null) return [null, null, null];
    const amount = qty.multiply(price).setScale(2, BigDecimal.ROUND_HALF_UP);
    if (rate === null) return [amount, null, null];
    const taxInc = amount.multiply(BigDecimal.ONE.add(
      rate.divide(new BigDecimal("100"), 6, BigDecimal.ROUND_HALF_UP)
    )).setScale(2, BigDecimal.ROUND_HALF_UP);
    return [amount, taxInc, taxInc.subtract(amount)];
  }
  class SmSalorderCalcPlugin extends AbstractBillPlugIn {
    /** true 仅让本监听器接收当前字段的整个ChangeData[]，不是跨字段批次结束通知。 */
    isSupportBatchPropChanged(): boolean { return true; }
    propertyChanged(e: PropertyChangedArgs): void {
      super.propertyChanged(e);
      if (inputs.indexOf(e.getProperty().getName()) < 0 || e.getChangeSet().length === 0) return;
      const model = this.getModel();
      validate(model);
      const count = model.getEntryRowCount("billentry");
      if (!Number.isSafeInteger(count) || count < 0) throw new Error("分录范围无效");
      const rows = Array.from({ length: count }, (_, i) => model.getEntryRowEntity("billentry", i));
      const values = rows.map((_, i) => inputs.map(k => decimal(model.getValue(k, i))));
      const plan = values.map(calculate);
      // 任一行该金额未知，则头对应金额也未知；空表汇总为0。
      const sums: Money[] = outputs.map((_, col) => {
        let sum = BigDecimal.ZERO;
        for (const row of plan) {
          const n = row[col];
          if (n === null) return null;
          sum = sum.add(n);
        }
        return sum;
      });
      /** 写入前后核完整行身份与输入，避免事件索引或规则回写改变本次计算口径。 */
      const stable = (): void => {
        validate(model);
        if (model.getEntryRowCount("billentry") !== count) throw new Error("计算期间分录数量变化");
        rows.forEach((row, i) => {
          if (model.getEntryRowEntity("billentry", i) !== row) throw new Error("计算期间分录顺序变化");
          inputs.forEach((k, j) => {
            if (!equal(decimal(model.getValue(k, i)), values[i][j])) throw new Error("计算期间输入变化");
          });
        });
      };
      /** 只写数值有差异的字段，减少二次派发；立即读回检测可空/精度/同步规则冲突。 */
      const write = (key: string, value: Money, row: number): void => {
        stable();
        if (!equal(decimal(model.getValue(key, row)), value)) model.setValue(key, value, row);
        stable();
        if (!equal(decimal(model.getValue(key, row)), value)) throw new Error("金额被字段配置或规则改写：" + key);
      };
      stable();
      plan.forEach((row, i) => row.forEach((value, j) => write(outputs[j], value, i)));
      // 全部行目标读回正确之后才写头合计，不汇总任何旧派生值。
      const checkRows = (): void => plan.forEach((row, i) => row.forEach((value, j) => {
        if (!equal(decimal(model.getValue(outputs[j], i)), value)) throw new Error("分录金额被后续同步规则改写");
      }));
      checkRows();
      sums.forEach((value, j) => write(totals[j], value, 0));
      stable();
      checkRows();
      sums.forEach((value, j) => {
        if (!equal(decimal(model.getValue(totals[j], 0)), value)) throw new Error("头金额被后续同步规则改写");
      });
    }
  }
  return new SmSalorderCalcPlugin();
}
export { createSalesAmountPlugin };
```

项目完成上述合同实现后创建并导出 `plugin = createSalesAmountPlugin(projectValidate)`。示例先基于完整输入形成行金额与头合计计划，再只写差异；一次回调内完成所有变更对应的金额刷新和一次头汇总。不依靠派生字段旧值汇总，不用 `beginInit()` 屏蔽业务规则。

## 消费者与验证边界

本机7.0 `ModelEventProxy` 对每个监听器读取 `isSupportBatchPropChanged()`：true交当前字段原始变化数组，false逐条拆开；`DefaultPropChangedContainer`/`PropChangedTaskCollection` 的待处理任务按字段组织，执行中 `setValue` 还会追加任务。故一次回调返回不是整条规则链的最终稳定点，不能宣称开启批量模式就把整次导入/跨字段变化合为一次。

`DecimalProp.setFieldValue` 在不允许空时把null转0，非空还会按元数据处理精度，所以必须先核字段配置并读回；读回仅能发现已发生的同步改写。后续排队规则、其他监听器或下一次请求仍可能更改结果，应消除多计算所有者，并在项目正式保存/提交校验中重算最终金额。中途异常可能留下部分写入；本例没有事务或自动回滚，也不宣称读回检测能撤销旧事件。 完整输入检查会在写前后重复扫描，成本约随行数平方增长；大表应接项目已有批量计算引擎，不以此例宣称性能提升。

依据：[官方propertyChanged事件](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=228917111786574080&type=Knowledge&productLineId=29)（2026-07-31 11:59；未给完整目标版本范围）及目标实际7.0 JAR派发/字段消费者。SDK类型检查与本地替身验证不代表KingScript或真实页面验收。
