# 扩展插件基类 (Plugin Base Extensions)

详细知识、官方来源与验证边界：[云端专题](https://chatgpt.com/space/page_e984982cb5b48191b0e8447301286950)。

## TL;DR
- 适用：所有可继承 Ext 基类的表单、单据、列表、操作插件都应先读本页。
- 先抓：选对 `Abstract*Ext` 基类，再复用已封装的日志、取值、监听注册和列表能力。
- 跳转：BOTP 转换、反写、工作流、OpenAPI 这类无 Ext 封装场景不要停在本页。
- 继续读全文：当你要确认 `@Override` 签名、生命周期或扩展方法全集时。

## 概述
扩展插件基类（Ext 系列）是基于金蝶苍穹原生插件类的二次封装。通过继承 `kd.cd.common.plugin` 下的基类，开发者可以直接获得统一的 `log` 对象，以及视图/元数据/取值等常用扩展方法。这是 `kd-cd-cosmic-commons` 项目包装的基础能力之一，并非所有苍穹环境自带 API。已核构件为 `RELEASE-26-0424`（声明 `Cosmic-Version: 7.0+`）；仍须检查项目实际依赖。

> **适用边界**
> ✅ 适用：所有需要继承 Ext 基类的表单/单据/列表/操作插件。
> ❌ 不适用：BOTP 转换插件和反写插件没有 Ext 封装，直接用原生基类。

## 核心基类

### 基础插件
- **`kd.cd.common.plugin.AbstractBasePlugInExt`**: 基础插件扩展。

### 单据插件
- **`kd.cd.common.plugin.AbstractBillPlugInExt`**: **单据插件首选**。封装了原生 `AbstractBillPlugIn`，内置 `log` 对象，实现 `IBillPluginExtension` 和 `BeforeF7SelectListener`。

### 表单插件
- **`kd.cd.common.plugin.AbstractFormPluginExt`**: 动态表单插件扩展。

### 列表插件
- **`kd.cd.common.plugin.AbstractListPluginExt`**: 列表插件扩展，强化了选中行（SelectedRows）的处理。

### 操作插件
- **`kd.cd.common.plugin.AbstractOperationServicePlugInExt`**: 操作插件扩展，简化了 `onPreparePropertys` 字段准备。

### 校验器
- **`kd.cd.common.plugin.AbstractValidatorExt`**: 校验器扩展。

## 常用 API 方法

### 通用能力 (所有基类)
- `log.info(String msg, Object... args)`: 统一的 `kd.bos.logging.Log` 日志对象。

### 操作插件特有 (`AbstractOperationServicePlugInExt`)
- `allFields()`: 按包装规则生成字段路径列表；不是无条件包含全部属性。
- `entryFields(String... entryKeys)`: 遍历指定分录并按包装规则生成字段路径列表。
- `addErrorMessage(DynamicObject dataEntity, String message)`: 快速回填操作错误。
- `addErrorMessage(DynamicObject dataEntity, String title, String message)`: 带标题的错误消息。
- `addErrorMessage(DynamicObject dataEntity, String title, String errCode, String message)`: 完整错误消息。
- `arrayOfIds(DynamicObject[] array)`: 提取主键数组。
- `setOfIds(DynamicObject[] array)`: 提取主键集合。
- `listOf(DynamicObject[] array, String field)`: 提取字段值列表。
- `setOf(DynamicObject[] array, String field)`: 提取字段值集合。

本构件两种字段入口都保留键名 `id`，其它属性排除 `LongProp`，再按所属实体补路径；不能将 `LongProp` 泛化为所有 Java Long 字段。必需字段按真实模型显式追加。`addErrorMessage` 最终追加操作错误信息，没有显式抛出业务异常或直接调用事务回滚，不能单独作为阻断/整批回滚保证。

### IFormPluginExtension 接口方法
- `getValue(String key)`: 获取字段值。
- `getValue(String key, int rowIndex)`: 获取分录字段值。
- `getValue(String key, int rowIndex, int parentRowIndex)`: 获取分录分录字段值。
- `getFlatValues(String key)`: 扁平获取字段所有值，返回 `List<T>`。
- `getBaseDataQuoteType(String baseDataField)`: 获取基础资料引用类型。
- `getEntryPropKeys(String entryKey)`: 获取分录字段标识集。
- `getEntryProperties(String entryKey)`: 获取分录字段属性映射。
- `getProperties(Predicate<IDataEntityProperty> predicate)`: 筛选字段属性。
- `getProperty(String field)`: 获取字段属性。
- `getEntryType(String entryKey)`: 获取分录类型。
- `getMainEntityType()`: 获取主实体类型。
- `view()`: 获取当前视图。

### 监听器注册方法
- `addEntryRowClickListeners(String... entryKeys)`: 批量注册分录行点击监听。
- `addTabSelectListeners(String... tabKeys)`: 批量注册页签选择监听。
- `addHyperClickListeners(String... keys)`: 批量注册超链接点击监听。
- `addItemClickListeners(String... keys)`: 批量注册菜单项点击监听。
- `addBeforeF7SelectListeners(String... keys)`: 批量注册 F7 弹出前监听。

### 数据更新方法
- `updateEntryView(String entryKey, DynamicObjectCollection rowData)`: 更新分录视图数据。

### 列表插件补充方法 (`AbstractListPluginExt`)
- `getButtonKeys(boolean includeDropDown)`: 获取列表按钮标识与操作映射。
- `getBillList()`: 获取列表控件。
- `getSelectedRowPkValues()`: 获取当前选中行主键集合。
- `clearSelectRows()`: 清空当前列表选中项。

### 继承接口补充
- `IBillPluginExtension` 另有 `getPkValue()` / `getBillStatus()`；`IFormEventArgsExtension` 提供操作标识/结果、点击标识和字段变化取值入口。
- `IFormViewExtension` 提供控件/样式、页面状态、父页面、参数、插件查询等能力；操作插件通过 `IEntityExtension` 继承对象/集合/主键工具。按实际基类选能力，不把所有接口方法当成所有插件共有。
- 本构件部分 extension 接口为包级可见，业务代码复用公开 Ext 基类继承的方法，不直接跨包 `implements` 这些接口。

### 调试方法
- `peek()`: 预览实体结构（调试用）。

## 示例代码

### 标准单据插件模板
```java
package kd.cd.common.demo;

import kd.cd.common.plugin.AbstractBillPlugInExt;
import kd.cd.common.entity.EntityUtils;
import kd.bos.entity.operate.result.OperationResult;
import kd.bos.form.events.AfterDoOperationEventArgs;

public class MyBillPlugin extends AbstractBillPlugInExt {
    @Override
    public void afterDoOperation(AfterDoOperationEventArgs e) {
        super.afterDoOperation(e);
        OperationResult result = e.getOperationResult();
        if ("audit".equals(e.getOperateKey()) && result != null && result.isSuccess()) {
            String billNo = getValue(EntityUtils.getBillNoKey(getBillFormId()));
            log.info("单据 {} 审核成功", billNo);
        }
    }
}
```

操作标识只说明执行了哪种操作；成功提示须检查结果，不能把进入 `afterDoOperation` 当作成功。官方 [AfterDoOperationEventArgs](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/form/events/AfterDoOperationEventArgs.html) 的方法是 `getOperateKey()`；[OperationResult.isSuccess()](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/entity/operate/result/OperationResult.html) 会计入校验失败及错误信息。依据为 Cosmic V7.0.1；目标签名仍按 `SKILL.md` 核验，批量操作还需分别处理成功项与失败项。

### 操作插件模板
```java
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import kd.cd.common.plugin.AbstractOperationServicePlugInExt;
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.entity.plugin.PreparePropertysEventArgs;
import kd.bos.entity.plugin.args.BeginOperationTransactionArgs;

public class MyOperationPlugin extends AbstractOperationServicePlugInExt {
    @Override
    public void onPreparePropertys(PreparePropertysEventArgs e) {
        super.onPreparePropertys(e);
        Set<String> fields = new LinkedHashSet<>();
        if (e.getFieldKeys() != null) {
            fields.addAll(e.getFieldKeys());
        }
        // 按场景选一项；需要包装全字段路径时改为 allFields()。
        List<String> requested = entryFields("entry1", "entry2");
        fields.addAll(requested);
        fields.add("forbidflag"); // 示例依赖的主实体字段；交付时核对真实标识。
        e.setFieldKeys(new ArrayList<>(fields));
    }

    @Override
    public void beginOperationTransaction(BeginOperationTransactionArgs e) {
        super.beginOperationTransaction(e);
        DynamicObject[] bills = e.getDataEntities();
        if (bills == null) {
            return;
        }
        for (DynamicObject bill : bills) {
            if (bill != null && Boolean.TRUE.equals(bill.getBoolean("forbidflag"))) {
                // 仅演示结果回填，不表示事务已回滚或此记录已被剔除。
                addErrorMessage(bill, "操作失败，请检查数据");
            }
        }
    }
}
```

连续 `setFieldKeys` 会替换前一清单；先合并既有字段和本例依赖，再设置一次。`entry1`、`entry2`、`forbidflag` 是说明性标识，交付时核对真实模型。本例只展示字段准备和错误回填；前置阻断应使用实际校验/异常合同，不能因加了错误信息就跳过数据状态与事务结果确认。

### 使用扩展方法
```java
import java.util.List;
import java.util.Set;
import kd.cd.common.plugin.AbstractBillPlugInExt;

public class DemoPlugin extends AbstractBillPlugInExt {
    public void demo() {
        // 获取字段值（支持深路径）
        String orgName = getValue("org.name");

        // 扁平获取分录所有物料ID
        List<Object> materialIds = getFlatValues("entry.material.id");

        // 获取分录字段信息
        Set<String> entryFields = getEntryPropKeys("entry");

        // 获取基础资料引用类型
        String baseType = getBaseDataQuoteType("material");

        // 调试预览
        Object data = peek();
    }
}
```

## 方法签名快照（生成 @Override 时直接对照）

以下是本机构件核验的可用重写签名；不是完整生命周期顺序或所有版本承诺。

### AbstractFormPluginExt / AbstractBillPlugInExt 共有生命周期
```java
public void initialize()
public void registerListener(EventObject e)
public void preOpenForm(PreOpenFormEventArgs e)
public void createNewData(BizDataEventArgs e)
public void afterCreateNewData(EventObject e)
public void loadData(LoadDataEventArgs e)
public void beforeBindData(EventObject e)
public void afterBindData(EventObject e)
public void afterCopyData(EventObject e)
public void propertyChanged(PropertyChangedArgs e)
public void beforeDoOperation(BeforeDoOperationEventArgs args)
public void afterDoOperation(AfterDoOperationEventArgs args)
public void beforeItemClick(BeforeItemClickEvent evt)
public void itemClick(ItemClickEvent evt)
public void beforeClick(BeforeClickEvent evt)
public void click(EventObject evt)
public void beforeF7Select(BeforeF7SelectEvent e)
public void confirmCallBack(MessageBoxClosedEvent evt)
public void closedCallBack(ClosedCallBackEvent e)
public void clientCallBack(ClientCallBackEvent e)
public void beforeClosed(BeforeClosedEvent e)
public void customEvent(CustomEventArgs e)
public void TimerElapsed(TimerElapsedArgs e)
public void afterAddRow(AfterAddRowEventArgs e)
public void afterDeleteRow(AfterDeleteRowEventArgs e)
public void afterDeleteEntry(AfterDeleteEntryEventArgs e)
public void destory()   // 注意：不是 destroy
```

### AbstractBillPlugInExt 单据生命周期
```java
public void afterLoadData(EventObject e)
```

本机构件的 `afterLoadData` 来自 `IBillPlugin`，单据插件可用；不能直接放到普通 `AbstractFormPluginExt` 上生成 `@Override`。

### AbstractListPluginExt 特有
```java
public void setFilter(SetFilterEvent e)
public void afterCreateNewData(EventObject e)
```

旧条目 `beforeDoSelectRow(BeforeDoSelectRowEventArgs)` 在本机列表继承链未确认，不用它生成 `@Override`；需要选中行行为时核对目标控件/插件的实际事件入口，不杜撰替代签名。

### AbstractOperationServicePlugInExt 生命周期
```java
public void onPreparePropertys(PreparePropertysEventArgs e)
public void onAddValidators(AddValidatorsEventArgs e)
public void beforeExecuteOperationTransaction(BeforeOperationArgs e)
public void beginOperationTransaction(BeginOperationTransactionArgs e)
public void endOperationTransaction(EndOperationTransactionArgs e)
public void afterExecuteOperationTransaction(AfterOperationArgs e)
public void onReturnOperation(ReturnOperationArgs e)
```

### AbstractValidatorExt
```java
public void validate()
```

本机校验器重写无参 `validate()`，数据及上下文由 `getDataEntities()` / `getValidateContext()` 取得；不能套用旧的双参数签名。

## 实践建议
1. **保留父类合同**：重写时先核对父实现及项目要求；存在必要逻辑就保留 `super.xxx()` 并遵守其调用位置，不能推定所有事件都在 super 初始化上下文。本机表单 `setView` 保存视图/模型并注册监听，而 `initialize`、操作接口的 `onPreparePropertys`/`beginOperationTransaction` 默认体为空；后者示例保留 super 调用，但不把它说成已执行初始化。接口默认方法与继承类的方法按实际声明判断。
2. **包名校验**: 导入时必须认准 `kd.cd.common.plugin`，避免误导至原生的 `kd.bos` 类。
3. **轻量化插件**: 插件层只保留贴近触发点的编排与控制逻辑；复杂计算、可复用业务规则与跨模块数据处理应剥离至服务层（Service）。
4. **使用扩展方法**: 优先使用基类提供的扩展方法（如 `getValue`, `getFlatValues` 等），减少重复代码。

## 常见坑位
1. **成员状态与资源**：官方普通表单初始化说明按请求重建插件/视图/模型，不能把所有插件成员当作 Session 持久状态；其它插件按其实际生命周期核对。仍不要把 `DataSet`、`InputStream` 等有生命周期的资源放入成员跨回调保存；在使用范围内释放。确需跨请求保存的合法业务数据按平台缓存/序列化合同处理，不序列化活资源。
2. **初始化职责**：官方 `initialize` 文档明确可通过 `this.getView()` 取得界面信息；该事件适合轻量变量初始化，不用于设置字段值、控件状态或注册监听。按对应事件执行这些动作；自行 new 插件不代表已注入视图。
3. **多实例冲突**: 同一个表单打开多个页签时，静态变量（static）会共享，严禁在插件中使用非 final 的静态变量存储状态。
4. **绕过父类逻辑**：例如自行重写 `setView` 却丢失父类视图注入，会破坏上下文；按具体父方法合同保留，不推广成所有事件统一初始化。

## 来源与验证边界

- 官方 [setView 事件](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=222729004057800960&type=Knowledge&productLineId=29&lang=zh-CN) 与 [initialize 事件](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=222730410794020096&type=Knowledge&productLineId=29&lang=zh-CN) 分别说明上下文注入和轻量初始化；文章未列精确 SDK 补丁。
- 签名按实际 commons `RELEASE-26-0424` 与本机 7.0 hotfix 依赖核验；三个示例仅离线编译，生命周期声明另用 `@Override` 编译壳校验。未初始化表单、日志、事务、DB 或验证真实事件触发/回滚。
