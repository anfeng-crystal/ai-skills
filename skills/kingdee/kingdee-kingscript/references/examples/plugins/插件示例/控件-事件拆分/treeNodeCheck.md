# treeNodeCheck - 统计完整有效的已选权限

[返回控件监听器案例](../控件.md#treenodechecklistener)

将本页成员并入现有 `AbstractBillPlugIn`，不替换整个插件或已有 `registerListener`。示例控件 `kdec_permission_tree`、计数字段 `kdec_perm_count` 须核对真实元数据。导入合并到原文件顶部：

```typescript
import { AbstractBillPlugIn } from "@cosmic/bos-core/kd/bos/bill";
import { TreeView } from "@cosmic/bos-core/kd/bos/form/control";
import { TreeNodeCheckEvent } from "@cosmic/bos-core/kd/bos/form/control/events";
```

只把下列注册行合并到已有 `registerListener`，保留父调用和其他监听：

```typescript
const tree = this.getView().getControl("kdec_permission_tree") as TreeView;
tree.addTreeNodeCheckListener(this);
```

项目通过 `configurePermissionSnapshotReader` 为每个处理回调的实例显式配置同步读取器；函数属性不保证跨请求自动恢复。读取器接收当前插件和原事件，返回 `readonly unknown[] | null`：数组必须是完整、有效、唯一的权限 ID 集合，`[]` 仅表示已确认没有任何有效选择；状态未知/未同步返回 `null`，不能写成 0。

接入前确认既有选择初始化、未加载节点覆盖、父子级联、目录节点排除、按真实身份去重、事件同步时点，以及取消勾选和事件被取消后的有效状态。单次事件和 `TreeView.getTreeState()` 有声明，不等于完整业务全集；不能只用事件次数、当前节点或增减 1 推算。代码的数组结构检查不验证 ID 的业务有效性与唯一性，这些由已核实的项目读取器保证；同步取得条件尚未满足就返回 `null`。

```typescript
private permissionSnapshotReader:
  ((plugin: AbstractBillPlugIn, evt: TreeNodeCheckEvent) => readonly unknown[] | null) | null = null;

/** 项目提供完整有效选择快照；这是接入入口，不是平台API。 */
configurePermissionSnapshotReader(
  read: (plugin: AbstractBillPlugIn, evt: TreeNodeCheckEvent) => readonly unknown[] | null
): void {
  this.permissionSnapshotReader = read;
}

/** 未配置或快照未知时保留原计数，不将未知状态误写成0。 */
treeNodeCheck(evt: TreeNodeCheckEvent): void {
  const read = this.permissionSnapshotReader;
  if (read == null) {
    this.getView().showTipNotification("尚未配置完整权限选择来源，未更新数量。"); return;
  }
  const ids = read(this, evt);
  if (ids == null || !Array.isArray(ids)) {
    this.getView().showTipNotification("完整有效的权限选择尚未就绪，未更新数量。"); return;
  }
  const count = ids.length;
  this.getModel().setValue("kdec_perm_count", count);
  this.getView().showTipNotification("已选择 " + count + " 项权限");
}
```

需要本次勾选状态时由项目读取 `evt.getChecked()`；它返回本次勾选/取消勾选状态，不是完整集合。`getChecked() == false` 不等于继承的 `isCancel()` 所表示的事件取消；有效快照须结合目标时序确认。原示例未使用的 `nodeId`、`checked` 局部变量已移除，不调用 `isChecked()` 或事件上不存在于已核声明链的 `getCheckedNodeIds()`。

依据本地 `@cosmic/bos-core` 声明包 `1.0.0` / buildTime `2025-11-12 15:28:03`；不是目标部署补丁证明。仅静态核对，未编译、执行模型、初始化 SDK 或验证平台；计数提示不证明权限已持久化或改变授权。

延伸核验：[云端 KingScript 与 ISCB 运行时边界](https://chatgpt.com/space/page_e22ab958bea4819195a0e5ffd3b154c2)。
