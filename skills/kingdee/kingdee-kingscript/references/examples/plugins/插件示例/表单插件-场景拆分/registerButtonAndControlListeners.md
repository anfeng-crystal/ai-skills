# registerButtonAndControlListeners - 注册按钮与控件监听

## 场景

表单初始化后，需要同时监听工具栏按钮、普通按钮、单据体行点击和树节点点击，并在不同入口里做联动处理。

## Java 来源

- `kd.bos.plugin.sample.dynamicform.pcform.form.bizcase.RegisterListenerSample`

这个 Java 样例展示了如何在一个 `registerListener` 里统一拿到多个控件并挂监听器。

## 适用入口

- `registerListener(e: $.java.util.EventObject): void`
- `itemClick(e: ItemClickEvent): void`
- `click(e: $.java.util.EventObject): void`
- `entryRowClick(e: $.kd.bos.form.control.events.RowClickEvent): void`
- `treeNodeClick(e: $.kd.bos.form.control.events.TreeNodeEvent): void`
- 插件基类：`AbstractFormPlugin`

## 监听注册工厂示例

本地 `@cosmic/bos-core` 声明包 `1.0.0` / buildTime `2025-11-12 15:28:03` 支持下列类型和监听方法；这不证明与目标 Java SDK、KingScript 引擎为同一发布包，也不等于已编译或可直接挂载。项目核对实际声明、控件/字段及 `refresh` 操作后，用工厂创建实例，再按目标引擎的插件导出/注册方式接入。

`resolveNodeText(plugin, nodeId: unknown): string | null` 必须从项目真实树数据源或同页已维护的节点映射取得名称，未知节点返回 `null`。不要猜 `TreeNodeEvent.getNodeText()` 或以展开结果充当点击文本，也不要把 ID 显示成名称。ID 原样传入映射与模型，不经 JavaScript Number 或任意 String 转换；目标 `currentnodeid` 字段须能接收真实节点 ID 类型，需转换时先核项目明确的无损映射合同。名称缺失时提示并停止本次字段联动，不宣称切换成功。

```typescript
import { AbstractFormPlugin } from "@cosmic/bos-core/kd/bos/form/plugin";
import { Button, Control, Toolbar, EntryGrid, TreeView } from "@cosmic/bos-core/kd/bos/form/control";
import { ItemClickEvent, RowClickEvent, TreeNodeEvent } from "@cosmic/bos-core/kd/bos/form/control/events";

/** 项目提供真实节点名称来源；监听与业务字段仅在当前表单元数据核实后使用。 */
function createRegisterListenersPlugin(
  resolveNodeText: (plugin: AbstractFormPlugin, nodeId: unknown) => string | null
): AbstractFormPlugin {
  return new class extends AbstractFormPlugin {

  registerListener(e: $.java.util.EventObject): void {
    super.registerListener(e);

    let toolbar = this.getView().getControl("tbmain") as Toolbar;
    toolbar.addItemClickListener(this);

    let button = this.getView().getControl("buttonap1") as Button;
    button.addClickListener(this);

    let entryGrid = this.getView().getControl("entryentity") as EntryGrid;
    entryGrid.addRowClickListener(this);

    let treeView = this.getView().getControl("treeviewap1") as TreeView;
    treeView.addTreeNodeClickListener(this);
  }

  itemClick(e: ItemClickEvent): void {
    super.itemClick(e);

    if (e.getItemKey() === "baritem_refresh") {
      this.getView().showTipNotification("工具栏刷新已触发。");
      this.getView().invokeOperation("refresh");
    }
  }

  click(e: $.java.util.EventObject): void {
    super.click(e);

    let control = e.getSource() as Control;
    if (control.getKey() === "buttonap1") {
      let billNo = this.getModel().getValue("billno") as string;
      this.getView().showMessage("当前单据编号：" + billNo);
    }
  }

  entryRowClick(e: RowClickEvent): void {
    let row = e.getRow();
    let materialName = this.getModel().getValue("materialname", row) as string;

    if (materialName != null && materialName !== "") {
      this.getView().showTipNotification("当前行物料：" + materialName);
    }
  }

  /** 先解析真实名称；缺少映射时不写字段、不用ID冒充名称。 */
  treeNodeClick(e: TreeNodeEvent): void {
    const nodeId: unknown = e.getNodeId();
    if (nodeId == null) {
      this.getView().showTipNotification("未取得节点ID，未执行节点联动。"); return;
    }
    const nodeText = resolveNodeText(this, nodeId);
    if (typeof nodeText !== "string" || nodeText.trim() === "") {
      this.getView().showTipNotification("未找到该节点的名称，请核对树数据来源；未执行节点联动。"); return;
    }
    this.getModel().setValue("currentnodeid", nodeId);
    this.getView().showTipNotification("所选节点：" + nodeText);
  }
  }();
}
export { createRegisterListenersPlugin };
```

## 映射说明

- Java 样例通过 `getView().getControl(key)` 拿到 `Toolbar`、`Button`、`EntryGrid`、`TreeView` 后再分别挂监听，Kingscript 里同样适合按控件类型拆开注册。
- 工具栏按钮点击优先进入 `itemClick`，普通按钮点击进入 `click`，单据体和树控件则进入各自的事件回调，这种“一个入口负责一类控件”的分工和 Java 一致。
- 对于单据体和树控件，案例保留了“注册在 `registerListener`，处理在专用回调”的写法，便于后续继续扩展更多监听器。

## 注意事项

- `registerListener` 里要先 `super.registerListener(e)`，再开始挂自定义监听。
- 监听注册前核对真实元数据。示例中的 `tbmain` 是工具栏控件 key，`baritem_refresh` 是其子项 itemKey；前者用于取得控件并注册监听，后者用于 `getItemKey()` 分流，不可互换。普通按钮、分录、树控件、`billno`/`materialname`/`currentnodeid` 字段及 `refresh` 操作也仅是需核实的示例标识。
- 一个插件里可以同时实现多种监听器，但建议每个回调只处理自己负责的控件类型。
- 单据体和树控件的事件回调更适合做联动展示；涉及大量数据处理时，建议抽到独立方法里，避免回调方法过长。

延伸核验：[云端 KingScript 与 ISCB 运行时边界](https://chatgpt.com/space/page_e22ab958bea4819195a0e5ffd3b154c2)。
