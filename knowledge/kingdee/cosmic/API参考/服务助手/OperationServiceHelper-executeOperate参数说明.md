# OperationServiceHelper-方法全量与executeOperate参数说明

> 来源: 本地随包开发文档 `/Users/anfeng/Code/Study/cosmic-kafka-local/runtime/cosmic-home/static-file-service/devdoc/base/operation/OperationServiceHelper.md`；本地 Javadoc `/Users/anfeng/Code/Study/cosmic-kafka-local/runtime/cosmic-home/static-file-service/devtools/ks-api/kd/bos/servicehelper/operation/OperationServiceHelper.html`；本地依赖 `bos-servicehelper-7.0.jar`、`bos-mservice-operation-7.0.jar` 反编译核对
> 作者: 本地知识库整理
> 日期: 2026-04-15
> 标签: OperationServiceHelper, executeOperate, 服务助手, 操作服务, 苍穹插件

---

## 摘要
`OperationServiceHelper` 是苍穹实体操作服务的上层封装。本文按源码成员完整整理常量、构造器、4 个公开 `executeOperate` 重载和 2 个内部私有方法，并给出人类可读、模型可解析的使用规则；`executeOperate` 第三个参数只有 `DynamicObject[]` 和 `Object[]` 两类有效重载，集合必须先转换为数组，不能直接等同于 id 数组。

## 适用版本
- 金蝶云苍穹 V7.0 本地运行包
- Java 8
- 本地依赖核对时间：2026-04-15

## 核心概念

| 概念 | 说明 |
|---|---|
| `operationKey` | 操作标识，例如 `save`、`submit`、`audit`、`unaudit`、`delete` 或设计器自定义操作。 |
| `entityNumber` | 实体标识，即设计器中的表单/单据标识。 |
| `DynamicObject[]` | 已加载或新建的实体对象数组，直接作为待操作数据进入操作服务。 |
| `Object[] ids` | 主键数组，操作服务会先按主键加载实体数据，再执行操作。 |
| `OperateOption` | 操作选项和自定义变量容器，可传 `OperateOption.create()`；传 `null` 时 Helper 内部会补建。 |
| `OperationResult` | 操作结果，包含成功状态、成功主键、错误信息、消息等。 |

## 详细内容

### 类成员全量清单

本地随包文档、Javadoc 和 `bos-servicehelper-7.0.jar` 核对到的类成员如下：

| 成员 | 可见性 | 状态 | 人类理解 | 模型判断 |
|---|---|---|---|---|
| `IS_OPEN_INTENT_LOCKS` | `public static final String` | 内部常量 | 操作选项中的意向锁变量 key，值为 `isOpenIntentLocks`。 | 只读常量，不作为业务开关手工改写。 |
| `OperationServiceHelper()` | `public` | 不推荐主动使用 | 工具类默认构造器，源码中无状态。 | 不需要 `new`，直接调用静态方法。 |
| `executeOperate(String, String, DynamicObject[])` | `public static` | 已过时 | 按实体对象执行操作，内部自动创建默认 `OperateOption`。 | 可识别为实体对象模式，但新代码应改四参重载。 |
| `executeOperate(String, String, DynamicObject[], OperateOption)` | `public static` | 推荐 | 按已加载或新建的实体对象执行操作。 | `third_arg_type=DynamicObject[]`，选择实体对象模式。 |
| `executeOperate(String, String, Object[])` | `public static` | 已过时 | 按主键执行操作，内部自动创建默认 `OperateOption`。 | 可识别为主键模式，但新代码应改四参重载。 |
| `executeOperate(String, String, Object[], OperateOption)` | `public static` | 推荐 | 按主键数组执行操作，服务端先加载实体再操作。 | `third_arg_type=Object[]`，选择主键模式。 |
| `setOperateOption(OperateOption)` | `private static` | 内部方法 | 补齐空 `option`，并写入意向锁变量。 | 外部不可调用；解释执行链路时说明副作用。 |
| `getAppId(String, MainEntityType)` | `private static` | 内部方法 | 根据实体元数据计算操作服务路由 appId。 | 外部不可调用；解释服务路由时说明。 |

