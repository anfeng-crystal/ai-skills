# DynamicObject 与 BusinessDataServiceHelper 使用指南

> 来源: 联网搜索整理
> 整理时间: 2026-04-12

---

## 1. 核心数据加载方法

### 1.1 loadSingle vs load

| 方法 | 用途 | 返回值 | 性能特点 |
|------|------|--------|----------|
| `loadSingle` | 获取单个实体 | `DynamicObject` | 内部自动添加 limit 1 优化 |
| `load` | 获取多条记录 | `DynamicObject[]` | 可能返回大量数据，需注意性能 |

### 1.2 加载单个实体示例

```java
DynamicObject product = BusinessDataServiceHelper.loadSingle(
    "bd_material",                    // 物料基础资料标识
    "id,name,specification,baseUnit", // 需要加载的字段
    new QFilter[]{new QFilter("id", QCP.equals, "1001")}  // 精确匹配ID
);
```

### 1.3 加载多个实体示例

```java
DynamicObject[] orders = BusinessDataServiceHelper.load(
    "sal_order",                      // 销售订单标识
    "billNo,date,customer,amount",    // 需要加载的字段
    new QFilter[]{
        new QFilter("date", QCP.greater_equal, "2023-01-01"),
        new QFilter("amount", QCP.greater, 10000)
    }  // 复合查询条件
);
```

### 1.4 单据体字段加载规范

**重要：** 加载单据体时必须显式声明需要获取的二级字段！

```java
String fields = "billNo,date," +           // 单据头字段
                "entryEntity," +            // 单据体标识
                "entryEntity.materialId," + // 单据体二级字段
                "entryEntity.materialName," +
                "entryEntity.qty";

DynamicObject[] orders = BusinessDataServiceHelper.load(
    "sal_order",
    fields,
    new QFilter[]{new QFilter("billNo", QCP.equals, "SO20240001")}
);
```

---

## 2. 新建数据

### 2.1 创建 DynamicObject

```java
DynamicObject dynamicObject = BusinessDataServiceHelper.newDynamicObject("abq2_apply");
```

**注意：**
- 刚创建的实体，数值型字段默认为 0
- 其他字段默认为 null
- 建议给创建人、编号、数据状态、使用状态赋值

### 2.2 设置字段值

```java
// 生成单据编号
StringBuilder sb1 = new StringBuilder();
sb1.append("AskForLeave-");
for (int i = 1; i <= 10; i++) {
    int ascii = 48 + (int) (Math.random() * 9);
    char c = (char) ascii;
    sb1.append(c);
}

// 设置属性
dynamicObject.set("billno", sb1.toString());                          // 单据编号
dynamicObject.set("abq2_creator", RequestContext.get().getCurrUserId()); // 创建人
dynamicObject.set("enable", 1);                                        // 使用状态
dynamicObject.set("billstatus", "A");                                  // 数据状态
```

### 2.3 增加单据体分录

```java
// 获取单据体集合
DynamicObjectCollection dynamicObjectCollection =
    dynamicObject.getDynamicObjectCollection("abq2_task_entryentity");

// 新增分录
DynamicObject dynamicObjectEntry = dynamicObjectCollection.addNew();

// 设置单据体字段值
dynamicObjectEntry.set("abq2_task_context", "任务内容");
dynamicObjectEntry.set("abq2_expect_minute", 60);
dynamicObjectEntry.set("abq2_diff", "难度等级");
```

---

## 3. 保存数据

```java
SaveServiceHelper.saveOperate(
    "abq2_schedule_form",                    // 基础资料/单据标识
    new DynamicObject[]{dynamicObject},      // 要保存的实体数组
    null                                     // 操作选项
);
```

---

## 4. 修改数据

```java
// 1. 加载实体（省略 load 代码）
DynamicObject activity = ...;

// 2. 修改字段值
activity.set("abq2_selected_count", selectedCount + 1);

// 3. 保存
SaveServiceHelper.saveOperate("abq2_activity", new DynamicObject[]{activity}, null);
```

---

## 5. 获取当前页面数据

在插件中获取当前界面数据：

```java
// 获取单据头字段值
String taskName = this.getModel().getValue("name").toString();
String createTime = this.getModel().getValue("abq2_task_create_time").toString();

// 获取单据体数据
DynamicObjectCollection entries = this.getModel().getEntryEntity("abq2_task_entryentity");

// 遍历单据体
for (DynamicObject entry : entries) {
    String taskContent = entry.getString("abq2_task_context");
    String expectTime = entry.getString("abq2_expect_minute");
    String diff = entry.getString("abq2_diff");
}
```

---

## 6. 性能建议

1. **限制结果集大小** - 使用 `load` 时添加分页或结果集限制
2. **显式声明字段** - 避免使用 `*` 加载所有字段
3. **单据体字段** - 必须显式声明二级字段才能获取内容
4. **批量操作** - 尽量使用批量 save 而不是单条循环

---

## 参考来源

- https://blog.csdn.net/weixin_29263201/article/details/159152023
- https://juejin.cn/post/7388311581658628148
- https://dev.kingdee.com/sdk/Cosmic%20V6.0.4/javadoc/kd/bos/servicehelper/BusinessDataServiceHelper.html
