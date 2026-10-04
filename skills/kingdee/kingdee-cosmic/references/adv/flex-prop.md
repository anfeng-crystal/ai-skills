# 弹性域自动解析工具 (FlexPropUtils)

详细知识、官方来源与验证边界：[云端专题](https://chatgpt.com/space/page_0f91e47d48d881918717a54ee9dace3b)。

## TL;DR
- 适用：在具有该 commons 包装的项目中，把弹性域 ID 批量解析成结构化键值。
- 先抓：先确认 `FlexType`，再用 `FlexPropUtils` 做批量解析和结果映射。
- 跳转：普通字段/基础资料引用不要停在本页，分别去元数据或基础资料查询路径。
- 继续读全文：当你要处理多行分录弹性域、批量解析或配置加载方式时。

## 概述
弹性域按主基础资料启用不同维度，单据字段引用弹性域记录，读取值为 `DynamicObject`，参见[官方字段模型](https://vip.kingdee.com/knowledge/255615264455676160)。`kd.cd.common.util.FlexPropUtils` 是项目 commons 包装；下列合同核对自 `kd-cd-cosmic-commons` **RELEASE-26-0424**，不能当作所有苍穹版本的原生 SDK 合同。跨项目使用先确认依赖和字段映射。

> **适用边界**
> ✅ 适用：弹性域 ID 解析为结构化键值对。
> ❌ 不适用：普通实体字段读取请用 `entity-metadata.md`；基础资料引用请用 `BaseDataServiceHelper`。

## 核心类
- **`kd.cd.common.util.FlexPropUtils`**: **弹性域处理核心工具类**。
- **`kd.cd.common.util.FlexType`**: 弹性域类型枚举。

## FlexType 枚举
弹性域类型决定了字段映射关系的来源：
- **`ACT`**: 核算维度
- **`AUX`**: 辅助属性

该构件中 ACT 查询 `gl_assist.assvals`，AUX 查询 `bd_flexauxprop.value`。两枚举不是平台全部弹性域类型。

## 常用 API 方法

### 1. 弹性域自动解析
- `Map<String, Object> parseSingle(DynamicObject flexEntity, FlexType flexType)`：解析单个实体，按其主键提取内层映射。
- `Map<Object, Map<String, Object>> parse(Collection<DynamicObject> flexEntities, FlexType flexType)`：解析对象集合，外层按主键分组。
- `Map<Object, Map<String, Object>> parseByFlexIds(Collection<Object> flexIds, FlexType flexType)`：查询已有弹性域 ID 后解析，外层按查询行主键分组。

### 2. 查询方法
- `Map<Object, String> queryJsonByFlexIds(Collection<Object> flexIds, FlexType flexType)`：返回主键到 JSON 字符串的映射，JSON 字段由 ACT/AUX 决定。

### 3. 配置加载
- `Map<String, String> loadFieldRelationAsMap(FlexType flexType)`：加载配置 **`flexfield` → `valuesource.number`**，不是反向映射。

### 调用合同
- 五个方法均为 `public static`。解析后的内层键为 `valuesource.number`，值保留 JSON 反序列化结果，不自动加载基础资料对象或显示名称；没有配置映射的 JSON 键会被忽略。
- `parseSingle` / `parse` 固定读取对象的 `value` JSON 字段，不按 ACT 自动改读 `assvals`。直接传实体前确认字段已加载；ACT 通常选用按 ID 的入口，不能假定任意 ACT 对象满足直接解析前提。
- 三个集合入口收到 null 或空集合时直接返回空 Map；`parseSingle(null, ...)` 及 `parse` 的 null 行没有保护。`parse` 跳过 PK 为 null 的行，`parseSingle` 的空 PK 在配置加载成功后返回 null。
- 非空 ID 集合中的 null、空字符串或无效 ID 不会被包装逐项过滤；调用方先按目标主键合同校验。非空输入还要求非 null 的 `FlexType`，查询、配置与缓存访问可能失败。
- 区分外层缺少 ID（未查到）与内层空 Map（如 JSON 空白、JSON 解析异常或没有匹配项）。空 Map 不能证明数据完整；重复主键或重复映射结果键会覆盖，不会自动合并。

## 示例代码

以下完整类保留单实体、批量、分录三种场景。`flex_field`、`entry` 是示例字段；`flex_color` / `flex_size` 必须替换为实际配置的 **`valuesource.number`**。输入 ID 应是同一类型下已确认有效的主键；示例只过滤 null，不替代业务主键校验。

```java
package kd.cd.common.demo;

import kd.cd.common.util.FlexPropUtils;
import kd.cd.common.util.FlexType;
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.dataentity.entity.DynamicObjectCollection;
import java.util.Map;
import java.util.Collection;
import java.util.HashSet;
import java.util.Set;

public class FlexDemo {
    // 单实体：AUX 对象须已加载 value JSON 字段。
    public void demo(DynamicObject bill) {
        if (bill == null) {
            return;
        }
        DynamicObject flexEntity = bill.getDynamicObject("flex_field");
        if (flexEntity == null || flexEntity.getPkValue() == null) {
            return;
        }

        Map<String, Object> values = FlexPropUtils.parseSingle(flexEntity, FlexType.AUX);
        if (values == null || values.isEmpty()) {
            return;
        }
        // 按值来源编码取值，结果不是已加载的基础资料对象。
        Object color = values.get("flex_color");
        Object size = values.get("flex_size");
    }

    // 批量：过滤 null 后一次解析，避免逐条查询。
    public void batchDemo(Collection<Object> flexIds) {
        if (flexIds == null || flexIds.isEmpty()) {
            return;
        }
        Set<Object> ids = new HashSet<>(flexIds);
        ids.remove(null);
        Map<Object, Map<String, Object>> result =
                FlexPropUtils.parseByFlexIds(ids, FlexType.AUX);
        for (Map.Entry<Object, Map<String, Object>> entry : result.entrySet()) {
            Object flexId = entry.getKey();
            Map<String, Object> fieldValues = entry.getValue();
            Object color = fieldValues.get("flex_color");
        }
    }

    // 分录：先收集 ID，再统一解析，最后匹配各行。
    public void extractFromEntry(DynamicObject bill) {
        if (bill == null) {
            return;
        }
        DynamicObjectCollection entries = bill.getDynamicObjectCollection("entry");
        if (entries == null || entries.isEmpty()) {
            return;
        }
        Set<Object> flexIds = new HashSet<>();
        for (DynamicObject entry : entries) {
            DynamicObject flex = entry == null ? null : entry.getDynamicObject("flex_field");
            if (flex != null && flex.getPkValue() != null) {
                flexIds.add(flex.getPkValue());
            }
        }
        Map<Object, Map<String, Object>> flexValues =
                FlexPropUtils.parseByFlexIds(flexIds, FlexType.AUX);
        for (DynamicObject entry : entries) {
            DynamicObject flex = entry == null ? null : entry.getDynamicObject("flex_field");
            if (flex == null || flex.getPkValue() == null) {
                continue;
            }
            Map<String, Object> values = flexValues.get(flex.getPkValue());
            if (values != null && !values.isEmpty()) {
                // 在此使用解析值；必要时另行按基础资料合同解析显示信息。
            }
        }
    }
}
```

## 实践建议
1. **按配置解析**：优先复用当前映射，避免把动态维度与物理字段关系写死。直接读取已确认元数据中的字段路径并非平台禁用能力；读取前确认字段、加载范围和用途。
2. **区分 FlexType**: 当前 commons 中内置的类型为 `ACT`（核算维度）与 `AUX`（辅助属性），调用前必须确认所属类型。
3. **批量处理性能**: 在分录处理逻辑中，建议收集所有弹性域 ID 后统一调用 `parseByFlexIds` 一次性完成转换。
4. **空值判断**：按上面的调用合同分别处理空输入、缺记录与空解析结果；对象直接解析不保证 null 安全。

## 常见坑位
1. **缓存层次**：此构件的映射加载经过 `ThreadCache.get(key, loader)` 和 `BusinessDataServiceHelper.loadFromCache`。包装及所核对的 7.0 ThreadCache 无固定十分钟 TTL 依据，不能承诺等待十分钟即刷新，也不能据此断言底层缓存无过期机制。发布后结果未更新时先核配置和具体缓存层；刷新动作另按环境授权处理。
2. **字段前提**：对象有主键不代表已加载 `value`；只持有 ID 时使用 `parseByFlexIds`，不要把对象解析当作自动补载。
3. **字段重复**: 不同类型的弹性域可能包含相同标识的字段，调用时必须确认 `FlexType`。
4. **返回类型变化**: `parseSingle` 方法实际是从 `parse` 返回的 Map 中提取对应主键的值，注意返回类型是 `Map<String, Object>`。
