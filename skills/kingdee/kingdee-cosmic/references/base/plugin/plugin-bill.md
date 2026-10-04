# 单据界面插件

详细知识、官方来源与验证边界：[云端专题](https://chatgpt.com/space/page_9aa888dff7848191b4386011cc427738)。


## TL;DR
- 适用：单据界面插件的原生兜底，封装层没覆盖到的单据事件时再读本页。
- 先抓：`AbstractBillPlugIn`、额外监听器和单据特有事件时机。
- 跳转：若 `AbstractBillPlugInExt` 足够，优先回到 `adv/plugin-base.md`。
- 继续读全文：当你要确认工具栏、F7、操作后回调或单据关闭等具体事件时。

## 概述
单据界面插件继承动态表单插件能力，并增加单据特有事件，适合处理加载后初始化与单据交互控制。

> **适用边界**
> ✅ 本文档是原生兜底：当 `plugin-base.md`(封装层) 未覆盖你需要的单据事件时使用。
> ❌ 如果封装层 `AbstractBillPlugInExt` 已满足需求，优先读 `references/adv/plugin-base.md`。

- 适用场景：单据加载初始化、字段联动、操作前后 UI 协同

术语说明：文档中的 `F7` 指基础资料、引用数据等选择控件弹窗，不是键盘按键事件。

## 核心基类


- 基类：`kd.bos.bill.AbstractBillPlugIn`
- 继承关系：`AbstractBillPlugIn extends AbstractFormPlugin implements IBillPlugin`

## 额外监听器

- `BeforeF7SelectListener`：F7（基础资料/引用数据选择控件）选择前拦截
- `ItemClickListener`：菜单/按钮点击监听
- `ClickListener`：控件通用点击监听
- `TreeNodeClickListener`：树节点点击监听

## 核心事件

- `afterLoadData(EventObject e)`：// 已有单据数据包加载完成后触发，适合按已存数据调整界面
- `afterCreateNewData(EventObject e)`：// 新数据包创建并填好默认值后触发，适合加工新增默认值和默认分录
- `beforeDoOperation(BeforeDoOperationEventArgs e)`：// 操作执行前触发，适合做前置校验/参数整理
- `afterDoOperation(AfterDoOperationEventArgs e)`：// 操作执行后触发；成功提示先检查操作结果
- `propertyChanged(PropertyChangedArgs e)`：// 字段值变更后触发，适合做联动赋值

说明：单据插件同时支持动态表单全套事件（生命周期与交互事件与 `plugin-form.md` 一致）。

上列参数类型见官方 Cosmic V7.0.1 [IFormPlugin](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/form/plugin/IFormPlugin.html) 和 [IDataModelChangeListener](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/entity/datamodel/events/IDataModelChangeListener.html)。操作事件参数位于 `kd.bos.form.events`，字段事件参数位于 `kd.bos.entity.datamodel.events`；不能统一写成 `EventObject`，否则没有覆盖目标事件。生成代码仍核对目标依赖。

## 插件内上下文方法

```java
// 视图与模型
IFormView view = this.getView();
IDataModel model = this.getModel();

// 读取单据常用字段
String billNo = (String) model.getValue("billno");
String billStatus = (String) model.getValue("billstatus");

// 控件级操作
Control control = view.getControl("fieldkey");
BasedataEdit basedataEdit = view.getControl("basedatafield");
view.setEnable(false, "fieldkey");
```

说明：`view.getControl("fieldkey")` 的返回类型是 `<T extends kd.bos.form.control.Control>`，所有控件都继承自 `kd.bos.form.control.Control`，实际拿到的是具体控件对象，例如 `BasedataEdit`、`EntryGrid`、`ProgressBar` 等。

## 示例代码

示例代码统一维护在模板文件中，直接参考：

- [BillPlugInTemplate.java](../../../assets/BillPlugInTemplate.java)

## 实践建议

1. 已有单据加载后处理放 `afterLoadData`；新增默认值放 `afterCreateNewData`。一次加载/刷新按数据包来源触发其中一个，避免把新增默认值覆盖到已存单据。
2. 事务级校验放操作插件，UI 插件只做交互提示与轻校验。
3. 字段联动优先在 `propertyChanged`；用户录入先执行相关实体服务规则，再触发此事件。初始化期间（包括 `afterCreateNewData` 内）赋值不触发它，需要的初始联动在初始化路径完成。
4. 变更值类型须与字段模型一致；模板的 `qty` 使用 `BigDecimal`。分录或多项变更使用 `e.getChangeSet()` 中各项的值与行索引，不能把包装层取首项的 helper 当成整个变更集合。

## 常见坑位

- 新增单据不触发 `afterLoadData`，初始化逻辑需兼顾 `afterCreateNewData`。
- 在 UI 插件中直接改状态字段替代操作流，容易与业务状态机冲突。