### 公开 API 方法

公开可调用的 `executeOperate` 方法如下：

| 方法签名 | 状态 | 选择条件 | 返回 |
|---|---|---|---|
| `static OperationResult executeOperate(String operationKey, String entityNumber, DynamicObject[] dataEntities, OperateOption option)` | 推荐 | 已有 `DynamicObject` 或正在保存新对象。 | `OperationResult` |
| `static OperationResult executeOperate(String operationKey, String entityNumber, Object[] ids, OperateOption option)` | 推荐 | 只有主键，或保存成功后用 `successPkIds` 继续提交/审核。 | `OperationResult` |
| `static OperationResult executeOperate(String operationKey, String entityNumber, DynamicObject[] dataEntities)` | 已过时 | 兼容旧代码；不需要自定义 `OperateOption`。 | `OperationResult` |
| `static OperationResult executeOperate(String operationKey, String entityNumber, Object[] ids)` | 已过时 | 兼容旧代码；不需要自定义 `OperateOption`。 | `OperationResult` |

### 方法卡片

以下卡片采用固定字段，便于人类阅读，也便于模型在编码时做参数选择。

#### 1. 常量 `IS_OPEN_INTENT_LOCKS`

| 字段 | 内容 |
|---|---|
| 成员类型 | 常量 |
| 签名 | `public static final String IS_OPEN_INTENT_LOCKS = "isOpenIntentLocks"` |
| 用途 | 作为 `OperateOption` 变量 key，记录当前操作是否启用意向锁。 |
| 人类怎么用 | 一般不用直接使用；只需要知道 Helper 会自动写入该变量。 |
| 模型怎么判断 | 遇到该常量时，将其解释为操作服务内部变量，不建议业务代码主动设置或覆盖。 |
| 注意 | 常量标注为内部用途，业务代码不要把它当成普通业务参数。 |

#### 2. 构造器 `OperationServiceHelper()`

| 字段 | 内容 |
|---|---|
| 成员类型 | 构造器 |
| 签名 | `public OperationServiceHelper()` |
| 用途 | Java 默认工具类构造器，无状态初始化逻辑。 |
| 人类怎么用 | 不需要使用。调用操作服务时直接用类名调用静态方法。 |
| 模型怎么判断 | 生成代码时不要写 `new OperationServiceHelper()`；应写 `OperationServiceHelper.executeOperate(...)`。 |
| 示例 | `OperationServiceHelper.executeOperate("submit", formId, ids, option);` |

#### 3. `executeOperate(String, String, DynamicObject[], OperateOption)`

| 字段 | 内容 |
|---|---|
| 成员类型 | 公开静态方法 |
| 状态 | 推荐 |
| 输入模式 | 实体对象模式 |
| 签名 | `public static OperationResult executeOperate(String operationKey, String entityNumber, DynamicObject[] dataEntities, OperateOption option)` |
| 用途 | 对已构造、已加载或已修改的 `DynamicObject` 数组执行操作。 |
| 人类怎么用 | 适合保存新对象、保存修改后的对象，或操作当前模型中的实体对象。 |
| 模型怎么判断 | 当第三参是 `DynamicObject[]` 或 `list.toArray(new DynamicObject[0])` 时选择此重载。 |
| 不适合 | 只有主键时不要先手工加载对象再操作，优先用 `Object[] ids` 重载。 |
| 返回 | `OperationResult`，需要检查 `isSuccess()` 和错误信息。 |

```java
OperateOption option = OperateOption.create();
OperationResult result = OperationServiceHelper.executeOperate(
        "save",
        formId,
        new DynamicObject[]{data},
        option);
```

#### 4. `executeOperate(String, String, Object[], OperateOption)`

