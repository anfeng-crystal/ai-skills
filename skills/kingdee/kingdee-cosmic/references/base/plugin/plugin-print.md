# 打印插件

详细知识、官方来源与验证边界：[云端专题](https://chatgpt.com/space/page_c6cf5db9bdd48191a49a2d55ec2c2adc)。


## TL;DR
- 适用：打印数据加载、自定义数据源和打印前后加工。
- 先抓：`AbstractPrintPlugin` 以及 `beforeLoadData` / `loadCustomData` 两类核心入口。
- 跳转：报表展示不是本页；文件和附件处理也不是本页。
- 继续读全文：当你要确认打印上下文、扩展点或自定义数据源示例时。

## 概述
打印插件用于控制打印数据加载、控件输出前后加工以及自定义数据源取数。

> **适用边界**
> ✅ 本文档直接使用：打印插件无封装层，直接参考本文档。

## 核心基类
- 基类：`kd.bos.print.core.plugin.AbstractPrintPlugin`
- 继承关系：`AbstractPrintPlugin implements IPrintPlugin`

## 核心事件

- `beforeLoadData(BeforeLoadDataEvent evt)`：打印数据加载前触发，可取消默认取数。
- `loadCustomData(CustomDataLoadEvent evt)`：自定义数据源加载数据时触发。
- `beforeOutputWidget(BeforeOutputWidgetEvent evt)`：控件输出前触发。
- `afterOutputWidget(AfterOutputWidgetEvent evt)`：控件输出后触发。

## 插件内上下文方法

以下更适合作为打印插件内主动访问的上下文能力：

- `getMainDataVisitor()`
- `getDataVisitor(String dataSource)`
- `getPrintSetting()`
- `getExtParam()`
- `getTplInfo()`
- `isPreview()`

```java
Map extParam = this.getExtParam();
Object tplInfo = this.getTplInfo();
boolean preview = this.isPreview();
```

## 其他扩展点

- `parseRichImg(...)`：富文本图片解析扩展。
- `setExtParam(...)` 等 getter/setter：上下文读写接口，不建议写成事件说明。

## 示例代码

示例代码统一维护在模板文件中，直接参考：

- [PrintPluginTemplate.java](../../../assets/PrintPluginTemplate.java)

## 实践建议

1. 替换既有数据源取数：在 `beforeLoadData` 中先按数据源标识限定范围，构造 `List<DataRowSet>` 并 `evt.setDataRowSets(rows)`，再 `evt.setCancleLoadData(true)`。实际 7.0 的默认提供器取消后直接返回本事件结果，不再执行该分支的默认取数及后置加工；取消本身不会转到 `loadCustomData`。
2. 真正的 `CustomDataSource`：在 `loadCustomData` 中向 `evt.getCustomDataRows()` 添加实际行。名称带 custom 不会改变数据源类型，`getExtParam()` 完成标记也不代表已提供数据。
3. 输出前后事件更适合做格式化和控件值调整，不要承载重型查询。
4. 上下文 getter/setter 保持在模板提示里即可，不必按事件去展开。
5. 自定义数据源场景优先让模板和数据源标识一一对应。

## 常见坑位

- 把 `getExtParam()`、`getPrintSetting()` 这类上下文访问方法写成事件。
- 只取消默认加载或只构造 `DataRowSet` 却未把它加入结果集合，导致打印空白。
- 无条件取消所有数据源，或把只追加过滤条件的场景也取消默认取数。
- `loadCustomData` 无条件 `clear()` 清掉其他插件贡献的数据。整体替换与追加须由业务明确。
- 在输出前后事件里执行过重逻辑，拖慢打印性能。

## 结果集合与字段

`setDataRowSets` 会整体替换当前事件集合，模板的普通源示例选择的是整体替换。若需求要求保留前序插件已经提供的行，先复制事件已有集合（若有），按业务规则合并本插件行，再设置完整结果；不要直接向引擎最初传入的集合追加，实际 7.0 Query 提供器的初始集合可能不可修改。自定义源模板则以追加为默认。整体重建、追加及去重方式须按业务决定，不能混用。

模板中的 `loadReplacementRows` / `loadCustomRows` 是待实现的本地业务钩子，不是 SDK 事件。前者默认 `null` 保留默认取数；返回空集合则有意返回零行。后者返回非 null 的待追加集合。一次事件可以仅负责一个数据源或一批数据，不把实例字段中的旧行集合当成本次结果复用。

`DataRowSet` 的值是打印 `Field`，不是直接放任意业务对象。文本行可按已确认的字段和值映射：

```java
// imports: kd.bos.print.core.data.DataRowSet;
//          kd.bos.print.core.data.field.TextField;
//          java.util.Map;
private DataRowSet toTextRow(Map<String, String> values) {
    DataRowSet row = new DataRowSet();
    for (Map.Entry<String, String> value : values.entrySet()) {
        row.put(value.getKey(), new TextField(value.getValue()));
    }
    return row; // 调用者还须 rows.add(row) 或加入 evt.getCustomDataRows()
}
```

金额、整数等保留相应 `DecimalField`、`IntegerField`、`LongField` 类型；分录用 `CollectionField(List<DataRowSet>)`。真实字段、过滤、权限和分页取数由业务实现，不把示意文本填给所有字段。

## 依据与版本

[官方知识：打印模板插件](https://vip.kingdee.com/knowledge/558017838934302720)（更新 2026-07-30）区分 `setDataRowSets` 替代结果和自定义源 `getCustomDataRows`。其中演示代码存在取消位置在范围判断之前、构造行后未加入集合等疏漏，不能原样套用。本文的签名和取消分支以实际 7.0 打印 JAR 核验；其他版本按目标 SDK 确认，不由知识页更新时间推定兼容。
