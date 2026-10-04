# treeNodeDragged - 更新组织上级并检查保存结果

**签名**：`treeNodeDragged(evt: TreeNodeDragEvent): void`
**触发控件**：TreeView
**场景**：拖拽组织节点后，更新被拖动组织的上级并反馈保存结果。

这是合并到现有 `AbstractBillPlugIn` 的类成员片段。合并导入与监听注册，保留其他注册和事件方法。返回[控件汇总页](../控件.md#treenodedragged)。

适用前提：项目已确认 `kdec_org_tree` 的节点 ID 与 `bos_org` 主键一致，并确认 `parent` 字段接受目的父节点的原始 ID；通用 `DynamicObject.set(string, any)` 不能证明该字段合同。若字段要求基础资料对象，应按真实元数据改为该对象后再接入本段。沿用目标工程已有权限、组织业务规则和保存操作校验，不绕过它们。

`getNodeId()` 是被拖动节点，`getFromParentId()` 是来源父节点，`getToParentId()` 是目的父节点。目的父节点不能解释成鼠标悬停/投放节点。本段保留非空限制，不推断空值是根节点，不实现没有合同依据的同级排序或 before/after/inside 放置规则；平台事件时点及失败后树状态恢复需由项目验证。

将导入合并到文件顶部：

```typescript
import { BusinessDataServiceHelper } from "@cosmic/bos-core/kd/bos/servicehelper";
import { SaveServiceHelper } from "@cosmic/bos-core/kd/bos/servicehelper/operation";
import { OperateOption } from "@cosmic/bos-core/kd/bos/dataentity";
```

将以下成员合并到原插件类：

```typescript
registerListener(e: $.java.util.EventObject): void {
  super.registerListener(e);
  const tree = this.getView().getControl("kdec_org_tree") as $.kd.bos.form.control.TreeView;
  tree.addTreeNodeDragListener(this);
  // 合并原插件其他控件的注册，不以此片段覆盖它们。
}

treeNodeDragged(evt: $.kd.bos.form.control.events.TreeNodeDragEvent): void {
  const nodeId = evt.getNodeId();
  const toParentId = evt.getToParentId();
  if (nodeId == null || toParentId == null) {
    this.getView().showTipNotification("节点信息不完整，未执行组织层级保存");
    return;
  }

  const orgObj = BusinessDataServiceHelper.loadSingle(nodeId, "bos_org");
  if (orgObj == null) {
    this.getView().showTipNotification("未找到组织，未执行层级保存");
    return;
  }
  // 仅在已确认 parent 字段接受目的父节点原始 ID 的项目中使用。
  orgObj.set("parent", toParentId);
  const result = SaveServiceHelper.saveOperate("bos_org", [orgObj], OperateOption.create());
  if (result != null && result.isSuccess()) {
    this.getView().showSuccessNotification("组织层级已调整");
  } else {
    this.getView().showTipNotification("组织层级保存未成功，请查看操作结果");
    // 将 result 接入目标工程已确认的操作结果展示；本段不猜测展示 API。
  }
}
```

`saveOperate` 是保存操作调用，不能当成仅修改页面模型。非空且 `isSuccess()` 为真才提示成功；异常自然向上传递，不吞错后报成功。失败分支没有完成平台树的回滚或刷新，须结合真实回调时序实现；重试前核对实际组织数据。

本地 `@cosmic/bos-core` 包 `1.0.0`、构建时间 `2025-11-12 15:28:03` 的声明支持上述事件 getter 和保存结果判断；这不是目标部署补丁证明。本例仅作静态合同修正，未编译、执行保存或验证平台行为。详细依据见[云端运行时边界](https://chatgpt.com/space/page_e22ab958bea4819195a0e5ffd3b154c2)。
