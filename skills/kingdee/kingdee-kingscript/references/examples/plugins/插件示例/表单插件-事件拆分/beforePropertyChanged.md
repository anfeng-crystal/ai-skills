# beforePropertyChanged - 字段值改变前事件

来源：从 [表单插件.md](../表单插件.md) 拆出。

## 基本信息

| 属性 | 说明 |
|------|------|
| 所属接口 | IDataModelChangeListener |
| 触发时机 | 字段值被修改之前触发，用于读取待变更值及前置通知或联动 |
| 方法签名 | `beforePropertyChanged(e: PropertyChangedArgs): void` |

## 说明

在字段值实际写入数据模型之前触发。字段标识来自 `e.getProperty().getName()`，待变更的新值、旧值和行号来自 `e.getChangeSet()` 中各条 `ChangeData`。该参数没有 `setCancel`；本事件的提示或 `return` 不会取消后续赋值，也不能据此承诺界面恢复旧值。

## 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| e | PropertyChangedArgs | 事件参数对象 |
| e.getProperty().getName() | string | 本次事件变更的字段标识 |
| e.getChangeSet() | ChangeData[] | 当前字段的变更集合；批量变更时逐条处理 |
| change.getNewValue() | any | 该条变更即将设置的新值 |
| change.getOldValue() | any | 该条变更的旧值 |
| change.getRowIndex() | number | 该条变更的行索引；单据头字段为 0，单据体从 0 开始 |
| change.getDataEntity() | DynamicObject | 该条变更所在的数据包 |

## 业务场景

在单价字段即将改成负数时提醒用户核对。本示例仅提示，不构成“禁止负数”或“审核后禁止修改”的硬约束；硬约束应选择目标版本已确认支持的校验或编辑控制路径。

## 完整示例代码

```typescript
import { AbstractBillPlugIn } from "@cosmic/bos-core/kd/bos/bill";
import { PropertyChangedArgs } from "@cosmic/bos-core/kd/bos/entity/datamodel/events";
import { BigDecimal } from "@cosmic/bos-script/java/math";

/**
 * 单价字段变更前提示；依赖目标声明及 price 的 Decimal 元数据。
 * 仅展示页面提示，不取消赋值、不保存数据；不替代业务校验。
 */
class PmPurorderPriceHintPlugin extends AbstractBillPlugIn {

  /**
   * 读取本次 price 变更的各行新值；空值不提示，其他字段直接返回。
   * 事件参数和变化集由数据模型提供，return 仅结束当前回调。
   */
  beforePropertyChanged(e: PropertyChangedArgs): void {
    super.beforePropertyChanged(e);

    const fieldKey = e.getProperty().getName();
    if (fieldKey !== "price") {
      return;
    }

    const messages: string[] = [];
    for (const change of e.getChangeSet()) {
      const rowIndex = change.getRowIndex();
      const newPrice = change.getNewValue() as BigDecimal;
      // 遍历全部变更行，汇总提示；空值不参与负数比较。
      if (newPrice != null && newPrice.compareTo(BigDecimal.ZERO) < 0) {
        messages.push("第 " + (rowIndex + 1) + " 行单价即将改为负数，请核对");
      }
    }

    if (messages.length > 0) {
      this.getView().showTipNotification(messages.join("；"));
    }
  }
}

let plugin = new PmPurorderPriceHintPlugin();
export { plugin };
```

## 注意事项

- `price` 在示例中是单据体 Decimal 字段，复用前核对实际字段标识与类型；行索引从 0 开始，界面提示的序号才加 1。
- `PropertyChangedArgs` 没有直接获取新旧值、行号或取消赋值的方法。通过 `ChangeData` 读取新旧值和行；不将其他事件的 `setCancel` 套入本事件。
- 逐条处理 `getChangeSet()`，不要只处理第一条；需要比较修改前后值时读取同一条 `change.getOldValue()` / `change.getNewValue()`。
- 初始化阶段不触发本事件，包括在 `afterCreateNewData` 中改值；初始化逻辑须按对应生命周期处理。
- 插件类不能定义类属性，所有变量应在方法内部声明为局部变量；保留 `super.beforePropertyChanged(e)` 调用。

依据：[官方 beforePropertyChanged 事件](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=228912833529089024&productLineId=29)（2026-07-31 11:59 更新，正文未标完整版本范围）。本地 `@cosmic/bos-core` 声明包 `1.0.0`（buildTime `2025-11-12 15:28:03`）与 `7.0` 标记 JAR 均确认上述参数与取值 API，且未提供取消方法；声明包号和 JAR 标签不等于产品补丁号，也不证明所有目标版本或 KingScript 引擎兼容。
