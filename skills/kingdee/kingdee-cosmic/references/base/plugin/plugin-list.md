# 标准单据列表插件

## TL;DR
- 适用：标准/基础资料/左树右表列表的原生兜底事件与取数控制。
- 先抓：`AbstractListPlugin`、过滤容器、列定义、行点击和打开单据回调。
- 跳转：若 Ext 基类够用先回 [封装基类](../../adv/plugin-base.md)；树侧联动再补读 `plugin-tree-list.md`。
- 标准列表/模板导出要切换 CSV/XLSX、核对容量或数值格式时，先读 [导出格式合同](../../list-export-format.md)。
- 继续读全文：当你要改过滤器、列表取数、超链接或行事件，并规避文末坑位时。

## 概述
单据列表插件用于控制列表的加载、显示、取数、过滤、行交互等全生命周期。列表支持标准的单据/基础资料列表、左树右表列表等多种布局。

> **适用边界**
> ✅ 本文档是原生兜底：当 `plugin-base.md`(封装层) 未覆盖你需要的列表事件时使用。
> ❌ 如果封装层 `AbstractListPluginExt` 已满足需求，优先读 `references/adv/plugin-base.md`。

- 适用场景：列表过滤定制、列表数据处理、行交互、超链接、单据打开回调

术语说明：文档中的 `F7` 指过滤容器或字段上的基础资料/引用数据选择控件弹窗，不是键盘按键事件。

## 核心基类


- 基类：`kd.bos.list.plugin.AbstractListPlugin`
- 继承关系：`AbstractListPlugin extends AbstractFormPlugin implements ListRowClickListener, IPCListPlugin`

## 额外监听器

- `IRegisterPropertyListener`：过滤/依赖字段事件
- `BeforeF7SelectListener` 是普通基础资料字段的监听器；列表过滤容器走已有 `filterContainerBeforeF7Select(BeforeFilterF7SelectEvent)` 回调，不混用两个参数类型。

## 核心事件

- `filterContainerInit`：// 初始化或搜索时重建过滤面板，可添加/修改字段定义；可能多次触发
- `beforeCreateListColumns`：// 创建列定义前，可添加/修改列信息
- `beforeCreateListDataProvider`：// 创建取数器前，可自定义取数逻辑
- `setFilter`：// 查询前调整过滤条件
- `filterContainerSearchClick`：// 用户点击查询或修改快捷过滤时触发
- `filterContainerAfterSearchClick`：// 过滤条件解析完毕后联动处理
- `filterContainerBeforeF7Select`：// 过滤容器 F7（基础资料/引用数据选择控件）弹出前拦截
- `filterColumnSetFilter`：// 基础资料过滤字段条件调整
- `baseDataColumnDependFieldSet`：// 设置常用过滤依赖字段
- `beforeItemClick`：// 菜单按钮点击前触发
- `itemClick`：// 菜单按钮点击时触发
- `billListHyperLinkClick`：// 点击超链接单元格时触发
- `beforeShowBill`：// 打开单据维护界面前触发
- `billClosedCallBack`：// 单据维护界面关闭返回时触发
- `listRowClick`：// 列表行点击时触发
- `listRowDoubleClick`：// 列表行双击时触发
- `setCellFieldValue`：// 设置单元格指令时触发
- `setPluginName`：// 界面显示前触发
- `preOpenForm`：// 界面打开前触发
- `loadCustomControlMetas`：// 自定义控件元数据加载时触发
- `setView`：// 视图注入时触发
- `initialize`：// 初始化时触发
- `registerListener`：// 注册监听时触发
- `beforeBindData`：// 绑定前触发
- `afterBindData`：// 绑定后触发

## 插件内上下文方法

### 过滤容器操作

参数为 `kd.bos.form.events.FilterContainerInitArgs` / `FilterContainerSearchClickArgs`；过滤字段类为 `kd.bos.filter.FilterColumn`，比较枚举为 `kd.bos.entity.filter.CompareTypeEnum`。下面是对应事件中的 API 片段，字段必须来自当前列表实际元数据。

