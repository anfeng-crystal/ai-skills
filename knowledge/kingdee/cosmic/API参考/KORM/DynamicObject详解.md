# DynamicObject 操作指南

> 来源: https://vip.kingdee.com/article/466017882661337088
> 作者: 爱孤独又爱你
> 日期: 2023-07-09
> 标签: DynamicObject, KORM, 数据操作

---

## 摘要

DynamicObject 是金蝶云苍穹的核心数据结构，类似于键值对。本文介绍 DynamicObject 的取值、赋值、新增键、复制等常用操作。

## 适用版本

- 金蝶云苍穹 V5.0+

## 核心概念

DynamicObject 是苍穹平台的基础数据载体，每个 DynamicObject 都有对应的 `DynamicObjectType` 定义其结构。

## 基本操作

### 1. 取值

```java
// 取出来的值是 Object 类型，需要强转
String name = (String) dynamicObject["Name"];
```

### 2. 赋值

```java
String newName = "张三";
dynamicObject["Name"] = newName;
```

### 3. 新增键（属性）

**注意**：不能直接给不存在的键赋值，会报错。

正确做法：通过 `DynamicObjectType` 注册新属性：

```java
DynamicObjectType dynamicObjectType = dynamicObject.DynamicObjectType;
// 注册新属性
dynamicObjectType.RegisterProperty("ID", typeof(string));

// 创建新对象
dynamicObject newDynamicObject = new DynamicObject(dynamicObjectType);
newDynamicObject["ID"] = "1234";

// 复制原对象的值
foreach(DynamicProperty property in dynamicObjectType.Properties) {
    if (dynamicObject[property.Name] != null) {
        newDynamicObject[property.Name] = dynamicObject[property.Name];
    }
}
```

### 4. 复制对象

```java
// 创建相同结构的新对象
DynamicObjectType dynamicObjectType = dynamicObject.DynamicObjectType;
DynamicObject newDynamicObject = new DynamicObject(dynamicObjectType);

// 复制所有属性值
foreach(DynamicProperty property in dynamicObjectType.Properties) {
    newDynamicObject[property.Name] = dynamicObject[property.Name];
}
```

## DynamicObjectCollection 技巧

### 批量新增键的技巧

对于 `DynamicObjectCollection`，如果添加一个带有新键的 DynamicObject，**集合中所有元素都会自动添加这个键**。

```java
DynamicObjectCollection collection = ...;
// collection 里所有元素原本只有 Name 键

// 1. 获取类型并注册新属性
DynamicObjectType dynamicObjectType = collection[0].DynamicObjectType;
dynamicObjectType.RegisterProperty("ID", typeof(string));

// 2. 创建带新属性的对象并添加到集合
DynamicObject newDynamicObject = new DynamicObject(dynamicObjectType);
collection.Add(newDynamicObject);

// 3. 移除临时对象（可选）
collection.Remove(newDynamicObject);

// 4. 现在所有元素都有 ID 键了
collection[0]["ID"] = "123";  // 不会报错
```

**优点**：
- 不需要频繁操作集合的 Add/Remove
- 不需要替换整个对象（"狸猫换太子"）

## 注意事项

1. **类型安全**：DynamicObject 取值是 Object 类型，需要强转
2. **属性注册**：新增属性必须通过 `DynamicObjectType.RegisterProperty`
3. **集合特性**：DynamicObjectCollection 会自动同步所有元素的结构

## 相关链接

- [DynamicObject与BusinessDataServiceHelper指南](DynamicObject与BusinessDataServiceHelper指南.md)
- [金蝶云苍穹开发者文档](https://dev.kingdee.com)
