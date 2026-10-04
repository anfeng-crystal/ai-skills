# 单据转换与下推 (BotpUtils & PushResult)

工具包证据、分单场景和验证边界见 [云端知识：单据转换与多目标结果](https://chatgpt.com/space/page_3c45abfff804819194126ee8f805cfcf)；本页保留执行合同和示例。

## TL;DR
- 适用：下推、选单、来源追踪和转换结果处理。
- 先抓：目标项目已引入并核验 `BotpUtils` / `PushResult` 时优先复用；缺少工具包时核对目标原生转换 API。
- 跳转：只是保存/提交/审核改读 `operate-chain.md`；只是转换插件事件再读 `base/plugin/plugin-botp.md`。
- 继续读全文：当你要确认上拉、链路追踪或后台自动下推模板时。

## 概述
单据下推（Push）与转换（Convert）是苍穹实现业务流转（如订单下推入库）的核心机制。`BotpUtils` (位于 `kd.cd.common.util`) 对原生的转换服务进行了深度简化，支持一键下推并保存、下推并显示界面、上拉数据以及多层级的正/反向链路追踪。

`BotpUtils` / `PushResult` 来自项目引入的 `kd.cd.common` 工具包（可位于 `cus`），不是所有苍穹环境默认提供的标准 SDK。使用前确认目标依赖中实际存在的工具包、版本和签名；不能仅凭包名推定平台自带。

> **适用边界**
> ✅ 适用：下推/选单/来源追踪/转换结果处理。
> ❌ 不适用：单纯的操作执行（保存/审核）请用 `OpUtils`；转换插件的事件扩展请用 `ConvertPlugInTemplate`。

## 核心类
- **`kd.cd.common.util.BotpUtils`**: **下推核心工具类**。
- **`kd.cd.common.util.PushResult`**: 下推结果封装对象，可通过 `getPks()`、`getDatapacks()`、`getSingleDataPack()` 获取结果，并通过 `failThenThrow()` 直接抛出失败详情。
- **`kd.bos.entity.botp.runtime.ConvertOperationResult`**: 原生转换结果。

## 常用 API 方法

### 1. 下推操作 (BotpUtils)
单个 `srcPkValue` 限定源单选择，不保证只生成一张目标单；目标数量仍取决于转换规则的分单策略和实际结果。

- `pushAndSave(String sourceEntityId, String targetEntityId, Object srcPkValue, String ruleId)`: 单源后台下推并自动保存的简版重载。
- `pushAndSave(String sourceEntityId, String targetEntityId, Object srcPkValue, Map<String, List<Long>> entryMapping, String ruleId, Consumer<PushArgs> consumer)`: **最常用**。单源后台下推并自动保存。
- `pushNoSave(String sourceEntityId, String targetEntityId, Object srcPkValue, String ruleId)`: 单源后台下推但不保存的简版重载。
- `pushNoSave(String sourceEntityId, String targetEntityId, Object srcPkValue, Map<String, List<Long>> entryMapping, String ruleId, Consumer<PushArgs> consumer)`: 下推生成内存对象，不持久化。
- `push(boolean autoSave, String sourceEntityId, String targetEntityId, List<ListSelectedRow> selectedRows, String ruleId, Consumer<PushArgs> consumer)`: 基于 `selectedRows` 的通用下推入口。
- `push(boolean autoSave, PushArgs pushArgs)`: 通用下推方法。
- `pushAndShowTarget(IFormView view, boolean autoSave, String sourceEntityId, String targetEntityId, List<ListSelectedRow> selectedRows, String ruleId, Consumer<PushArgs> consumer)`: 按选择行下推并直接打开目标单。
- `pushAndShowTarget(IFormView view, boolean autoSave, PushArgs pushArgs)`: 下推并直接在界面弹出目的单。

### 2. 上拉操作 (BotpUtils)
- `drawToBill(IFormView view, String sourceEntityId, Collection<ListSelectedRow> selectRows, String ruleId, Consumer<DrawArgs> consumer)`: 下拉数据至当前单据。

### 3. 链路追踪 (BotpUtils)
- `findAllTargetBills(String targetEntityId, String entityId, Collection<Long> pkValues)`: 正向查找生成的全量目的单，按当前单据主键分组。
- `findAllTargetBillsFlat(String targetEntityId, String entityId, Collection<Long> pkValues)`: 正向查找，不分组。
- `findAllSourceBills(String sourceEntityId, String entityId, Collection<Long> pkValues)`: 反向查找来源单据，按当前单据主键分组。
- `findAllSourceBillsFlat(String sourceEntityId, String entityId, Collection<Long> pkValues)`: 反向查找，不分组。
- `findDirectTargetBills(String targetEntityId, String entityId, Collection<Long> pkValues)`: 查找直接下游（第一层）。
- `findDirectSourceBills(String sourceEntityId, String entityId, Collection<Long> pkValues)`: 查找直接上游（第一层）。

### 4. 辅助方法
- `loadTargetEntities(ConvertOperationResult result)`: 从下推结果中加载完整的目的单 DynamicObject。
- `getConvertFailMsg(ConvertOperationResult result)`: 获取下推失败信息详情。
- `getDefaultRuleId(String sourceEntityId, String targetEntityId)`: 获取默认转换规则ID（启用状态）。
- `buildSelectedRows(Map<Object, Map<String, List<Long>>> billData)`: 构建下推选择行信息。
- `PushResult.failThenThrow()`: 下推失败时直接抛出 `PushConvertFailureException`。
- `PushResult.getDatapacks()`: 获取目标单数据包；自动保存场景下会懒加载。
- `PushResult.getSingleDataPack()`: 返回数据包首项，无数据包时返回 `null`，不检查结果是否唯一。`failThenThrow()` 也不验证目标数量。

## 示例代码

### 后台自动下推模板
```java
package kd.cd.common.demo;

import kd.cd.common.util.BotpUtils;
import kd.cd.common.util.PushResult;

public class PushDemo {
    public Object[] autoPush(String sourceFormId, String targetFormId, Object sourcePk) {
        // 1. 下推并保存
        PushResult result = BotpUtils.pushAndSave(sourceFormId, targetFormId, sourcePk, null);
        result.failThenThrow();

        // 2. 返回全部已保存目标主键，由调用方处理完整结果
        return result.getPks();
    }
}
```

需要完整数据包时调用 `result.getDatapacks()` 并处理全部元素。只有业务明确要求唯一目标时，才先验证数量，再读取单张：

```java
DynamicObject[] targets = result.getDatapacks();
if (targets == null || targets.length != 1) {
    throw new IllegalStateException("预期唯一目标单，请核对已生成的完整结果");
}
DynamicObject target = targets[0];
```

`DynamicObject` 的完整类名为 `kd.bos.dataentity.entity.DynamicObject`。`pushAndSave` 已执行保存；后续数量校验失败不表示未保存，不能据此盲目重新下推。

### 链路追踪示例
```java
public void traceBills(String entityId, Collection<Long> pkValues) {
    // 查询所有下游目标单（按当前单据主键分组）
    Map<Long, Map<String, Set<Long>>> targetBills = BotpUtils.findAllTargetBills(entityId, pkValues);

    // 查询特定类型的直接上游源单
    Map<Long, Set<Long>> sourceBills = BotpUtils.findDirectSourceBills("pm_purorderbill", entityId, pkValues);
}
```

## 实践建议
1. **RuleId 获取**: 建议通过 `BotpUtils.getDefaultRuleId` 获取单据间的默认规则，避免硬编码。
2. **分录下推**: 使用 `entryMapping` 参数可精确控制需要下推的分录行。
3. **加载明细**: `loadTargetEntities` 获取的对象包含分录的全量数据。
4. **链路追踪**: 使用 `findDirectXxx` 方法仅查询直接关联，`findAllXxx` 方法递归查询全量关联。

## 常见坑位
1. **规则未分配**: 如果返回空结果，优先检查"转换规则"是否在目标组织中已发布。
2. **分录转换缺失**: 如果 RuleId 中未配置分录，下推后的单据将只有表头。
3. **主键精度丢失**: `Object` 类型的 ID 在跨系统传递时需注意 JS 的数字精度限制（Long -> String）。
4. **参数顺序**: 注意 pushAndSave/pushNoSave 的参数顺序是 `(sourceEntityId, targetEntityId, ...)` 而非旧版的 `(targetId, ruleId, sourceIds, orgId)`。