```java
// filterContainerInit：添加字段定义；仅在当前定义中缺少时添加。
FilterColumn filterColumn = args.getFilterColumn("datefield");
if (filterColumn == null) {
    filterColumn = new FilterColumn("datefield");
    args.addFilterColumn(filterColumn);
}
// 默认值属于首次初始化逻辑，需由插件自己的标志控制，避免搜索时重置用户条件。
```

`filterColumn.setDefaultValues("2019-1-30", "2019-1-31")` 为真实 API，但只在业务明确的首次初始化分支执行。快捷、常用和方案过滤分别核对实际字段定义；不要把事件名中的 Init 理解成只执行一次。

```java
// filterContainerSearchClick：先按字段实际类型解释 Object，不直接赋给 String。
Object filterValue = args.getFilterValue("datefield");
List<Map<String, List<Object>>> fastFilters = args.getFastFilterValues();

// 调整面板条件配置：这里的操作符是 CompareTypeEnum。
args.addFilter("textfield", CompareTypeEnum.EQUAL, "123");
args.addFastFilter("textfield", "searchValue");

// 主组织 ID 是 Long 列表，不是 String 集合。
List<Long> mainOrgIds = args.getSelectMainOrgIds();
```

构造 ORM 条件用 `new QFilter("textfield", QFilter.equals, "123")`；它的操作符是字符串。不能把 `QFilter` 当作 `args.addFilter` 的第二参。`getQFilter(String)` 在本地 7.0 仍存在，但已标记弃用；维护旧代码时可识别其能力，新逻辑按真实过滤配置或查询事件合同处理，不能凭方法名虚构替代入口。

### 列定义操作
```java
// beforeCreateListColumns 中修改列定义
ComboListColumn comboColumn = new ComboListColumn();
comboColumn.setListFieldKey("combofield");

MergeListColumn mergeColumn = new MergeListColumn();
mergeColumn.setKey("mergecolumn");
mergeColumn.getItems().add(comboColumn);

beforecreatelistcolumnsargs.addListColumn(mergeColumn);
```

### 行点击操作
```java
// kd.bos.list.events.ListRowClickEvent
// kd.bos.entity.datamodel.ListSelectedRow
@Override
public void listRowClick(ListRowClickEvent e) {
    ListSelectedRow row = e.getCurrentListSelectedRow();
    if (row == null) return;
    Object billId = row.getPrimaryKeyValue();
    // 按目标主键类型处理当前点击行
}

@Override
public void listRowDoubleClick(ListRowClickEvent e) {
    ListSelectedRow row = e.getCurrentListSelectedRow();
    if (row == null) return;
    Object billId = row.getPrimaryKeyValue();
    // 按任务需要打开单据；不要把主键强制转成 String
}
```

[V7.0.1 ListRowClickEvent](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/list/events/ListRowClickEvent.html) 区分当前点击行 `getCurrentListSelectedRow()` 与选择集合 `getListSelectedRowCollection()`；两者不能互换。事件不提供完整 `DynamicObject` 数据包，不按不存在的 `getDataEntity()` 取字段；其他字段按列表实际提供的列数据或明确的加载需求处理。

## 示例代码

示例代码统一维护在模板文件中，直接参考：

- [ListPluginTemplate.java](../../../assets/ListPluginTemplate.java)

## 实践建议

1. **过滤定制优先用 filterContainerInit + filterContainerAfterSearchClick**
   - 在 init 中定义字段
   - 在 afterSearchClick 中处理联动

2. **避免在逐行处理链路中查库**
   - 大数据量场景性能问题
   - 应在 beforeCreateListDataProvider 或 setFilter 中提前准备数据

3. **包装列表数据时保护基础资料缓存对象**
   - `beforePackageData` 或自定义取数中，不要直接修改已加载基础资料对象的名称等原有属性；这可能污染缓存并影响其他引用方。
   - 仅为本列表展示的派生值放入独立展示字段，按目标事件与数据包合同赋值；不能通过改基础资料对象实现临时展示。

