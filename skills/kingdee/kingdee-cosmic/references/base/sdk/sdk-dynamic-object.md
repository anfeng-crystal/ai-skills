# 动态领域模型 - 数据包 (DynamicObject)

## 适用与结构

`kd.bos.dataentity.entity.DynamicObject` 是按实体模型创建的数据包；简单属性存值，复杂属性存引用对象，集合属性通常为 `DynamicObjectCollection`。字段名称、类型和主子层级以当前模型为准。项目工具类已满足需求时，先读 [团队工具](../../adv/dynamic-object.md)，但工具封装也不能抹平“未填”“0”“缺字段”的业务区别。

## 原生 API

- `get(String)` / `set(String,Object)`：当前属性读写；`get` 也可能按属性类型和 `isEnableNull()` 转换，不能一概当作未经转换的原始值。
- `getString(String)` / `getLong(String)` / `getBigDecimal(String)`：类型化取值；其中 `getLong` 返回基本类型 `long`，不可能返回 `null`。
- `getBigDecimal(String, boolean enableNull)`：允许保留当前数值属性读取结果的空值；先确认该属性存在。`false` 仍会沿属性自身的空值配置处理，不能解释成“强制把 null 变 0”。
- `getDynamicObject(String)` / `getDynamicObjectCollection(String)`：引用对象与分录集合；先确认属性类型和层级，引用对象可能为空。
- `containsProperty(String)`：检查当前对象属性是否存在；缺字段是模型/投影问题，不等于字段已存在但没填值。
- `getDataEntityType()` / `getPkValue()`：模型与主键；`getPkValue` 是继承方法，模型无主键时可为 `null`。

## 数值空值合同

以下是实际 7.0 JAR、默认值为 null 的普通 `DynamicSimpleProperty` 本地内存实例结果；不是数据库、所有自定义属性或表单默认值的统一保证。表中的 null 指在本例无非空默认值时，属性读取结果为 null。

|属性及配置|`get(key)`|类型 getter|`getBigDecimal(key,true)`|
|---|---|---|---|
|Long，`enableNull=false`，值 null|`0L`|`getLong` 为 0|不用于 Long 示例|
|Long，`enableNull=true`，值 null|null|`getLong` 拆箱抛 NPE|不用于 Long 示例|
|BigDecimal，`enableNull=false`，值 null|0|`getBigDecimal` 为 0|null|
|BigDecimal，`enableNull=true`，值 null|null|`getBigDecimal` 为 null|null|
|已赋实际 0|0|0|BigDecimal 为 0|

所以 `get(key)==null` 也不总能识别未填写。需要绕过 `DynamicObject` 的类型转换时，可从当前模型取得已确认属性后调用 `IDataEntityProperty.getValueFast(object)`，再按真实类型处理；不要强行把所有主键转为 Long。它仍会采用属性默认值，不是直接读取未经处理的底层存储。`getBigDecimal(key,true)` 也经过该属性读取过程；若默认值为 0，或创建、加载、上游转换已把值写成 0，读取端都不能还原它此前是不是未填写。

页面空白也不证明数据为 null：未开启“为零显示”时，0 和空值可呈现相同外观。字段配置、实际值和数据库约束要分别核实。

`getBigDecimal(missingKey,true)` 在上述目标中会抛 NPE，不是可选字段安全读取接口。其他缺字段路径也不能承诺返回 null；部分错误信息依赖平台资源初始化。先检查模型，不能靠捕获异常把缺字段降成零金额。

## 示例：数量为空时不覆盖原金额

本例假定 `qty`、`amt` 是已确认的分录 BigDecimal 字段，未填数量的属性读取结果为 null（没有默认 0），`amt` 允许计算结果；数量为 null 时保留原金额，实际 0 则计算并写入 0。如果业务要求必录或清空金额，应明确采用对应规则，不在通用读取中自动补 0。它只修改内存数据包；页面插件若要触发联动与刷新，应使用适用的数据模型接口。

```java
import java.math.BigDecimal;
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.dataentity.entity.DynamicObjectCollection;
import kd.bos.dataentity.metadata.IDataEntityProperty;

public class DynamicObjectExample {
    private static void requireField(DynamicObject object, String key) {
        if (object == null || !object.containsProperty(key)) {
            throw new IllegalArgumentException("数据包缺少属性：" + key);
        }
    }

    public String billNumber(DynamicObject bill) {
        requireField(bill, "billno");
        return bill.getString("billno");
    }

    public BigDecimal totalAmount(DynamicObject bill) {
        requireField(bill, "totalamount");
        return bill.getBigDecimal("totalamount", true);
    }

    public void recalculate(DynamicObject bill) {
        requireField(bill, "entryentity");
        DynamicObjectCollection rows = bill.getDynamicObjectCollection("entryentity");
        if (rows == null) return;
        for (DynamicObject row : rows) {
            requireField(row, "qty");
            requireField(row, "amt");
            BigDecimal qty = row.getBigDecimal("qty", true);
            if (qty != null) {
                row.set("amt", qty.multiply(new BigDecimal("10")));
            }
        }
    }

    public Object customerId(DynamicObject bill) {
        requireField(bill, "customer_id");
        IDataEntityProperty property = bill.getDataEntityType().getProperties().get("customer_id");
        return property.getValueFast(bill);
    }
}
```

## 基础资料对象与内码

普通基础资料字段常见 `customer` 对象键和 `customer_id` 内码键，仍须按实际模型和查询投影核实；不能把所有复杂属性都视作双键。仅需关联/过滤时读取已确认内码属性，避免无谓加载。读取对象名称前判空；设对象键时传入符合引用模型的对象，不把裸 ID 当作引用数据包。表单按 ID 赋值属于数据模型接口的另一层合同。

```java
DynamicObject customer = bill.getDynamicObject("customer");
if (customer != null) {
    String code = customer.getString("number");
}
DynamicObject newCust = BusinessDataServiceHelper.loadSingleFromCache(123456L, "bd_customer");
if (newCust == null) {
    throw new IllegalArgumentException("指定客户不存在");
}
bill.set("customer", newCust);
```

## Key、集合与边界

- 仍使用元数据中的原始 Key 编码。实际 7.0 默认动态属性集合使用不区分大小写的索引，本地普通对象对不同大小写的 `get/set/containsProperty` 均命中；因此不能写成“所有字段 Key 大小写敏感”。这不证明 SQL、表达式、深路径、其他 API 或自定义索引全部不区分大小写。
- `DynamicObjectCollection.add/remove` 只代表数据包变化，页面联动、状态和持久化按所在插件/数据模型合同处理；大批量对象注意内存与引用生命周期。
- 不为读取空值原地更改共享实体模型的 `enableNull`；需要改变业务字段定义时走对应元数据流程。

## 依据

[数值允许为空说明](https://vip.kingdee.com/knowledge/82142730041627904)（2026-07-30 14:44）指出数值基本类型 getter 在空值时会转换异常，并区分页面显示与实际值。[动态表单插件-数据模型](https://vip.kingdee.com/knowledge/221682121566163200)（2026-07-31 12:15）确认数据包结构与模型分层；正文未声明精确 SDK 版本。[V7.0.1 DynamicObject](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/dataentity/entity/DynamicObject.html) 确认 `enableNull` 形参与公开签名。数值和大小写行为另由实际 `bos-dataentity-7.0.jar` 的本地实例与字节码核验；测试隔离了日志配置，不代表默认平台启动、数据库加载或所有业务字段已验证。
