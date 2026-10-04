# 报表取数插件

## TL;DR
- 适用：报表取数插件，接管查询、动态列和 `DataSet` 返回。
- 先抓：`AbstractReportListDataPlugin` 的 `query`、列定义和树数据入口。
- 跳转：如果你改的是报表界面交互而不是数据源，去 `plugin-report-form.md`。
- 继续读全文：当你要写复杂取数、左树右表报表或自定义列定义时。

## 概述
报表取数插件用于接管报表列表的数据查询与列定义，适合复杂查询、自定义数据源、左树右表联动和动态列场景。

> **适用边界**
> ✅ 本文档直接使用：报表取数插件无封装层，直接参考本文档。

## 核心基类


- 基类：`kd.bos.entity.report.AbstractReportListDataPlugin`
- 挂载：报表设计器的【报表】→【报表列表】→【查询插件】。

## 核心事件

- `query(ReportQueryParam queryParam, Object selectedObj)`：报表查询入口，返回 `DataSet`。
- `getColumns(List<AbstractReportColumn> columns)`：调整显示列定义，控制隐藏、顺序、宽度、冻结等属性。

`query` 是抽象方法，直接实现取数，不调用 `super.query(...)`。`getColumns` 的基类实现直接返回入参；模板可直接处理并返回 `columns`，无需调用 `super.getColumns(...)`。输入可能含 `ReportColumnGroup`，修改字段列前先判断 `instanceof ReportColumn`，保留分组及其子列，不能将每个 `AbstractReportColumn` 强转为字段列。

依据：[官方报表取数插件帮助](https://vip.kingdee.com/knowledge/225993397708629504)、[官方报表界面插件帮助的列类型检查示例](https://vip.kingdee.com/knowledge/225997720761664000)，并已用本地 7.0 SDK 编译及混合列对象验证。帮助正文未声明最低适用版本；其他版本仍需核对目标 SDK。此验证未覆盖平台挂载、查询取数或导出。

## 插件内上下文方法

以下方法属于查询过程中的上下文访问能力，不建议当成“自动触发事件”处理：

- `getQueryParam()`：获取当前报表查询参数。
- `getSelectedObj()`：获取左树或左表当前选中对象。
- `setProgress(int)`：异步查询时回传进度。

```java
ReportQueryParam qp = this.getQueryParam();
Object selected = this.getSelectedObj();
this.setProgress(30);
```

## 其他扩展点

- `export(...)`：导出时复用或覆盖查询结果。
- `exportWithSheet(...)`：多 sheet 导出扩展。
- `queryBatchBy(...)`：分批查询扩展。
- `getDynamicColumns(...)`：动态列构造扩展。

## 示例代码

示例代码统一维护在模板文件中，直接参考：

- [ReportListDataPluginTemplate.java](../../../assets/ReportListDataPluginTemplate.java)

## 实践建议

1. `query` 只负责取数和必要聚合，格式化尽量放界面插件。
2. 左树右表场景优先使用 `selectedObj` 限定范围。
3. 大数据量异步查询时使用 `setProgress(int)` 反馈执行进度。
4. 列控制集中放在 `getColumns`，不要在 `query` 混入列逻辑。

## 常见坑位

- 把 `getQueryParam()`、`getSelectedObj()`、`setProgress(int)` 当成事件去写说明或示例。
- 忽略 `selectedObj`，导致左树右表点击节点后仍返回全量数据。
- `query` 返回空对象而不是合法 `DataSet`。
- 在 `query` 里逐行远程调用，导致报表超时。