| 字段 | 内容 |
|---|---|
| 成员类型 | 公开静态方法 |
| 状态 | 推荐 |
| 输入模式 | 主键模式 |
| 签名 | `public static OperationResult executeOperate(String operationKey, String entityNumber, Object[] ids, OperateOption option)` |
| 用途 | 对主键数组对应的数据执行操作。服务端会按主键加载实体对象后再执行操作。 |
| 人类怎么用 | 适合提交、审核、反审核、删除、保存后继续提交等场景。 |
| 模型怎么判断 | 当第三参来源是主键列表、`getSuccessPkIds()`、`queryPrimaryKeys()` 或 `new Object[]{pkId}` 时选择此重载。 |
| 不适合 | 不要传 `new Object[]{ids}`，这会把集合整体当成一个主键。 |
| 返回 | `OperationResult`，需要检查 `isSuccess()`、`getSuccessPkIds()` 和错误信息。 |

```java
Object[] ids = saveResult.getSuccessPkIds().toArray(new Object[0]);
OperationResult result = OperationServiceHelper.executeOperate(
        "submit",
        formId,
        ids,
        option);
```

#### 5. `executeOperate(String, String, DynamicObject[])`

| 字段 | 内容 |
|---|---|
| 成员类型 | 公开静态方法 |
| 状态 | 已过时 |
| 输入模式 | 实体对象模式，默认操作选项 |
| 签名 | `public static OperationResult executeOperate(String operationKey, String entityNumber, DynamicObject[] dataEntities)` |
| 源码行为 | 内部调用 `OperateOption.create()`，再转到四参 `DynamicObject[]` 重载。 |
| 人类怎么用 | 只读旧代码时理解即可，新代码不要继续使用。 |
| 模型怎么判断 | 自动迁移为四参方法，并显式传 `OperateOption.create()` 或项目统一的 `getOprateOption()`。 |

```java
// 旧写法
OperationServiceHelper.executeOperate("save", formId, new DynamicObject[]{data});

// 推荐写法
OperationServiceHelper.executeOperate("save", formId, new DynamicObject[]{data}, OperateOption.create());
```

#### 6. `executeOperate(String, String, Object[])`

| 字段 | 内容 |
|---|---|
| 成员类型 | 公开静态方法 |
| 状态 | 已过时 |
| 输入模式 | 主键模式，默认操作选项 |
| 签名 | `public static OperationResult executeOperate(String operationKey, String entityNumber, Object[] ids)` |
| 源码行为 | 内部调用 `OperateOption.create()`，再转到四参 `Object[]` 重载。 |
| 人类怎么用 | 只读旧代码时理解即可，新代码不要继续使用。 |
| 模型怎么判断 | 自动迁移为四参方法，并显式传 `OperateOption.create()` 或项目统一的 `getOprateOption()`。 |

```java
// 旧写法
OperationServiceHelper.executeOperate("submit", formId, ids);

// 推荐写法
OperationServiceHelper.executeOperate("submit", formId, ids, OperateOption.create());
```

#### 7. `setOperateOption(OperateOption)`

| 字段 | 内容 |
|---|---|
| 成员类型 | 私有静态方法 |
| 状态 | 内部方法，外部不可调用 |
| 签名 | `private static OperateOption setOperateOption(OperateOption option)` |
| 源码行为 | 如果 `option == null`，创建 `OperateOption.create()`；随后写入变量 `isOpenIntentLocks = String.valueOf(CoreMutexHelper.isOpenIntentLocks())`。 |
| 人类怎么理解 | Helper 会统一补齐操作选项，并把平台锁控制状态透传给后续操作服务。 |
| 模型怎么判断 | 解释 `option` 允许为 `null`，但生成业务代码时仍推荐显式传 `OperateOption.create()`。 |

#### 8. `getAppId(String, MainEntityType)`

| 字段 | 内容 |
|---|---|
| 成员类型 | 私有静态方法 |
| 状态 | 内部方法，外部不可调用 |
| 签名 | `private static String getAppId(String entityNumber, MainEntityType dt)` |
| 源码行为 | 先取 `dt.getAppId()`；若不是 `bos` 直接返回；若是 `bos`，再取 `bizAppNumber`，为空时通过 `MetadataDao.getAppNumberByEntityNumber(entityNumber)` 查询，最后组装成 `bos.{bizAppNumber}`。 |
| 人类怎么理解 | 它负责把实体操作路由到正确应用服务。 |
| 模型怎么判断 | 不生成调用代码；解释跨应用实体操作时说明 Helper 会按元数据自动路由。 |

