# buildTreeViewAndLazyLoadNodes - 构建树并按需懒加载节点

## 场景

页面先展示可勾选、可拖拽的根节点，展开时按父节点标识生成两个孩子；点击、双击、勾选和拖拽请求给出反馈。节点是演示数据，真实组织查询见[TreeNodeQueryListener](../控件.md#treenodequerylistener)。

## Java 来源与节点协议

参考 `kd.bos.plugin.sample.dynamicform.pcform.control.bizcase.TreeViewSample` 与[官方树形控件插件](https://vip.kingdee.com/knowledge/230366156979367424)。采用目标本机7.0声明的 `TreeView/TreeNode/TreeNodeEvent`：`TreeNode(parentId,id,text)` 序列化为 `parentid`，显式空 `children` 标记等待懒加载；通过控件 `addNodes` 返回孩子，不向事件写集合。

节点标识须唯一且父键已存在。真实PC追加消费者按ID跳过重复，未知父键不追加；重复绑定固定根不会更新既有节点状态，因此本例初始化不等于完整树刷新。省略/null `children` 与空列表不同，前端从该字段重算 `isParent`，单设 `leaf` 不能代替。

## 适用入口

`AbstractFormPlugin` 的 `registerListener`、`beforeBindData`，以及 `queryTreeNodeChildren/treeNodeClick/treeNodeDoubleClick/treeNodeCheck/treeNodeDragged`。仅PC独立TreeView；控件标识须为 `treeviewap1`。

## 完整 Kingscript 示例

```typescript
/**
 * PC TreeView 合成节点演示：初始化根节点，展开时追加两个孩子，响应节点交互。
 * 使用目标声明中的 TreeView、TreeNode 与树事件；只展示控件状态，不保存业务层级。
 */
import { AbstractFormPlugin } from "@cosmic/bos-core/kd/bos/form/plugin";
import { TreeView } from "@cosmic/bos-core/kd/bos/form/control";
import { TreeNode } from "@cosmic/bos-core/kd/bos/entity/tree";
import { TreeNodeCheckEvent, TreeNodeDragEvent, TreeNodeEvent } from "@cosmic/bos-core/kd/bos/form/control/events";
import { ArrayList } from "@cosmic/bos-script/java/util";

/** 为 treeviewap1 接线；节点标识由本示例的父子规则生成。 */
class BuildTreeViewAndLazyLoadNodesPlugin extends AbstractFormPlugin {
  /** 注册懒加载、点击、勾选和拖拽监听。 */
  registerListener(e: $.java.util.EventObject): void {
    super.registerListener(e);
    const tree = this.getView().getControl("treeviewap1") as TreeView;
    tree.addTreeNodeQueryListener(this);
    tree.addTreeNodeClickListener(this);
    tree.addTreeNodeCheckListener(this);
    tree.addTreeNodeDragListener(this);
  }

  /** 设置交互属性并追加固定根节点；不是业务树刷新或状态恢复。 */
  beforeBindData(e: $.java.util.EventObject): void {
    super.beforeBindData(e);
    const tree = this.getView().getControl("treeviewap1") as TreeView;
    tree.setMulti(true);
    tree.setRootVisible(true);
    tree.setDraggable(true);
    tree.setDroppable(true);
    const rootNodes = new ArrayList();
    rootNodes.add(this.createNode("node1", ""));
    tree.addNodes(rootNodes);
    tree.expand("node1");
  }

  /** 从展开事件取父节点标识，将孩子经控件 addNodes 发送给客户端。 */
  queryTreeNodeChildren(e: TreeNodeEvent): void {
    if ((e.getSource() as TreeView).getKey() !== "treeviewap1") return;
    const value = e.getNodeId();
    if (value == null || String(value) === "") return;
    const parentId = String(value);
    const children = new ArrayList();
    children.add(this.createNode(parentId + ".1", parentId));
    children.add(this.createNode(parentId + ".2", parentId));
    (this.getView().getControl("treeviewap1") as TreeView).addNodes(children);
  }

  /** 点击反馈按本示例共享命名规则显示名称，不从事件猜取节点名称。 */
  treeNodeClick(e: TreeNodeEvent): void {
    if ((e.getSource() as TreeView).getKey() !== "treeviewap1") return;
    const nodeId = e.getNodeId();
    if (nodeId != null) this.getView().showTipNotification("当前节点：" + this.displayText(String(nodeId)));
  }

  /** 双击只给出反馈；业务打开页面由调用方另行实现。 */
  treeNodeDoubleClick(e: TreeNodeEvent): void {
    if ((e.getSource() as TreeView).getKey() !== "treeviewap1") return;
    const nodeId = e.getNodeId();
    if (nodeId != null) this.getView().showMessage("双击节点：" + String(nodeId));
  }

  /** 从 TreeState 读取当前全部勾选标识，含取消最后一个勾选的空状态。 */
  treeNodeCheck(e: TreeNodeCheckEvent): void {
    if ((e.getSource() as TreeView).getKey() !== "treeviewap1") return;
    const tree = this.getView().getControl("treeviewap1") as TreeView;
    const checkedNodeIds = tree.getTreeState().getCheckedNodeIds();
    if (checkedNodeIds == null || checkedNodeIds.size() === 0) {
      this.getView().showTipNotification("当前没有勾选任何节点。");
      return;
    }
    const ids: string[] = [];
    for (let i = 0; i < checkedNodeIds.size(); i++) ids.push(String(checkedNodeIds.get(i)));
    this.getView().showTipNotification("已勾选：" + ids.join(", "));
  }

  /** 反馈拖拽请求的节点及新父节点；本例不更新层级，不代表移动或保存成功。 */
  treeNodeDragged(e: TreeNodeDragEvent): void {
    if ((e.getSource() as TreeView).getKey() !== "treeviewap1") return;
    const nodeId = e.getNodeId();
    const toParentId = e.getToParentId();
    if (nodeId == null || toParentId == null) return;
    this.getView().showTipNotification("拖拽请求：节点 " + String(nodeId) + "，目标父节点 " + String(toParentId));
  }

  /** 构造真实节点；显式空 children 表示下级尚未加载，允许再次展开请求。 */
  private createNode(nodeId: string, parentId: string): TreeNode {
    const node = new TreeNode(parentId, nodeId, this.displayText(nodeId));
    node.setChildren(new ArrayList());
    return node;
  }
  /** 仅用于本例生成的节点；真实组织树应使用已查询的业务名称。 */
  private displayText(nodeId: string): string {
    return nodeId === "node1" ? "业务对象" : "节点 " + nodeId;
  }
}
const plugin = new BuildTreeViewAndLazyLoadNodesPlugin();
export { plugin };
```

## 交互与能力边界

- 保留多选、根可见、拖拽、放置、初始展开，以及每次生成两个孩子的演示。名称来自本例统一生成规则，事件没有 `getNodeText()`，不能把节点ID当作平台提供的名称。
- 勾选反馈从 `TreeState.getCheckedNodeIds()` 读取当前全部状态，取消最后一项时显示空状态；双击仅提示，不冒充已经打开业务页面。
- 官方说明多选模式不触发单击；本机7.0所见PC点击消费者未以 `isMulti` 阻断回调。保留单击/双击/勾选接线，但不承诺所有部署版本的多选单击行为；由实际页面确认。
- 拖拽事件使用 `getNodeId()/getFromParentId()/getToParentId()`。本例保留请求反馈，**未实现移动节点或保存层级**。官方Java样例的删除再添加并未完整保留子树；业务层级调整需另核原节点状态、权限、循环、顺序和操作结果，不能看到事件就宣称调整成功。
- 每个演示孩子继续标记可懒加载；若真实查询没有孩子，本例的组织查询章节保留再次查询，不自动永久叶化。需完整节点副本后才能安全更新为叶子。
- 本机SDK、序列化和前端载荷验证不代表真实KingScript引擎、平台页面或业务保存验收；不推断部署补丁版本。
