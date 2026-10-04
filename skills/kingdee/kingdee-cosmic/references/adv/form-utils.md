# 界面视图增强工具 (FormUtils)

详细知识、官方来源与验证边界：[云端专题](https://chatgpt.com/space/page_6ba308ff7b4c819197859a5e2bf150cc)。

## TL;DR
- 适用：表单/UI 控件启停、可见性、筛选、消息提示和视图信息读取。
- 先抓：视图、插件、控件和消息方法需要有效的页面上下文；表单标识和元数据方法按各自参数使用。
- 跳转：后台打开页面改读 `view-handler.md`；服务端事务逻辑改读操作插件文档。
- 继续读全文：当你要确认控件定位、元数据读取或消息处理 API 时。

## 概述
`kd.cd.common.form.FormUtils` 是项目 commons 包装，提供视图、控件、标识、元数据与消息读取入口；不是原生 `kd.bos` SDK 类。下述包装合同按 `kd-cd-cosmic-commons` 的 `RELEASE-26-0424` 核验，实际依赖为本机 7.0 构件；迁移到其他项目时重新核对依赖。

> **适用边界**
> ✅ 适用：表单控件启用/禁用/隐藏、UI 消息、视图判定。
> ❌ 不适用：后台操作（无 UI 上下文）请用操作插件；后台打开表单/列表请用 `view-handler.md`。

## 核心类
- **`kd.cd.common.form.FormUtils`**: **界面工具核心类**。

## API 方法全览

### 1. 视图状态与属性
- `getBillFormId(IFormView view)`: 返回 `String`；列表取 `IListView.getBillFormId()`，其他视图取打开参数的 `formId`，null 视图返回 null；不自动归一扩展表单或实体标识。
- `getBillStatus(IFormView view)`: 返回 `String`；要求 `IBillView`，根据实体的状态字段标识读取模型值。缺字段、模型未就绪或值非 String 没有默认状态兜底。
- `getParentViewNoPlugin(IFormView view)`: 取打开参数的直接父 PageId，再调用 `view.getViewNoPlugin(id)`，并非逐级寻找没有插件的祖先页面。结果只用于访问页面数据，不执行依赖父页面插件的业务逻辑。
- `getViewByPageId(String pageId)`: 通过 PageId 恢复视图；依赖当前 `SessionManager`，此版本还调用 `setRequestThread(true)`，不是脱离页面环境的纯查找。找不到可能返回 null，不能据此建立跨用户访问权限。
- `getPluginInstance(String pageId, Class<T> clazz)`: `T extends IFormPlugin`；按类全名与 `getPluginName()` 精确匹配，视图或插件未找到返回 null，不是按继承关系筛选。
- `getAllPluginInstance(String pageId)`: 获取视图所有插件实例（调试用）。

### 2. 列表控件
- `getBillList(IFormView view)`: 获取列表控件（BillList）。
- `getReportList(IFormView view)`: 获取报表列表控件（ReportList）。
- `getListGrid(IFormView view, Class<T> clazz)`: 获取列表网格控件（泛型）。
- `getListButtonKeys(String formId, boolean includeDropDown)`: 获取列表所有按钮标识与其对应操作映射。

### 3. 控件筛选与检索
- `getAllControls(IFormView view)`: 获取当前界面所有控件 Map。
- `getAllControls(String formId)`: 获取表单中所有控件对象。
- `getSubControls(Container container, boolean includeContainer)`: 获取容器内的子控件。
- `selectControls(IFormView view, Predicate<Control> filter)`: 筛选表单控件。
- `selectSubControls(Container container, Predicate<Control> filter)`: 筛选容器子控件。

### 4. 表单标识获取
- `getF7ListFormId(String billFormId)`: 获取列表F7标识。
- `getListFormId(String billFormId)`: 获取列表标识。
- `getMasterFormId(String extFormId)`: 根据拓展表单标识获取原表单标识。

### 5. 元数据读取
- `readListMetadata(String billFormId)`: 查询列表元数据。
- `readEntityMeta(String formId)`: 查询实体元数据。
- `readEntityMetaAsMap(String formId, String... fieldKeys)`: 查询实体元数据字段映射。
- `readFormMeta(String formId)`: 查询表单元数据。
- `readFormMetaAsMap(String formId, String... fieldKeys)`: 查询表单元数据字段映射。

### 6. UI 消息处理
- `peekUIMsg(IFormView view)`: 返回 `Map<String, ?>`，按消息动作归集参数；新建 Map 和参数列表，但嵌套元素仍共享，不修改返回值中的嵌套对象。
- `getFlatUIMessages(IFormView view, boolean ignoreSuccessMsg)`: 返回新 `List<String>`，提取 `ShowNotificationMsg`、`showMessage`、`showErrMsg`。true 只跳过 `ShowNotificationMsg` 中 `type` 与 `Integer.valueOf(0)` 相等的通知，不代表过滤所有指令中的成功结果。

两者内部要求非空的 `kd.bos.mvc.form.FormView`，读取待发送的 UI action，在该包装实现中不消费或清空原消息；不是业务成功/失败的权威结果。消息可能包含业务数据，调试输出先脱敏。

## 示例代码

以下完整类保留视图信息、控件筛选、列表与插件定位、UI 消息四个场景。由已有页面插件在相应模型/控件就绪后调用；`billView` 须有可用状态字段，`listView` 须为单据列表，`pluginType` 传实际已挂载插件类。类本身不挂载、不打开页面，也不在构造器或任意后台线程调用这些方法。

```java
import java.util.List;
import java.util.Map;
import kd.cd.common.form.FormUtils;
import kd.bos.bill.IBillView;
import kd.bos.form.IFormView;
import kd.bos.form.control.Control;
import kd.bos.form.control.EntryGrid;
import kd.bos.form.plugin.IFormPlugin;
import kd.bos.list.BillList;
import kd.bos.list.IListView;

public final class FormUtilsExamples {
    public void analyzeView(IBillView billView) {
        String formId = FormUtils.getBillFormId(billView);
        String status = FormUtils.getBillStatus(billView);
        IFormView parentView = FormUtils.getParentViewNoPlugin(billView);
        // parentView 可能不存在；有值时也不调用其插件业务逻辑。
    }

    public void filterControls(IFormView view) {
        String formId = FormUtils.getBillFormId(view);
        Map<String, Control> allControls = FormUtils.getAllControls(view);
        Map<String, Control> entryGrids =
                FormUtils.selectControls(view, EntryGrid.class::isInstance);
        Map<String, String> buttonOps = FormUtils.getListButtonKeys(formId, true);
    }

    public <T extends IFormPlugin> T listOperation(
            IListView listView, Class<T> pluginType) {
        String pageId = listView.getPageId();
        BillList billList = FormUtils.getBillList(listView);
        IFormView targetView = FormUtils.getViewByPageId(pageId);
        if (targetView == null) {
            return null;
        }
        // 返回 null 时，由调用方处理页面失效、未挂载或插件名不匹配。
        return FormUtils.getPluginInstance(pageId, pluginType);
    }

    public void checkMessages(IFormView view) {
        List<String> messages = FormUtils.getFlatUIMessages(view, true);
        Map<String, ?> uiMsg = FormUtils.peekUIMsg(view);
        // 仅供脱敏诊断，不修改 uiMsg 中浅共享的嵌套参数。
    }
}
```

## 实践建议
1. **控件筛选**: 使用 `selectControls` 配合方法引用可以快速筛选特定类型控件，如 `EntryGrid.class::isInstance`。
2. **父视图获取**: 仅访问父页面数据时可用 `getParentViewNoPlugin`；无插件视图不得用来绕开插件业务逻辑。
3. **按钮映射**: `getListButtonKeys` 可用于动态判断按钮对应的操作，便于条件控制。
4. **元数据读取**: `readEntityMeta/readFormMeta` 委托 `MetadataDao` 解析标识并读取运行时元数据，其他 read 入口在此基础上处理。避免高频重复读取；是否命中平台缓存、实际 DB 次数须按目标版本/调用路径确认，不自行增加没有隔离与失效合同的缓存。

## 常见坑位
1. **视图类型判断**: `getBillStatus` 对非 `IBillView` 的视图断言失败；IBillView 也不保证有状态字段。先核实体字段与模型就绪时机，不把异常或 null 改写为默认状态。
2. **PageId 与插件上下文**: 使用当前授权页面流程中的 PageId，处理页面失效/null；PageId 不是授权凭据，不从外部输入直接恢复其他用户视图。平台通过 `setView` 注入插件上下文，自行 new 插件不能替代此过程。
3. **控件 Key 区分**: 控件的 Key 与字段标识可能不同，需通过设计器确认。
4. **元数据缓存**: 包装入口不提供“每次物理访问数据库”或“永不访问数据库”的保证；平台元数据读取与当前页面运行模型也不是同一对象合同。

## 相关工具类
- **`kd.cd.core.util.SystemPropertyUtils`**: 系统配置工具
  - `isProdEnv()`: 判定是否为生产环境
  - `get(String key, String def)`: 获取配置项
  - `getBoolean(String key, boolean def)`: 获取布尔配置项

## 官方入口
- [动态表单视图模型](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=218036503564142336&id=221674425806898944&type=Knowledge&productLineId=29&lang=zh-CN)、[setView 上下文注入](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=222729004057800960&type=Knowledge&productLineId=29&lang=zh-CN)：官方正文未标精确产品版本。
- [IFormView：Cosmic V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/index.html?nav=class&package=kd.bos.form&name=IFormView)：原生 noPlugin 与页面指令合同；不替代项目 commons 及实际 7.0 构件核验。
