# treeMenuClick - 部门树过滤与名称提示

## 回调合同

**签名**：`treeMenuClick(evt: TreeNodeEvent): void`
**触发控件**：TreeMenu 树形菜单
**场景**：点击左侧部门树节点，按真实部门节点过滤员工列表并提示部门名称。

这是合并到现有 `AbstractBillPlugIn` 的方法片段，不是替换整个插件。合并所需导入和监听注册；保留其他注册与[汇总页既有的 treeMenuDoubleClick 部门详情能力](../控件.md#treemenudoubleclick)。本地 `TreeMenuClickListener` 的单击、双击方法均为必需，不能删去双击方法来拼出单方法插件。

`configureDeptNodeTextResolver` 是本例的项目配置入口，不是 SDK API。项目须从真实树数据源/节点映射提供 `resolveNodeText(plugin, nodeId: unknown): string | null`，为每个实际处理事件的插件实例完成装配；不能假设上次请求实例上的函数属性会自动恢复。树构建、懒加载、刷新后映射须同步；未知名称返回 `null`，不拿 ID 或展开结果冒充名称。`kdec_dept_tree`、`kdec_filter_dept_id` 和 `refresh` 需核对目标元数据；节点 ID 必须确实是过滤字段接受的部门标识，虚拟节点等不直接套用本段。ID 原样传递，不经 Number/任意 String 转换。

将导入合并到文件顶部：

```typescript
import { AbstractBillPlugIn } from "@cosmic/bos-core/kd/bos/bill";
import { TreeMenu } from "@cosmic/bos-core/kd/bos/form/control";
import { TreeNodeEvent } from "@cosmic/bos-core/kd/bos/form/control/events";
```

将以下成员合并到原插件类。部门解析器与[F7 选择解析器](treeNodeDoubleClick.md)独立命名、分别装配，不能互相覆盖；每个实际实例/回调生命周期均须保证项目配置可用：

```typescript
private deptNodeTextResolver:
  ((plugin: AbstractBillPlugIn, nodeId: unknown) => string | null) | null = null;

/** 由项目显式传入真实名称解析器；它不是平台节点getter。 */
configureDeptNodeTextResolver(
  resolveNodeText: (plugin: AbstractBillPlugIn, nodeId: unknown) => string | null
): void {
  this.deptNodeTextResolver = resolveNodeText;
}

registerListener(e: $.java.util.EventObject): void {
  super.registerListener(e);
  const treeMenu = this.getView().getControl("kdec_dept_tree") as TreeMenu;
  treeMenu.addTreeMenuClickListener(this);
  // 合并原插件其他控件的注册，不以此片段覆盖它们。
}

treeMenuClick(evt: TreeNodeEvent): void {
  const nodeId: unknown = evt.getNodeId();
  if (nodeId == null) {
    this.getView().showTipNotification("未取得部门节点ID，未执行过滤。"); return;
  }
  if (this.deptNodeTextResolver == null) {
    this.getView().showTipNotification("尚未配置部门节点名称来源，未执行过滤。"); return;
  }
  const nodeText = this.deptNodeTextResolver(this, nodeId);
  if (typeof nodeText !== "string" || nodeText.trim() === "") {
    this.getView().showTipNotification("未找到部门名称，请核对树数据来源；未执行过滤。"); return;
  }
  this.getModel().setValue("kdec_filter_dept_id", nodeId);
  this.getView().invokeOperation("refresh");
  this.getView().showTipNotification("所选部门：" + nodeText);
}
```

本地 `@cosmic/bos-core` 包 `1.0.0` / buildTime `2025-11-12 15:28:03` 支持上述控件/事件导出及监听合同。`TreeNodeEvent` 自身声明未列 `getNodeText`；外部父类和部署包装未核，不泛化所有版本。此片段未做引擎或业务验收，提示只描述所选部门，不证明刷新查询或保存成功。

延伸核验：[云端 KingScript 与 ISCB 运行时边界](https://chatgpt.com/space/page_e22ab958bea4819195a0e5ffd3b154c2)。
