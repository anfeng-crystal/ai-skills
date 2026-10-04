# treeNodeDoubleClick - 选择结果返回

**签名**：`treeNodeDoubleClick(evt: TreeNodeEvent): void`
**场景**：双击树节点返回选中 ID 与真实名称，再关闭选择页（F7 选择场景）。

将本段成员并入原 `AbstractBillPlugIn`，保留[汇总页的 treeNodeClick 和既有 TreeView 注册](../控件.md#treenodeclick)。`TreeView.addTreeNodeClickListener` 同时对应单击/双击监听，不改成 TreeMenu 的注册接口。实际控件须由目标元数据确认是 TreeView。

名称解析器通过项目配置入口显式传入，合同与[TreeMenu 片段](treeMenuClick.md)一致：从真实树数据源按原 ID 解析名称，为每个处理事件的实例装配，随树构建/懒加载/刷新同步，未知返回 `null`。F7 选择映射与部门过滤映射是两个业务合同，使用独立属性和配置入口，不能在同页组合时覆盖对方。每个实际实例/回调生命周期均须保证配置可用，不能假设函数属性设置一次便跨请求自动恢复。导入合并到原文件顶部：

```typescript
import { AbstractBillPlugIn } from "@cosmic/bos-core/kd/bos/bill";
import { TreeNodeEvent } from "@cosmic/bos-core/kd/bos/form/control/events";
import { HashMap } from "@cosmic/bos-script/java/util";
```

```typescript
private selectionNodeTextResolver:
  ((plugin: AbstractBillPlugIn, nodeId: unknown) => string | null) | null = null;

/** 项目显式提供真实树节点名称来源；独立使用本段时保留此配置入口。 */
configureSelectionNodeTextResolver(
  resolveNodeText: (plugin: AbstractBillPlugIn, nodeId: unknown) => string | null
): void {
  this.selectionNodeTextResolver = resolveNodeText;
}

treeNodeDoubleClick(evt: TreeNodeEvent): void {
  const nodeId: unknown = evt.getNodeId();
  if (nodeId == null) {
    this.getView().showTipNotification("未取得节点ID，未返回选择结果。"); return;
  }
  if (this.selectionNodeTextResolver == null) {
    this.getView().showTipNotification("尚未配置节点名称来源，未返回选择结果。"); return;
  }
  const nodeText = this.selectionNodeTextResolver(this, nodeId);
  if (typeof nodeText !== "string" || nodeText.trim() === "") {
    this.getView().showTipNotification("未找到节点名称，请核对树数据来源；未返回选择结果。"); return;
  }
  const returnData = new HashMap();
  returnData.put("selectedId", nodeId);
  returnData.put("selectedName", nodeText);
  this.getView().returnDataToParent(returnData);
  this.getView().close();
}
```

保留 Java `HashMap` 的 `selectedId`/`selectedName` 协议，ID 原样传回，名称必须来自真实映射；父页的读取方式、字段类型和消费协议仍需项目确认。名称缺失时既不回传也不关闭。`returnDataToParent` 调用正常返回后才调用 `close`；这不证明父页已经写入或保存成功，也不吞掉回传异常再关闭。

本地 `bos-core` 声明包 `1.0.0` / buildTime `2025-11-12 15:28:03` 与 `bos-script` 的 Java Map 声明/静态导出仅是本地合同证据，不证明部署为同一发布包。本段不以 `getExpandedNode` 作为点击名称，不猜未核 getter；未执行引擎、父子页回调或真实业务验收。

延伸核验：[云端 KingScript 与 ISCB 运行时边界](https://chatgpt.com/space/page_e22ab958bea4819195a0e5ffd3b154c2)。
