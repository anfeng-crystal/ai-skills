# 实体元数据解析工具 EntityUtils

详细知识与证据边界见 [云端实体模型知识](https://chatgpt.com/space/page_520cd1d4ff3481918163501cd358a1e3)。

## 适用范围

用于解析实体标识、字段、分录与下拉元数据。`kd.cd.common.entity.EntityUtils` 是项目包装；先确认当前项目含该构件，不把它当成所有苍穹安装都有的原生 API。本页包装合同核于 `kd-cd-cosmic-commons` 的 `RELEASE-26-0424`（manifest 声明 `Cosmic-Version: 7.0+`），目标环境不同须核实际版本。

原生模型结构读[动态领域模型](../base/sdk/sdk-entity-model.md)，数据值读[动态对象](dynamic-object.md)，弹性域读[弹性域解析](flex-prop.md)。本页元数据方法通常涉及表单/实体缓存，不可因方法简短而当作无需平台环境的纯函数。

## 已核方法与边界

| 能力 | 方法 | 约束 |
|---|---|---|
| 标识映射 | `String getEntityId(String formId)` | 读取表单配置的 entityTypeId；不是按字符串猜数据库表名。区分 FormId、EntityId 与物理表。 |
| 主键/编号/状态 | `String getPrimaryKey(String)`、`getBillNoKey(String)`、`getBillStatusKey(String)`；`Pair<String,String> getPkAndBillnoKey(String)` | 主键方法直接取模型 PK 的 name，无 PK 模型不受其空值保护；编号/状态方法要求单据或基础资料类型，不假定所有表单都有这些字段。 |
| 属性检索 | `IDataEntityProperty getProperty(String, String)`、`getProperty(MainEntityType, String)`；`boolean containsProperty(String, String)` | 包装最终调用模型 `findProperty`。未找到不能单凭 null 诊断为“扩展未发布”；核目标模型、字段标识及运行时范围。 |
| 属性筛选 | `Map<String,IDataEntityProperty> getAllProperties(String)`、`selectProperties(String, Predicate<IDataEntityProperty>)` | 复制 `getAllFields` 结果到新 Map 后筛选；官方 V7.0.1 说明该结果不含系统字段，不把它当作全部模型属性。Map 中的属性对象仍不应作为可写模型副本。 |
| 分录字段 | `Set<String> getEntryPropKeys(String, String)`；`Map<String,IDataEntityProperty> getEntryProperties(String, String)` | 先按真实 entryKey 取分录模型，再读 fields；缺失或非分录类型不是可自动忽略的空分录。 |
| 属性路径 | `String getPropKeyWithPrefix(String, String)`、`getPropKeyWithPrefix(IDataEntityProperty)`；`String getParentPropKey(String, String)` | 属性重载沿所属模型父链补分录前缀，不含根实体名。字符串有点号时，只解析首段并原样追加剩余后缀；不是完整路径验证器。getParentPropKey 返回直接父模型名称。 |
| 下拉项 | `Map<String,String> getComboItemMap(String, String)` | 属性必须是 `ComboProp`，读取配置项“值→名称”；不等于任意状态字段或业务运行时过滤后的选项。 |
| 模型与表定义 | `MainEntityType getMainEntityType(String)`；`DynamicObjectType getDynamicObjectType(String)`、`getDynamicObjectType(String, String)`；`EntryType getEntryType(String, String)`、`getEntryType(MainEntityType, String)`；`TableDefine getTableDefine(String)` | 主模型通过 FormId→EntityId→实体缓存获取；选字段版本按逗号拆分并请求子模型。不要假定缓存模型包含当前界面动态注册的字段。 |
| 实体信息 | `String getChsName(String)`、`getAppId(String)`；`DBRoute getDBRoute(String)`；`String getBaseDataQuoteType(String, String)`；`Map<String,String> getLinkEntryRelation(String)` | 中文名读取 zh_CN 显示值；引用方法要求 `IBasedataField`，实际返回 baseEntityId。路由/关联信息按模型使用，不能据名称推断 SQL 或跨库权限。 |
| 别名状态 | `State getAliasState(String, String)` | 属性不存在时返回 negative；存在时用属性 alias（分录用 itemType.alias）构造 ok。它不查询数据库列是否存在、已发布或可用。 |
| 主键值判空 | `boolean isEmptyPk(Object)`、`isNotEmptyPk(Object)`；`void checkNotEmptyPk(Object, String)` | 只判断下面列出的值规则，不查询数据库；不支持的值类型会抛异常。 |
| 调试提取 | `<T> List<T> flatListValue(DynamicObject, String)`；`Object peek(Object)` | 保留扁平提取/结构预览能力；按已核模型使用，不将完整业务值直接打印到生产日志或当作自动脱敏结果。 |

## 主键判空不是持久化状态

本版 `isEmptyPk`：null、`Long` 的 0、空字符串返回 true；其他 Long 和非空字符串返回 false。空格字符串、字符串 `"0"`、负 Long 都属于非空；`Integer`、`BigDecimal` 等其他类型抛 `IllegalStateException`。`isNotEmptyPk` 取反；`checkNotEmptyPk` 在已支持类型判为空时抛 `IllegalArgumentException`。

主键类型、默认值和生成时机须按实际模型核定，不能统一断言为 0L。非空 PK 可能仅是预分配值；是否已保存、记录是否仍存在应使用对应操作结果或已授权查询证据，不能由值判空推导。

## 完整只读示例

`formId` 须是已核实的单据/基础资料表单；`comboKey` 须是真实 ComboProp，`entryKey`/`fieldKey` 按实际模型传入。此例返回诊断信息，不执行保存，也不诊断发布状态。

```java
package kd.cd.common.demo;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import kd.bos.dataentity.metadata.IDataEntityProperty;
import kd.cd.common.entity.EntityUtils;

public final class MetaDemo {
    public Map<String, Object> getInfo(String formId, String comboKey, Object pkValue) {
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("entityId", EntityUtils.getEntityId(formId));
        info.put("pkKey", EntityUtils.getPrimaryKey(formId));
        info.put("noKey", EntityUtils.getBillNoKey(formId));
        Map<String, String> items = EntityUtils.getComboItemMap(formId, comboKey);
        info.put("comboItems", items);
        info.put("chsName", EntityUtils.getChsName(formId));
        // 仅表示本包装的主键值判空结果，不代表是否入库。
        info.put("emptyPk", EntityUtils.isEmptyPk(pkValue));
        return info;
    }

    public Map<String, Object> analyzeEntry(String formId, String entryKey, String fieldKey) {
        Set<String> fieldKeys = EntityUtils.getEntryPropKeys(formId, entryKey);
        Map<String, IDataEntityProperty> properties = EntityUtils.getEntryProperties(formId, entryKey);
        IDataEntityProperty property = EntityUtils.getProperty(formId, fieldKey);
        if (property == null) throw new IllegalArgumentException("field not found in target model");
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("fieldKeys", fieldKeys);
        info.put("properties", properties);
        info.put("fullKey", EntityUtils.getPropKeyWithPrefix(property));
        return info;
    }
}
```

## 执行约束

- 通用单据/基础资料逻辑可复用模型的编号字段标识；先核表单类型及字段配置，不将包装用于所有表单。
- 频繁只读检查可在循环外获取一次模型并复用；缓存主实体模型及其属性不原地修改。当前页面动态字段使用当前运行时模型；修改模型时遵循[原生模型的副本与事件合同](../base/sdk/sdk-entity-model.md)。
- 字段找不到先区分错误实体/字段、查找范围、当前运行时模型与发布/缓存状态；返回 null 只说明本次未查到，不能直接确认某一个原因。
- 使用前缀结果前仍核完整路径；不要由输出字符串推断字段存在、基础资料扩展已生效或查询投影已加载。