4. **行点击与菜单项点击分离**
   - 行点击处理用 listRowClick
   - 菜单按钮用 itemClick
   - 避免混淆

5. **单据打开回调用 billClosedCallBack**
   - 不要在打开前后分散写逻辑
   - 统一由 billClosedCallBack 处理返回

## 常见坑位

### ❌ 将查询投影与缓存对象修改混为一谈

增加 `org.name` 等查询列与对基础资料对象调用赋值方法是两种行为，不能仅凭查询列包含基础资料属性就判定破坏缓存。先确认代码修改的是查询定义、独立展示数据，还是共享的基础资料对象。

`beforeCreateListDataProvider` 用于创建或替换列表数据提供者；本地 Cosmic V8.0.1 SDK 索引中的 `kd.bos.form.events.BeforeCreateListDataProviderArgs` 提供 `getListDataProvider` / `setListDataProvider`，不能据此编造 `args.getQueryStatement()` 调用。目标项目的查询扩展方式仍按实际依赖核验，不用索引版本替代目标版本。

缓存污染风险发生在实际修改共享基础资料对象的原有属性时，尤其要检查 `beforePackageData` 与自定义取数中的对象赋值；把同一赋值换到另一个事件不能证明问题已解决。核验修改对象及其他引用方是否受影响，同时保留正常取数和独立展示字段能力。

来源：[列表常见问题排查](https://vip.kingdee.com/knowledge/324953160731165184)，更新 2026-07-30 12:06；正文未声明完整补丁适用范围。SDK 索引只确认该版本签名，不等于目标环境运行验证。

### ❌ beforeItemClick 与 itemClick 逻辑混用
```java
// 错误：重复执行
@Override
public void beforeItemClick(ItemClickEvent e) {
    // 在此修改单据状态  
}

@Override
public void itemClick(ItemClickEvent e) {
    // 在此又修改了同样的状态  → 重复！
}

// 正确：职责分离
beforeItemClick → 检查权限、校验
itemClick → 执行操作
```

### ❌ 逐行处理链路中循环查库
```java
// 错误：性能灾难
for (每一行) {
    queryDatabase();  // ❌ 10000 行数据 = 10000 次查询
}

// 正确：提前准备数据
@Override
public void beforeCreateListDataProvider(...) {
    // 一次查询获取所有需要的数据
    Map<String, Object> dataCache = queryAllDataOnce();
    // 后续逐行逻辑直接从缓存取值
}
```

### ❌ 把原生空实现当作过滤提交开关

本地 7.0 的 `AbstractListPlugin.filterContainerSearchClick` 是空实现；过滤配置由参数对象修改，不能声称“漏调 super 就丢失过滤”。继承项目 Ext 或其他业务插件时，父类可能有实际逻辑，应按该继承链保留调用。官方示例中的 `super` 调用本身不是必须调用的语义证明。

### ❌ listRowClick 中修改列表数据
- 行点击时不要直接修改数据源
- 应该打开编辑界面或触发操作，而非在列表里直接改

### ❌ 吞掉超链接处理异常

先确定失败应在当前入口转成业务提示，还是向上交给平台处理；不要以“防止列表崩溃”为由加入空 `catch (Exception)`。确需包装异常时保留原因和可理解的失败信息，避免把失败返回成成功。

## 过滤与列定义依据

- [过滤初始化](https://vip.kingdee.com/knowledge/223887352173535232)，2025-05-10 15:35：初始化和搜索均可能触发；可调整三类过滤字段及默认值。
- [搜索条件事件](https://vip.kingdee.com/knowledge/224130102366893824)，2026-07-31 12:07：先修改面板配置，再由系统生成取数条件。
- [列构建事件](https://vip.kingdee.com/knowledge/224120361749421824)，2024-04-22 15:02：动态增删列，保留 `addListColumn` / `setListFieldKey` 等能力。

上述正文未声明精确 SDK 版本。过滤返回类型、操作符和父类行为另经实际 7.0 JAR 核验；原列定义块在同一目标下编译通过，未因只查子类而删掉继承方法。编译不代表目标列表的 UI、权限过滤或用户交互已验收。
