# splitTargetRowsAfterConvert - 转换后按数量拆分目标数据

## 场景与完整调用链

采购源单下推固定资产卡片，每件资产生成一张主卡片：`afterCreateTarget` 先读取目标分录对应的首条来源行，将来源单号写入 `memo`；`afterConvert` 再把 `fa_card_real` 主实体按精确正整数数量拆分。这里保留两个事件的完整链路，不把主实体索引算法直接套用到分录或子分录。

## 前提与数量规则

- 插件基类为 `AbstractConvertPlugIn`，事件分别使用 `AfterCreateTargetEventArgs`、`AfterConvertEventArgs`。
- 目标分录标识 `entryentity`、来源字段 `billno`、备注字段 `memo`，以及目标主实体 `fa_card_real` 的 `assetamount/sourceentrysplitseq` 都须与实际元数据一致。`ConvertSource` 是转换器提供的来源行扩展值；字段属性从事件 `getFldProperties` 取。
- 一物一卡的数量必须为 `int` 范围内的正整数。TypeScript `as number` 没有运行时强转效果；通过 `BigDecimal(...).intValueExact()` 拒绝小数和越界值，不取整、不截断、不把零/负数改成 1。传入前已经丢失的数值精度不能由字符串转换恢复，应按真实数量字段类型接入。
- `maxCardsPerConvert=1000` 是本例可调整的批量保护值，超过时在修改原卡前拒绝并提示分批；它不是平台固有限制。应根据项目容量确认或调整，不能悄悄只生成前 1000 张。

## 完整 KingScript 示例

```typescript
import { ExtendedDataEntity } from "@cosmic/bos-core/kd/bos/entity";
import { AbstractConvertPlugIn } from "@cosmic/bos-core/kd/bos/entity/botp/plugin";
import { AfterConvertEventArgs, AfterCreateTargetEventArgs } from "@cosmic/bos-core/kd/bos/entity/botp/plugin/args";
import { DynamicObject } from "@cosmic/bos-core/kd/bos/dataentity/entity";
import { OrmUtils } from "@cosmic/bos-core/kd/bos/dataentity/utils";
import { ArrayList } from "@cosmic/bos-script/java/util";
import { BigDecimal } from "@cosmic/bos-script/java/math";

/**
 * 采购单转换固定资产主卡片：来源分录补备注，再按离散单件数量拆分 fa_card_real。
 * 字段必须由目标元数据声明；金额、关联行与反写量须按项目合同在拆分时调整并验收；此处克隆不自动分摊。
 * 本例 1000 张是可调整的本地批量保护值，不是平台限制。不会主动保存或下推。
 */
class SplitTargetRowsAfterConvertPlugin extends AbstractConvertPlugIn {
  private readonly maxCardsPerConvert = 1000;
  private readonly maxDataIndex = 2147483647;

  /** 从转换器提供的源行列表及字段属性读取首条源单号；没有来源时不覆盖原备注。 */
  afterCreateTarget(e: AfterCreateTargetEventArgs): void {
    const rows = e.getTargetExtDataEntitySet().FindByEntityKey("entryentity");
    const billNoProp = e.getFldProperties().get("billno");
    if (billNoProp == null) { return; }
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      const sourceRows = row.getValue("ConvertSource") as $.java.util.List;
      if (sourceRows == null || sourceRows.size() === 0) { continue; }
      const sourceBillNo = billNoProp.getValue(sourceRows.get(0));
      if (sourceBillNo == null || String(sourceBillNo).length === 0) { continue; }
      this.requireProperty(row.getDataEntity(), "memo");
      row.setValue("memo", "来源单号：" + String(sourceBillNo));
    }
  }

  /**
   * 先校验整批数量、字段和索引，再准备副本；准备完成前不改原卡片。
   * 仅适用于主实体一物一卡；不把此主实体索引算法直接用于分录/子分录。
   */
  afterConvert(e: AfterConvertEventArgs): void {
    const cards = e.getTargetExtDataEntitySet().FindByEntityKey("fa_card_real");
    const quantities: number[] = [];
    const seenIndices: { [key: string]: boolean } = {};
    let highestIndex = -1;
    let totalCards = 0;

    for (let i = 0; i < cards.length; i++) {
      const card = cards[i];
      this.requireProperty(card.getDataEntity(), "assetamount");
      this.requireProperty(card.getDataEntity(), "sourceentrysplitseq");
      const qty = this.readQuantity(card.getValue("assetamount"));
      totalCards += qty;
      if (totalCards > this.maxCardsPerConvert) {
        throw new Error("拆分后的卡片总数超过本例批量上限，请分批转换");
      }
      quantities.push(qty);
      const index = card.getDataEntityIndex();
      if (!isFinite(index) || index < 0 || Math.floor(index) !== index || index > this.maxDataIndex || seenIndices[String(index)]) {
        throw new Error("目标主卡片数据索引无效或重复");
      }
      seenIndices[String(index)] = true;
      highestIndex = Math.max(highestIndex, index);
    }

    const copiesNeeded = totalCards - cards.length;
    if (copiesNeeded > this.maxDataIndex - highestIndex) {
      throw new Error("新增卡片的数据索引超出 int 范围");
    }
    let nextDataIndex = highestIndex + 1;
    const copies = new ArrayList();
    for (let i = 0; i < cards.length; i++) {
      for (let seq = 2; seq <= quantities[i]; seq++) {
        // 保留原 clone(false, true)：包含非 DB 属性，按 SDK 规则清副本主键。
        const copy = OrmUtils.clone(cards[i].getDataEntity(), false, true) as DynamicObject;
        copy.set("assetamount", 1);
        copy.set("sourceentrysplitseq", seq);
        copies.add(new ExtendedDataEntity(copy, nextDataIndex++, 0));
      }
    }
    for (let i = 0; i < cards.length; i++) {
      cards[i].setValue("assetamount", 1);
      cards[i].setValue("sourceentrysplitseq", 1);
    }
    if (copies.size() > 0) {
      e.getTargetExtDataEntitySet().AddExtendedDataEntities("fa_card_real", copies);
    }
  }

  /** 单件资产只接收精确正整数；拒绝小数、空值、非数值和超出 int 的数量。 */
  private readQuantity(value: unknown): number {
    if (value == null) { throw new Error("资产数量不能为空"); }
    let qty: number;
    try {
      qty = new BigDecimal(String(value)).intValueExact();
    } catch (error) {
      throw new Error("资产数量必须为 int 范围内的正整数");
    }
    if (qty < 1) { throw new Error("资产数量必须大于零"); }
    return qty;
  }

  /** ExtendedDataEntity 可存扩展值；先确认真实字段，避免误把内存扩展值当持久化字段。 */
  private requireProperty(data: DynamicObject, key: string): void {
    if (data.getDynamicObjectType().getProperty(key) == null) {
      throw new Error("目标实体未定义字段：" + key);
    }
  }
}

const plugin = new SplitTargetRowsAfterConvertPlugin();
export { plugin };
```