### 模型可解析索引

```yaml
OperationServiceHelper:
  role: "苍穹实体操作服务帮助类"
  call_style: "static"
  do_not_instantiate: true
  public_constant:
    IS_OPEN_INTENT_LOCKS:
      value: "isOpenIntentLocks"
      usage: "internal_operate_option_variable"
  overloads:
    - id: "execute_dynamic_with_option"
      signature: "executeOperate(String operationKey, String entityNumber, DynamicObject[] dataEntities, OperateOption option)"
      status: "recommended"
      third_arg_kind: "dynamic_object_array"
      use_when:
        - "saving_new_or_modified_dynamic_objects"
        - "operating_loaded_dynamic_objects"
      avoid_when:
        - "only_primary_keys_are_available"
      example_third_arg: "new DynamicObject[]{data}"
    - id: "execute_ids_with_option"
      signature: "executeOperate(String operationKey, String entityNumber, Object[] ids, OperateOption option)"
      status: "recommended"
      third_arg_kind: "primary_key_array"
      use_when:
        - "submit_audit_unaudit_delete_by_pk"
        - "continue_operation_with_saveResult.getSuccessPkIds()"
      avoid_when:
        - "third_arg_is_collection_object_wrapped_by_new Object[]{ids}"
      example_third_arg: "ids.toArray(new Object[0])"
    - id: "execute_dynamic_without_option"
      signature: "executeOperate(String operationKey, String entityNumber, DynamicObject[] dataEntities)"
      status: "deprecated"
      replacement: "execute_dynamic_with_option"
    - id: "execute_ids_without_option"
      signature: "executeOperate(String operationKey, String entityNumber, Object[] ids)"
      status: "deprecated"
      replacement: "execute_ids_with_option"
  private_methods:
    setOperateOption:
      callable_by_business_code: false
      effect:
        - "create_default_option_when_null"
        - "set isOpenIntentLocks variable"
    getAppId:
      callable_by_business_code: false
      effect:
        - "resolve operation service app route from entity metadata"
  selection_rules:
    - condition: "arg3 is DynamicObject[]"
      choose: "execute_dynamic_with_option"
    - condition: "arg3 is Object[] of primary keys"
      choose: "execute_ids_with_option"
    - condition: "arg3 is List or Set of primary keys"
      action: "convert_to_Object_array_first"
    - condition: "arg3 is List<DynamicObject>"
      action: "convert_to_DynamicObject_array_first"
    - condition: "arg3 is new Object[]{collection}"
      action: "reject_as_wrong_primary_key_array"
```

### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `operationKey` | `String` | 是 | 操作 key。必须是实体元数据中存在的操作标识。 |
| `entityNumber` | `String` | 是 | 实体标识。按该标识查找 `MainEntityType` 和操作元数据。 |
| `dataEntities` | `DynamicObject[]` | 是 | 需要操作的实体对象数组。 |
| `ids` | `Object[]` | 是 | 需要操作的数据主键数组，元素通常为 `Long`、`String` 等主键值。 |
| `option` | `OperateOption` | 否 | 自定义操作参数。源码中会对 `null` 自动创建，并写入 `isOpenIntentLocks` 变量。 |

### 执行流程

`DynamicObject[]` 重载流程：

1. 调用 `setOperateOption`，如果 `option` 为 `null` 则创建 `OperateOption.create()`。
2. 写入 `isOpenIntentLocks` 变量。
3. 通过 `entityNumber` 获取 `MainEntityType`。
4. 根据实体元数据计算服务 `appId`。
5. 通过 `DispatchServiceHelper.invokeBOSService(appId, "OperationService", "invokeOperation", ...)` 分发到服务端。
6. 服务端从 `DynamicObject[0].getDataEntityType()` 识别实体类型。
7. 初始化 `EntityOperateService`，执行操作插件、校验、事务、日志等。
8. 返回序列化后的 `OperationResult`，Helper 反序列化为结果对象。

