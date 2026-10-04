# 动态对象与项目包装 DynamicObjectUtils

详细知识与证据边界见 [云端动态对象知识](https://chatgpt.com/space/page_6dc95317103c8191a16c59507f9dfa31)。

## 适用范围

`DynamicObject` 是内存数据包；`kd.cd.common.util.DynamicObjectUtils` 是项目包装，不能假定所有苍穹工程都有它。以下包装合同核于 `kd-cd-cosmic-commons` 的 `RELEASE-26-0424`（manifest 声明 `Cosmic-Version: 7.0+`）及本机 7.0 依赖（dataentity/ormengine manifest 为 `hotfix_7.0.16_20250730`）；其他版本先核实际依赖。项目已提供时复用，缺少时用[原生 DynamicObject 合同](../base/sdk/sdk-dynamic-object.md)。

字段结构与类型读[实体元数据](entity-metadata.md)，查询取数读[查询与 DataSet](query-dataset.md)。工具名中的 safe/nullSafe 不代表字段、路径、类型和业务空值都经过校验。

## 已核包装方法

| 能力 | 方法与返回值 | 执行边界 |
|---|---|---|
| 取值 | `<T> T safeGetValue(DynamicObject, String)` | 对象为 null 或当前属性不存在时返回 null；存在时仍调用原生 `get`，不保证保留原始 null，也不校验调用方的泛型类型。 |
| 条件写 | `void safeSetValue(DynamicObject, String, Object)` | 对象为 null 或当前属性不存在时不写；不会新增字段，存在时仍调用原生 `set`。 |
| 根对象空值保护 | `<T> T nullSafeGet(DynamicObject, String)` | 只保护根对象为 null；其余直接 `get(field)`。缺字段、路径和类型问题仍按原生行为处理。 |
| 主键与属性检查 | `<T> T getPkValue(DynamicObject)`；`boolean containsKey(DynamicObject / DynamicObjectCollection, String)` | 主键优先取原生 PK，null 时再安全读取 `id`。主键类型按实际模型确认，不统一假设为 Long。 |
| 深路径提取 | `<T> Set<T> flatSetOf(DynamicObject, String)`；`<T> List<T> flatListOf(...)` | 如 `entry.subentry.field`；根对象不得为 null、表达式不得为空，路径各层必须符合实际模型。遍历真实对象/集合，不验证任意输入路径。 |
| 批量提取 | `Object[] arrayOfIds(...)`；`<T> Set<T> setOfIds(...)`、`setOf(..., String)`；`<T> List<T> listOf(..., String)` | 均有 `DynamicObject[]` 与 `Collection<DynamicObject>` 重载；按真实字段/路径和类型提取，Set 去重，List 保留列表结果。 |
| 汇总 | `BigDecimal sumOf(Collection<DynamicObject>, String)` | 空集合返回零；非空时逐行 `getBigDecimal` 再相加，不自动跳过可空金额。先明确 null 的业务规则。 |
| 转 DataSet | `DataSet toDataSet(DynamicObjectCollection)`；`DataSet toDataSet(DynamicObjectCollection, String...)` | 根据集合类型中的现有属性取列；先核选择字段，不能靠转换创建缺失字段。调用方管理 DataSet 生命周期，无性能保证。 |
| 转对象集合 | `DynamicObjectCollection fromDataSet(DataSet)` | 委托 `ORM.create().toPlainDynamicObjectCollection`；不能据此承诺还原原单据模型、分录关系或保存语义。 |
| 序列化 | `String serialize(DynamicObject...)`；`DynamicObject[] deSerialize(String, DynamicObjectType)` | 序列化以首个对象的类型为依据；反序列化要求类型非 null。跨进程/缓存使用还须验证模型、版本、数据规模与敏感字段边界。 |
| 创建 | `DynamicObject newDynamicObject(String)`；`newDynamicObject(DynamicObjectType)` | 前者通过表单标识查主实体类型，依赖平台元数据；后者用已知类型创建实例。都不等于保存单据。 |
| 克隆 | `DynamicObject clone(DynamicObject)` | 本版包装配置 `new CloneUtils(false, true)`，启用清主键。需另行核关系对象及业务编号的复制策略，不能将所有引用一概视为独立深拷贝。 |
| 属性信息 | `List<String> getPropKeys(DynamicObject / DynamicObjectCollection)`；`Map<String, Object> dump(DynamicObject)` | 属性标识返回 List。dump 是内容转储，不承诺不可变深拷贝或自动脱敏。 |
| 状态 | `boolean isNewCreate(DynamicObject)`；`void clearDirty(DynamicObject / DynamicObjectCollection)` | 前者仅取反内存 `fromDatabase` 标记；后者委托 ORMUtil 修改状态。两者都不是数据库是否存在记录的证明。 |

## 示例：明确字段与空金额规则

下例假设已核实 `org.name`、`billentry.amount` 和 `billentry.material.id` 的真实模型及加载字段。金额规则示例选择“遇 null 拒绝汇总”；若业务允许 null 按零处理，应显式实现该规则，不能认为 `sumOf` 已处理。完整类可按当前依赖编译，字段名称需替换为项目真实标识。

```java
package kd.cd.common.demo;

import java.math.BigDecimal;
import java.util.Set;
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.dataentity.entity.DynamicObjectCollection;
import kd.cd.common.util.DynamicObjectUtils;

public final class DataDemo {
    public String orgName(DynamicObject bill) {
        if (bill == null) return null;
        DynamicObject org = bill.getDynamicObject("org");
        return org == null ? null : org.getString("name");
    }

    public BigDecimal totalAmount(DynamicObject bill) {
        if (bill == null) throw new IllegalArgumentException("bill is required");
        DynamicObjectCollection rows = bill.getDynamicObjectCollection("billentry");
        if (rows == null) throw new IllegalStateException("billentry was not loaded");
        for (DynamicObject row : rows) {
            if (row.getBigDecimal("amount", true) == null) {
                throw new IllegalStateException("amount is required for this calculation");
            }
        }
        return DynamicObjectUtils.sumOf(rows, "amount");
    }

    public Set<Object> materialIds(DynamicObject bill) {
        if (bill == null) throw new IllegalArgumentException("bill is required");
        return DynamicObjectUtils.flatSetOf(bill, "billentry.material.id");
    }
}
```

## 状态、引用与字段约束

- `clearDirty` 不是绕过操作插件的开关。本机 ORMUtil 实现会递归调整 dirty/fromDatabase 等状态；不得为了跳过校验或业务操作随意清理。内存修改、页面模型联动和正式保存分别遵循各自合同。
- `isNewCreate` 只能用于已知数据包状态的判断；手动修改状态即可改变结果，不能据此断言“从未保存”或“数据库中已存在”。
- 集合 `clear()` 使指向同一集合的引用看到空集合；已取出的行对象引用仍指向该对象，不会自动变成 null。是否删除持久化分录或刷新界面另核对应流程。
- 克隆清主键不等于完成新增业务对象初始化；是否恢复主键、业务编号、引用和状态须按明确的新增/更新用途决定，不能把手动设 PK 当作通用保存方案。
- 数值的 null、零、默认值以及缺字段不同；按[原生数据包合同](../base/sdk/sdk-dynamic-object.md)处理。元数据缓存中的主实体模型不能原地修改；需要自定义内存类型时使用独立模型。
- 不得用 `safeSetValue` 吞掉虚构字段。仅有明确跨版本兼容需求且至少一个受支持环境真实存在该字段时才可条件写；否则先核外部值是查询参数还是持久化字段，再核精确编码体系与真实 F7/业务字段。
- 分录循环前批量提取需要的 ID，集中查询后在内存匹配；避免逐行查询。序列化和 DataSet 转换也应核容量、资源释放与目标版本，不由方法名称推断性能或可移植性。
