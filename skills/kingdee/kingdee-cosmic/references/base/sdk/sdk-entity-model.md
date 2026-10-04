# 动态领域模型：实体与属性

## 类型与适用范围

用于读取主实体、分录和字段结构；只操作字段值时转 `sdk-dynamic-object.md`，团队封装见 [entity-metadata.md](../../adv/entity-metadata.md)。以下继承与签名由实际 7.0 JAR 和官方 V7.0.1 Javadoc 互核，不把文档版本当成项目补丁版本。

|类型|继承/用途|
|---|---|
|`kd.bos.entity.EntityType`|继承 `DynamicObjectType`，此处主实体与分录的共同基类。|
|`MainEntityType`|继承 `EntityType`，主实体；并非所有实体的基类。|
|`BillEntityType` / `BasedataEntityType`|前者继承 `MainEntityType`；后者继承 `BillEntityType`。|
|`EntryType`|继承 `EntityType`，分录模型；不能强转为 `MainEntityType`。|
|`FieldProp` / `BasedataProp` / `EntryProp`|`kd.bos.entity.property` 下的字段属性；分别用于普通字段、基础资料引用、分录集合等判断。|

## 获取与遍历

- `MetadataServiceHelper.getDataEntityType(String)` 返回主实体模型；界面插件需要当前运行时模型时，使用其 `getModel().getDataEntityType()`，不要假定通用加载结果含界面动态注册的字段。
- `getProperties()` 只含当前实体层属性。分录进入 `EntryProp.getItemType(): IDataEntityType` 后继续遍历；基础资料通过 `BasedataProp.getBaseEntityId()` 识别引用实体，不当作分录处理。
- `MainEntityType.getProperty(String)`、`getPrimaryKey()` 由父类继承，是真实 API。主键返回 `ISimpleProperty`，动态表单等无物理主键场景可为 null。递归变量若是 `IDataEntityType`，使用其属性集合；该接口本身没有 `getProperty(String)`。

|属性 API|真实含义|
|---|---|
|`getName(): String`|属性标识，读取数据值时使用这个模型 Key。|
|`getAlias(): String`|通用接口约定为别名；只有结合具体持久化模型，才能判断是否对应物理表/列，不能据此直接生成 DDL。|
|`getDisplayName(): LocaleString`|继承自 `IMetadata`；`getLocaleValue()` 取当前语种显示值，模型可能未设置标题时先判空。|
|`getPropertyType(): Class<?>`|属性值的 Java 类型；集合属性返回集合的类型，不是集合项实体，更不是数据库物理类型。|

`IDataEntityProperty` 没有 `getDataType()`。数据库字段类型、长度、精度、表列映射需核实际元数据/数据库定义，不能把 `getPropertyType()` 当成同义替代。

## 只读示例

下面输出结构诊断，`entityId` 与 `customer` 字段须来自目标模型；控制台输出仅演示遍历，不是生产日志方案。递归只进入分录，打印完整属性路径，避免主表与分录同名字段混淆。

```java
import kd.bos.dataentity.entity.LocaleString;
import kd.bos.dataentity.metadata.IDataEntityProperty;
import kd.bos.dataentity.metadata.IDataEntityType;
import kd.bos.dataentity.metadata.ISimpleProperty;
import kd.bos.entity.MainEntityType;
import kd.bos.entity.property.BasedataProp;
import kd.bos.entity.property.EntryProp;
import kd.bos.servicehelper.MetadataServiceHelper;

public final class EntityModelInspection {
    public static void inspect(String entityId) {
        // 返回的实体模型可能被缓存；此例只读取，不原地修改。
        MainEntityType root = MetadataServiceHelper.getDataEntityType(entityId);
        ISimpleProperty primaryKey = root.getPrimaryKey();
        System.out.println("primaryKey="
                + (primaryKey == null ? "<none>" : primaryKey.getName()));
        printCurrentAndEntries(root, root.getName());

        // getProperty 是继承 API；按当前实体的字段标识取属性。
        IDataEntityProperty customer = root.getProperty("customer");
        if (customer instanceof BasedataProp) {
            String baseEntityId = ((BasedataProp) customer).getBaseEntityId();
            System.out.println("customer -> " + baseEntityId);
        }
    }

    private static void printCurrentAndEntries(IDataEntityType type, String path) {
        // getProperties 只遍历当前实体；分录的子实体需要单独进入。
        for (IDataEntityProperty prop : type.getProperties()) {
            LocaleString label = prop.getDisplayName();
            String displayName = label == null ? prop.getName() : label.getLocaleValue();
            Class<?> valueType = prop.getPropertyType();
            String propertyPath = path + "." + prop.getName();
            System.out.println(propertyPath + " : " + displayName
                    + " [Java=" + valueType.getTypeName() + "]");
            if (prop instanceof EntryProp) {
                IDataEntityType itemType = ((EntryProp) prop).getItemType();
                printCurrentAndEntries(itemType, propertyPath);
            }
        }
    }
}
```

## 模型缓存与修改边界

主实体模型可能被共享缓存，只读检查可在循环外取得后复用；不要在缓存对象上直接注册或修改属性。需要给当前界面增加字段时，按 `getEntityType` 事件合同克隆原模型，修改副本后回传 `setNewEntityType`，并配合动态控件事件；不把只读遍历顺手变成全局模型修改。

## 依据

- [动态表单插件-数据模型](https://vip.kingdee.com/knowledge/221682121566163200)，更新 2026-07-31：当前实体属性范围、分录模型、缓存副本和可空主键。
- [getEntityType 事件](https://vip.kingdee.com/knowledge/222733151671020800)，更新 2026-07-31：运行时模型副本与动态字段入口。
- [MainEntityType](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/entity/MainEntityType.html)、[EntryType](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/entity/EntryType.html)、[IDataEntityProperty](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/dataentity/metadata/IDataEntityProperty.html)、[DynamicCollectionProperty](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/dataentity/metadata/dynamicobject/DynamicCollectionProperty.html) · 官方 V7.0.1 Javadoc。

示例用实际 7.0 最小依赖与 JDK 8 离线编译通过；未执行目标元数据服务或界面模型修改。
