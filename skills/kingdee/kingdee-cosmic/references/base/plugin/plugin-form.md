# 动态表单插件

详细知识、官方来源与验证边界：[云端专题](https://chatgpt.com/space/page_8c9a77acc8fc8191b2fa5dec93e3ca30)。


## TL;DR
- 适用：动态表单插件原生兜底，封装层没覆盖的 UI 生命周期和监听器时读本页。
- 先抓：`AbstractFormPlugin`、`registerListener`、核心事件顺序和上下文方法。
- 跳转：能用 `AbstractFormPluginExt` 就优先回到 `adv/plugin-base.md`；纯后台逻辑别读本页。
- 继续读全文：当你要确认字段联动、F7、页签/分录监听、单据内容水印或文末坑位时。

## 概述
动态表单是金蝶云苍穹的基础 UI 承载，支持各类表单场景（单据、基础资料、活动等）。动态表单插件用于在表单加载、初始化、交互全生命周期进行业务逻辑干预。

> **适用边界**
> ✅ 本文档是原生兜底：当 `plugin-base.md`(封装层) 未覆盖你需要的表单事件时使用。
> ❌ 如果封装层 `AbstractFormPluginExt` 已满足需求，优先读 `references/adv/plugin-base.md`。

- 适用场景：表单字段联动、控件状态管理、事件拦截、参数验证

术语说明：文档中的 `F7` 指基础资料、引用数据等“选择引用数据”的控件弹窗场景，不是键盘按键事件。

## 核心基类


- 基类：`kd.bos.form.plugin.AbstractFormPlugin`
- 继承关系：`AbstractFormPlugin extends AbstractDataModelPlugin implements IFormPlugin`

## 额外监听器

- `BeforeF7SelectListener`：F7（基础资料/引用数据选择控件）弹出前，调整过滤条件
- `RowClickEventListener`：表格行点击
- `TreeNodeClickListener`：树形节点点击
- `TreeNodeCheckListener`：树形节点勾选
- `TabSelectListener`：标签页切换
- `ItemClickListener`：菜单/按钮点击
- `ClickListener`：控件通用点击
- `ProgresssListener`：进度条变化

## 核心事件

- `setPluginName`：// 显示界面前，准备显示配置时触发
- `preOpenForm`：// 显示界面前，准备参数时触发
- `loadCustomControlMetas`：// 显示界面前，构建参数时触发
- `setView`：// 表单视图模型初始化时调用，传入 IFormView
- `initialize`：// 表单视图初始化后触发
- `registerListener`：// 用于注册当前控件的事件监听；不据此假定整页生命周期只调用一次
- `getEntityType`：// 创建数据包前触发
- `createNewData`：// 开始新建数据包时触发
- `afterCreateNewData`：// 新建数据包完毕后触发
- `beforeBindData`：// 刷新前端前触发
- `afterBindData`：// 刷新前端后触发
- `beforeItemClick`：// 菜单按钮点击前触发
- `itemClick`：// 菜单按钮点击时触发
- `beforeDoOperation`：// 执行操作前触发
- `afterDoOperation`：// 执行操作后触发
- `confirmCallBack`：// 确认提示后触发
- `closedCallBack`：// 子界面关闭时触发
- `flexBeforeClosed`：// 弹性域维护界面关闭时触发
- `onGetControl`：// 获取控件编程模型时触发
- `customEvent`：// 自定义控件定制事件触发
- `TimerElapsed`：// 定时触发
- `beforeClosed`：// 界面关闭前触发，界面资源仍存在；可取消关闭
- `destory`：// 界面关闭后释放插件创建的资源；表单上下文可能已销毁
- `pageRelease`：// 界面关闭后释放插件创建的资源，比destory稍晚
- `beforeclick`：// 点击前校验事件
- `click`：// 点击后触发操作事件
- `propertyChanged`：// 修改字段值后触发

### 关闭前校验与关闭后释放

关闭校验以及它所需的表单读值放在 `beforeClosed`；通过 `BeforeClosedEvent.setCancel(true)` 可取消关闭，取消后不要继续按“页面已关闭”处理。正常完成关闭后，`destory` 先于 `pageRelease`，两者用于释放插件创建的资源。`destory` 时表单上下文可能已经销毁，不要把读取表单信息或关闭校验推迟到释放阶段；也不要由正常关闭顺序推定浏览器异常退出、断网时必定触发这些回调。

依据：[beforeClosed](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=222768769984991488&productLineId=29)（2026-07-31 更新）、[destory](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=222769424095135488&productLineId=29)（2024-04-17 更新）、[pageRelease](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=222769921389358336&productLineId=29)（2026-07-31 更新）。正文未给完整版本范围；实现时核对目标 SDK 的事件和参数签名。

## 插件内上下文方法

```java
// 获取表单视图模型
IFormView view = this.getView();

// 获取表单数据模型
IDataModel model = this.getModel();

// 获取指定控件
Control control = this.getView().getControl("controlKey");
BasedataEdit basedataEdit = this.getView().getControl("basedatafield");
EntryGrid entryGrid = this.getView().getControl("entryentity");

// 获取字段值
Object value = this.getModel().getValue("fieldKey");

// 设置字段值；初始建数据阶段不触发 propertyChanged，联动按事件合同处理
this.getModel().setValue("fieldKey", newValue);

// 控件启用/禁用
this.getView().setEnable(false, "controlKey");

// 控件隐显
this.getView().setVisible(false, "controlKey");

// 获取完整数据包
DynamicObject dataEntity = model.getDataEntity();
```

说明：`this.getView().getControl("controlKey")` 的返回类型是 `<T extends kd.bos.form.control.Control>`，所有控件都继承自 `kd.bos.form.control.Control`，实际拿到的是具体控件对象，例如 `BasedataEdit`、`EntryGrid`、`ProgressBar` 等。

## 示例代码

示例代码统一维护在模板文件中，直接参考：

- [FormPluginTemplate.java](../../../assets/FormPluginTemplate.java)

## 按单据内容生成水印

- 按单据内容定制时，核对示例所需的表单插件挂载与水印配置绑定；水印配置在上级节点绑定会作用于其下页面，先确认实际作用范围，不为单张单据扩大到整个应用。入口为 `IWaterMarkPlugin.setWaterMarkInfo(LoadWaterMarkInfoEventArgs e)`；普通表单事件里赋字段值不能代替水印回调。
- 通过事件源取打开参数前判断是否为 `BillShowParameter`。每条返回路径均需 `e.setWaterMark(waterMark)`，包括非单据来源或提前返回，避免下游取得空对象。
- 取单据编号时，从打开参数的 `formId` 解析 `FormConfig.getEntityTypeId()`，再按 `pkId` 取实体；不要直接把页面标识当实体标识。新建未保存可能没有 `pkId`，加载结果也可能为空；仅在确认实体类型为 `BillEntityType` 后使用其单据编号字段。无编号仍要求水印时，用当前可用信息组成非空内容，不为水印预先保存单据。
- 官方示例的随机类型包含“不显示”，仅适合演示；需要稳定水印时按业务要求固定为可见类型。示例虽然读取姓名、手机号，实际 `setText` 只写了单据编号；如需求包含用户信息，需明确拼接，并处理空用户和不足四位的手机号。
- 页面显示、附件预览、下载、打印按需求分别验证。正文示例出现 `setAddDownloadWatermark`、`setAddImageDownloadWatermark`，但不能据此推定所有打印或文件类型都会生效；先确认目标 SDK 与实际输出入口。

依据：[社区帮助《根据单据内容自定义水印》](https://vip.kingdee.com/knowledge/890900627831297280)（2026-09-24 更新）与[水印插件及配置范围](https://vip.kingdee.com/knowledge/specialDetail/294832938980257024?category=294833149400665344&id=289788705932651264&type=Knowledge&productLineId=29&lang=zh-CN)（2026-07-30 更新）。正文未给完整版本范围；接口在本地 Cosmic V8.0.1 索引可查，不代表目标项目已经兼容。注册、发布按当前任务授权执行。

## 初始化与页面状态

普通表单的服务端视图、模型和插件可能在后续请求中重建，`initialize` 用于轻量变量初始化，不能当作整页只执行一次的构造过程。页面缓存中的跨请求业务标记只在缺失时设默认值；再次初始化时保留已恢复状态，业务重置放到明确的操作/回调分支。模板的 `submitflag` 因而不会在下次初始化时被无条件改回 false。

创建数据后的默认值与初始计算放 `afterCreateNewData`；绑定前后围绕生成前端刷新指令，不把 `afterBindData` 当作浏览器完成渲染的确认。`propertyChanged` 处理后续字段联动，人工录入先执行相关实体服务规则；批量变更遍历 `ChangeData[]`，按字段所属实体及数据对象区分头/分录，不能只凭行号 0 判断字段层次。

依据：[initialize](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=222730410794020096&type=Knowledge&productLineId=29&lang=zh-CN)、[事件总览](https://vip.kingdee.com/knowledge/221684288814181632)、[propertyChanged](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=228917111786574080&type=Knowledge&productLineId=29&lang=zh-CN)。官方正文未给精确 SDK 版本；按目标依赖核签名，不把一页总览外推成所有插件完整调用链。

## 实践建议

1. **registerListener中统一注册所有监听**
   - 按控件与事件类型注册；仅实现监听接口不会自动订阅控件事件
   - 保留基类的 `super.registerListener(e)`；同一注册路径不要对同一控件、同一监听器重复 `add`
   - 不凭控件标识相同，就用页面缓存、静态集合或跨请求布尔值跳过后续注册；这不能证明当前控件实例已绑定监听

2. **propertyChanged做联动**
   - 修改后的级联操作放propertyChanged

3. **afterCreateNewData内赋值不触发propertyChanged**
   - 文档明确说明此时不触发propertyChanged
   - 初始化所需的计算与默认值在此显式完成；交互时仍由propertyChanged调用相同业务计算，不依赖初始化自动触发联动
   - afterBindData用于设置可见、可用等界面状态，不把初始化字段赋值移到此处

4. **子页面返回统一走closedCallBack**
   - 不要在各处open子页面时写回调
   - 所有子页面返回由closedCallBack统一处理

5. **重逻辑不要放插件**
   - 复杂业务逻辑写服务层
   - UI插件仅做编排与界面控制

## 常见坑位

### ❌ 仅implements接口不注册监听

实现接口后，还需在 `registerListener` 注册到具体控件；单击和双击的参数均为 `TreeNodeEvent`。完整写法：

```java
import java.util.EventObject;
import kd.bos.form.plugin.AbstractFormPlugin;
import kd.bos.form.control.TreeView;
import kd.bos.form.control.events.TreeNodeEvent;
import kd.bos.form.control.events.TreeNodeClickListener;

public class TreeClickGood extends AbstractFormPlugin implements TreeNodeClickListener {
    @Override
    public void registerListener(EventObject e) {
        super.registerListener(e);
        TreeView tv = this.getView().getControl("treeKey");
        if (tv != null) {
            tv.addTreeNodeClickListener(this);  // 必须注册
        }
    }

    @Override
    public void treeNodeClick(TreeNodeEvent e) {
        Object nodeId = e.getNodeId();
        // 按 nodeId 处理当前点击节点
    }

    @Override
    public void treeNodeDoubleClick(TreeNodeEvent e) {
        // 无双击业务时保留空实现
    }
}
```

依据：[社区帮助《树形控件插件》](https://vip.kingdee.com/knowledge/230366156979367424)的监听注册与回调示例；上述签名按目标 SDK 核验。普通 `TreeView` 的懒加载事件是 `queryTreeNodeChildren`，不要套用左树右表列表插件的 `refreshNode`。

### ❌ 在registerListener里调用model.getValue
- 此时数据尚未绑定，getValue返回null
- 应在afterBindData或propertyChanged里操作

### ❌ 期望afterCreateNewData触发propertyChanged
- 此时赋值不会触发propertyChanged事件
- 在afterCreateNewData显式完成必要的初始计算；afterBindData只根据结果控制界面状态

依据：[表单事件总览](https://vip.kingdee.com/knowledge/221684288814181632)、[初始化数据包](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=222735399012056064&productLineId=29)与[绑定后事件](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=222741078570036480&productLineId=29)。绑定前的属性设置及数据修改标志区别，见[生命周期放置策略](../../event-lifecycle.md#放置策略)。

### ❌ 嵌套树/表格重复注册监听
- 检查基类与子类是否对当前控件、同一事件重复 `add`；先区分重复注册和多个不同事件的正常订阅
- 判断需基于当前控件实例与实际注册路径；不要把“控件 key 相同”当作后续请求无需注册的证据

依据：[registerListener 专页](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=222731953945358592&productLineId=29)（2024-09-14 更新）说明控件事件须先注册，示例直接在回调中取得控件并添加监听。正文未承诺每页总调用次数；出现重复或漏回调时，结合目标 SDK 与运行时调用链核对，不新增无依据的全局去重开关。

### ❌ destory拼写错误
- 方法名是destory（少r），不是destroy
- 跟风覆盖时要按文档准确拼写
