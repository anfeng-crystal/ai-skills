# setHeadAndEntryValue - 表头与单据体字段赋值

## 场景

点击按钮后，需要同时给表头字段、单据体字段赋值；如果目标字段在子单据体中，还需要先切换当前单据体行，再对子单据体行赋值。

## Java 来源

- `kd.bos.plugin.sample.dynamicform.pcform.field.bizcase.SetValueSample`

这个 Java 样例的重点不是某个事件，而是 `setValue(fieldKey, value)`、`setValue(fieldKey, value, row)` 和 `setEntryCurrentRowIndex(entryKey, row)` 这组三段式写法。

## 适用入口

- `click(e: $.java.util.EventObject): void`
- 插件基类：`AbstractBillPlugIn`

## KingScript 场景示例

本地 `@cosmic/bos-core` 声明包 `1.0.0` / buildTime `2025-11-12 15:28:03` 将 `addClickListeners` 声明为 `...keys:string[]`，因此传入按钮标识，不把数组作为一个参数。包标识不代表目标部署补丁；示例字段、按钮、父子分录关系和日期桥接须按实际元数据与运行时核对。本轮仅核本地声明，没有编译或平台运行验收。

```typescript
import { AbstractBillPlugIn } from "@cosmic/bos-core/kd/bos/bill";
import { Control } from "@cosmic/bos-core/kd/bos/form/control";

class SetValueScenePlugin extends AbstractBillPlugIn {

  registerListener(e: $.java.util.EventObject): void {
    super.registerListener(e);
    this.addClickListeners("btn_fill_default");
  }

  click(e: $.java.util.EventObject): void {
    super.click(e);

    let control = e.getSource() as Control;
    if (control.getKey() !== "btn_fill_default") {
      return;
    }

    this.fillHeadFields();
    this.fillEntryRow(0);
    this.fillSubEntryRow(0, 0);
    this.getView().updateView();
  }

  private fillHeadFields(): void {
    this.getModel().setValue("remark", "由场景案例自动带出");
    this.getModel().setValue("biztype", "standard");
  }

  private fillEntryRow(row: number): void {
    if (this.getModel().getEntryRowCount("entryentity") <= row) {
      return;
    }

    this.getModel().setValue("qty", 10, row);
    this.getModel().setValue("price", 25, row);
    this.getModel().setValue("amount", 250, row);
  }

  private fillSubEntryRow(entryRow: number, subRow: number): void {
    if (this.getModel().getEntryRowCount("entryentity") <= entryRow) {
      return;
    }

    this.getModel().setEntryCurrentRowIndex("entryentity", entryRow);

    if (this.getModel().getEntryRowCount("subentryentity") <= subRow) {
      return;
    }

    this.getModel().setValue("deliverydate", new Date(), subRow);
    this.getModel().setValue("lastdate", new Date(), subRow);
  }
}

let plugin = new SetValueScenePlugin();
export { plugin };
```

## 映射说明

- Java 样例把赋值拆成表头、单据体、子单据体三个方法；这里保留同样的分层，便于看清不同数据层级的写法。
- 表头赋值直接调用 `setValue(fieldKey, value)`。
- 单据体赋值使用 `setValue(fieldKey, value, row)`。
- 当目标字段位于子单据体时，先用 `setEntryCurrentRowIndex(entryKey, row)` 切换父分录上下文，再对子单据体行调用 `setValue(fieldKey, value, subRow)`。

## 注意事项

- 赋值前最好先判断行是否存在，避免把案例直接复制后在空分录上运行出错。
- 子单据体赋值依赖父分录上下文，漏掉 `setEntryCurrentRowIndex` 时经常会出现“写到错误行”或“写不进去”的问题。
- 如果赋值后界面没有即时刷新，可以补 `this.getView().updateView()` 或只刷新具体控件。
- 这类案例适合回答“怎么写赋值链路”；如果你只想看某个字段事件的触发时机，应该回到事件拆分目录。

延伸核验：[云端 KingScript 与 ISCB 运行时边界](https://chatgpt.com/space/page_e22ab958bea4819195a0e5ffd3b154c2)。