## 数据包、索引与失败边界

先检查全批数量、真实字段、索引和总张数，再准备所有副本，最后修改原卡数量/拆分序号并追加。后续原卡写入或集合追加仍可能失败，本例不承诺数据库事务、自动回滚或完整恢复；异常后先检查实际状态，不自动重试转换/保存。只校验阶段和副本准备失败不改原卡，来源备注阶段属于更早的独立事件；`afterCreateTarget` 在后续字段赋值前触发，规则可能覆盖 `memo`，必须核对映射，不能只凭此处写入就宣称最终备注已保存。

新增主实体索引从现有最大 `getDataEntityIndex()+1` 起算，并检查重复、负值及 `int` 溢出；不能假定原索引始终为 `0..length-1`。实际 `AddExtendedDataEntities` 追加传入实体，不负责重新编号。数量 1 也统一设置拆分序号 1；相同结果集再次调用会把已有拆分序号统一写为 1，不能提供跨次转换幂等性；平台是否重入需单独核实，序号不是可用的去重凭证。

保留 `OrmUtils.clone(data, false, true)`：按实际 SDK，前者不将克隆限定为数据库属性，后者按克隆规则清副本主键。普通子集合随数据包复制，引用关系与主键处理按目标类型决定；不能理解为仅复制标题字段，也不能把它视为金额或关联量分摊。新建 `ExtendedDataEntity` 不会自动复制原 wrapper 的扩展值 map。

`afterConvert` 已处于目标转换末尾。这里调整数量和拆分序号，其他金额、关联行与反写量不会自动按张数分摊；若目标有这些字段，项目必须在拆分时按真实合同同步处理并验收。没有数量/金额/关联守恒证据时，本例不能直接作为完整财务转换上线。目标保存、下推事务、反写及真实业务幂等不在此片段中实现。

## 来源与验证

- [官方 afterConvert 事件](https://vip.kingdee.com/knowledge/225705003707377152)：一物一卡的 Java 示例、转换末尾事件和目标结果集入口；原例使用 `int` 数量强转，不能把 TS 类型断言当成等价检查。
- Java 来源类：`kd.bos.plugin.sample.bill.billconvert.bizcase.AfterCreateTargetSample`、`AfterConvertSample`。来源读取示例保留，仅在字段与来源行确有值时写备注。
- 实际 7.0 声明与 `ExtendedDataEntitySet/ExtendedDataEntity/OrmUtils/CloneUtils` 消费字节码用于核对索引、属性和复制合同。声明编译、Node 替身及纯 JDK 数值检查不等于 KingScript 转换运行；原生 clone 探针受本地平台依赖缺失阻塞，真实卡片、关系、金额、DB 保存和反写未验。
