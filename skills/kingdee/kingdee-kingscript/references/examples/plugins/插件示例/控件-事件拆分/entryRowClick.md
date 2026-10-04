# entryRowClick - 事件行与检验按钮

**签名**：`entryRowClick(evt: RowClickEvent): void`
**触发控件**：AbstractGrid
**场景**：点击单据体行时，根据当前行的物料类型控制"检验"按钮的启用状态。

将这些方法合并到现有 `AbstractBillPlugIn`，保留原插件的其他监听注册；这是方法片段，不能单独作为插件挂载。组合入口见[控件监听器汇总](../控件.md#rowclickeventlistener)。

```typescript
  registerListener(e: $.java.util.EventObject): void {
  let entryGrid = this.getView().getControl("kdec_entrygrid") as $.kd.bos.form.control.EntryGrid;
  entryGrid.addRowClickListener(this);
}

entryRowClick(evt: $.kd.bos.form.control.events.RowClickEvent): void {
  let row = evt.getRow();
  let materialType = this.getModel().getValue("kdec_material_type", row) as string;

  // 只有原材料类型才允许点击"检验"按钮
  if (materialType === "raw") {
    this.getView().setEnable(true, "kdec_btn_inspect");
  } else {
    this.getView().setEnable(false, "kdec_btn_inspect");
  }
}
```

本片段按本地 `@cosmic/bos-core` `1.0.0` / buildTime `2025-11-12 15:28:03` 的声明修订；仅说明行点击合同，不覆盖所有行切换路径。控件实际为 `EntryGrid`、字段类型、`raw` 含义与按钮权限仍须按目标元数据核实，类型断言不代替这些核验。本轮仅静态核对，未编译或执行平台。

延伸核验：[云端 KingScript 与 ISCB 运行时边界](https://chatgpt.com/space/page_e22ab958bea4819195a0e5ffd3b154c2)。
