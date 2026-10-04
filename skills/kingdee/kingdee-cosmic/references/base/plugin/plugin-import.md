# 引入引出插件

详细知识、官方来源与验证边界：[云端专题](https://chatgpt.com/space/page_c407fa7b3e2081918882cb0de6cb322f)。


## TL;DR
- 适用：Excel 导入流程扩展，包括导入前校验、保存拦截、日志和结果加工。
- 先抓：`BatchImportPlugin` 和导入生命周期，不要套用普通表单插件思路。
- 跳转：普通 UI 插件或批量按钮逻辑不看本页；模板优先参考 `BatchImportPluginTemplate`。
- 继续读全文：当你要确认导入事件、上下文对象或失败处理扩展点时。

## 概述
引入引出插件用于扩展 Excel 导入流程，包括批量策略、保存拦截、数据校验与日志记录。

> **适用边界**
> ✅ 本文档是原生兜底：引入引出场景直接使用，无封装层。
> ❌ 普通表单插件的导入事件已在 `FormPluginTemplate` 中省略，因为有独立的 `BatchImportPluginTemplate`。

## 核心基类


- 基类：`kd.bos.form.plugin.impt.BatchImportPlugin`
- 继承关系：`BatchImportPlugin implements Callable<Object>, IImportDataPlugin`

## 核心事件

- `save(List<ImportBillData> rowdatas, ImportLogger logger)`：每批导入数据保存时进入，是最核心的校验与过滤拦截点。
- `getBatchImportSize()`：初始化批量导入策略时调用，用于确定批次大小。
- `isForceBatch()`：初始化导入模式时调用，用于决定是否强制批处理。

## 插件内上下文方法

- 行数据从 `ImportBillData.getData()` 取得，日志使用事件传入的 `ImportLogger`。
- 批次大小通过 `getBatchImportSize()` 配置；原生目标 7.0 基类没有 `getContext()`、`getLogger()`、`getBatchSize()`，不要由普通表单插件推演这些接口。
- `refreshHeartbeat()` 是任务心跳方法，`call()` 是框架任务入口；不是业务事件，也不要在 `save` 中递归调用 `call()`。

```java
Map<String, Object> billData = data.getData();
// 移除一张不合格单据前，记录原始行号与该单据覆盖的物理行数。
logger.log(data.getStartIndex(), "错误信息").fail();
logger.signTotalRow(data.getEndIndex() - data.getStartIndex() + 1);
// 在迭代器中移除该单据，完成本批筛选后，再 return super.save(rowdatas, logger)。
```

## 其他扩展点

- `beforeSave(...)`：保存前批次预校验；目标 7.0 默认实现还执行平台无效单据过滤，覆盖时保留对应父类处理。
- `resolveExcel()`：Excel 解析扩展。
- `importData()`：导入主流程扩展。
- `getDefaultImportType()` / `getDefaultKeyFields()`：默认导入配置扩展。

## 示例代码

示例代码统一维护在模板文件中，直接参考：

- [BatchImportPluginTemplate.java](../../../assets/BatchImportPluginTemplate.java)

## 实践建议

1. 导入校验优先集中在 `save(...)`。
2. 大数据量场景要明确 `getBatchImportSize()` 和 `isForceBatch()`。
3. 自定义移除失败单据时，先按 `getStartIndex()` 记录失败，再以 `getEndIndex() - getStartIndex() + 1` 调用 `signTotalRow`；不能把导入批次重排后的序号当 Excel 原行号。保留行范围，否则被移除单据不会进入后续默认结果统计。
4. `super.save(...)` 会执行实际保存。先校验并过滤，再调用一次并原样返回结果；不能先调用它再删非法行，也不能丢弃结果后返回 `null`。
5. 本地 7.0 的默认 `save` 对空批直接返回 `null`，`buildResult` 跳过该结果；这个 `null` 不表示框架将再次默认保存。全部被拒绝时由前面逐单日志说明原因，模板继续调用默认保存方法让它处理空批。

## 常见坑位

- 用其他插件类型的上下文 getter 代替实际入参，或把框架任务入口当业务回调。
- 直接抛异常中断整批导入，导致可导入数据也丢失。
- 不记录失败日志，用户无法定位错误行。
- 批次过大导致内存抖动或请求超时。
## 依据与范围

[save 事件](https://vip.kingdee.com/knowledge/226286566404892160)（2026-07-31 12:00）展示先过滤再返回默认保存结果；正文 3.2 的“非暂存”描述与案例及代码相反，不照搬该句。[插件基类](https://vip.kingdee.com/knowledge/226283585832256256)（2024-04-17 20:53）说明批次、保存和导入主流程。两篇正文未标注精确 SDK 版本；上述调用顺序、空批和统计行为另由实际 7.0 JAR 核验。模板已做 Java 8 编译检查，未执行真实导入、WebAPI 保存或错误文件生成。
