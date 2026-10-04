# 左树右表单据列表插件

## TL;DR
- 适用：左树右表列表插件，处理树初始化、节点选择和树表联动。
- 先抓：`AbstractTreeListPlugin` 和树模型事件，先分清树模板类型。
- 跳转：标准列表无树场景先读 `plugin-list.md`；Ext 通用能力回 `adv/plugin-base.md`。
- 继续读全文：当你要改树筛选、节点点击、列表联动或特殊扩展点时。

## 概述
左树右表插件在标准列表上增加了“分组树 + 右侧列表”的协同能力，适用于组织树、分类树、业务分组树筛选场景。

> **适用边界**
> ✅ 本文档是原生兜底：左树右表有两个模板（TreeListPluginTemplate/StandardTreeListPluginTemplate），事件签名参考本文档。
> ❌ 封装层 Ext 基类的通用部分优先读 `references/adv/plugin-base.md`。

## 核心基类
- 基类：`kd.bos.list.plugin.AbstractTreeListPlugin`
- 继承关系：`AbstractTreeListPlugin extends AbstractListPlugin implements ITreeListPlugin, SearchEnterListener`

## 核心事件

- `initializeTree(...)`：树模型初始化时触发。
- `initTreeToolbar(...)`：树工具栏初始化后触发。
- `treeNodeClick(...)`：节点点击后触发。
- `buildTreeListFilter(...)`：基于当前节点构建右侧列表过滤条件。
- `refreshNode(...)`：树节点刷新时触发。
- `treeToolbarClick(...)`：树工具栏按钮点击时触发。
- `search(...)`：树搜索回车时触发。
- `beforeShowBill(...)`：打开右侧详情前触发。

## 插件内上下文方法

以下属于树列表插件的上下文访问能力，不建议继续按“事件”理解：

- `getTreeListView()`：获取树列表视图模型。
- `getTreeModel()`：获取树模型。
- `getView()` / `getModel()`：访问页面视图和数据模型。

```java
import kd.bos.entity.datamodel.ITreeModel;
import kd.bos.list.ITreeListView;

ITreeListView treeListView = this.getTreeListView();
ITreeModel treeModel = this.getTreeModel();
Object currentNodeId = treeModel.getCurrentNodeId();
```

当前节点由 `ITreeModel` 提供；`ITreeListView` 用于访问树模型、树控件及刷新能力。`setCurrentNodeId(...)` 只设置模型状态，不会同步前端焦点，需另用树控件的焦点 API。参见官方帮助[视图模型](https://vip.kingdee.com/knowledge/225179627017052160?productLineId=29&isKnowledge=2&lang=zh-CN)与[数据模型](https://vip.kingdee.com/knowledge/225181724320046848?productLineId=29&isKnowledge=2&lang=zh-CN)。

## 其他扩展点

- `setTreeListView(...)`：树列表视图模型注入阶段，偏框架上下文准备，不建议与业务事件并列。
- `nodeClickFilter()`：返回非空条件时，基类会将其加入右表过滤并取消系统分组过滤；只需追加条件时，在 `buildTreeListFilter(...)` 中调用 `e.addQFilter(...)`，不取消系统过滤。
- `setCustomerParam()`：树列表自定义参数构建扩展。
- `expendTreeNode(...)`：有的文档或版本中会出现，但官方说明更推荐统一在 `refreshNode(...)` 处理中做懒加载。

## 示例代码

示例代码统一维护在模板文件中，直接参考：

- [TreeListPluginTemplate.java](../../../assets/TreeListPluginTemplate.java)
- [StandardTreeListPluginTemplate.java](../../../assets/StandardTreeListPluginTemplate.java)

## 实践建议

1. 树节点驱动右表过滤优先放在 `buildTreeListFilter(...)`，当前点击节点用 `e.getNodeId()`。保留系统分组过滤时只追加条件；`e.setCancel(true)` 会略过系统内置分组过滤，只在插件完整提供替代条件时使用。模板中的占位条件需替换后启用。
2. 需要树模型时通过 `getTreeModel()` 访问，不要把它当成事件。
3. 懒加载场景优先统一放在 `refreshNode(...)` 处理。
4. 打开详情页前如需透传来源信息，可放在 `beforeShowBill(...)`。

## 常见坑位

- 把 `getTreeListView()`、`getTreeModel()` 这类上下文方法写进事件总览。
- 在 `treeNodeClick(...)` 里直接写大量查询逻辑，导致点击卡顿。
- 节点懒加载和刷新逻辑分散在多个事件里，后续难维护。
- 只在 `initializeTree(...)` 加节点，没有同步处理 `refreshNode(...)`。