`Object[] ids` 重载流程：

1. 调用 `setOperateOption` 并查找实体元数据。
2. 分发参数为 `operationKey`、`entityNumber`、`ids`、`option`。
3. 服务端按 ids 申请数据锁、准备字段。
4. 触发 `preparePropertys` 插件事件，让插件补充需要加载的字段。
5. 使用 `BusinessDataReader.load(ids, subEntityType, true)` 加载完整 `DynamicObject[]`。
6. 在 `OperateOption` 中写入 `isExcuteByIds = true`。
7. 再进入实体数组执行逻辑。
8. 执行后检查传入 id 中是否有未加载到的数据，未加载记录会加入错误信息并从成功主键中剔除。

### 常用示例

已有主键时执行提交：

```java
List<Object> ids = QueryServiceHelper.queryPrimaryKeys(formId, filters, null, -1);
OperationResult result = OperationServiceHelper.executeOperate(
        "submit",
        formId,
        ids.toArray(new Object[0]),
        OperateOption.create());
```

已有实体对象时执行保存：

```java
DynamicObject data = BusinessDataServiceHelper.newDynamicObject(formId);
OperationResult result = OperationServiceHelper.executeOperate(
        "save",
        formId,
        new DynamicObject[]{data},
        OperateOption.create());
```

保存成功后再按成功主键提交：

```java
OperationResult saveResult = OperationServiceHelper.executeOperate(
        "save",
        formId,
        new DynamicObject[]{data},
        option);

if (saveResult.isSuccess()) {
    OperationServiceHelper.executeOperate(
            "submit",
            formId,
            saveResult.getSuccessPkIds().toArray(new Object[0]),
            option);
}
```

单条主键操作：

```java
OperationServiceHelper.executeOperate(
        "delete",
        formId,
        new Object[]{pkId},
        OperateOption.create());
```

集合中的实体对象需要显式转为 `DynamicObject[]`：

```java
List<DynamicObject> dataList = new ArrayList<>();
OperationServiceHelper.executeOperate(
        "audit",
        formId,
        dataList.toArray(new DynamicObject[0]),
        OperateOption.create());
```

## 注意事项

1. `executeOperate` 没有 `Collection` 第三参重载。Java 代码中 `List`、`Set` 必须先转换为数组。
2. `ids.toArray()` 和直接构造 `new Object[]{id1, id2}` 最终都会进入 `Object[] ids` 重载，执行语义一致。
3. `new Object[]{ids}` 不等于 id 数组，它表示数组里只有一个元素，这个元素是集合对象本身，容易导致按主键加载失败。
4. `List<DynamicObject>.toArray()` 返回 `Object[]`，会命中主键数组重载；应使用 `toArray(new DynamicObject[0])`。
5. `Object[] ids` 重载会额外执行按主键加载、数据锁、字段准备和不存在记录检查；`DynamicObject[]` 重载则直接使用传入实体对象。
6. 操作顺序敏感时，不建议用无序 `Set` 直接转数组；优先使用 `List` 或 `LinkedHashSet` 保持顺序。
7. 空数组需谨慎处理。`DynamicObject[]` 空数组在服务端可能直接返回成功；`Object[] ids` 空数组在不同操作链路中可能进入加载失败或无数据逻辑，建议调用前自行判断。
8. 复杂操作或跨对象回写时，应关注操作插件事务边界，避免在同一事务中保存不同库对象。

## 相关链接

- [本地随包文档-实体操作服务帮助类](/Users/anfeng/Code/Study/cosmic-kafka-local/runtime/cosmic-home/static-file-service/devdoc/base/operation/OperationServiceHelper.md)
- [本地 Javadoc-OperationServiceHelper](/Users/anfeng/Code/Study/cosmic-kafka-local/runtime/cosmic-home/static-file-service/devtools/ks-api/kd/bos/servicehelper/operation/OperationServiceHelper.html)
- [插件类型体系速查](/Users/anfeng/KingdeeKnowledge/领域/后端开发/苍穹插件类型体系速查.md)
