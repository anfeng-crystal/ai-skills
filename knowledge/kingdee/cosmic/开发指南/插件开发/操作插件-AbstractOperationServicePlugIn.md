# 操作插件 AbstractOperationServicePlugIn 开发指南

> 来源: https://vip.kingdee.com/article/640131822910510848
> 来源: https://vip.kingdee.com/article/285118883487407967
> 标签: 操作插件, AbstractOperationServicePlugIn, 服务插件, 执行顺序

---

## 摘要

操作插件（AbstractOperationServicePlugIn）用于处理单据的保存、提交、审核等操作。本文介绍操作插件的执行顺序、核心事件及开发技巧。

## 适用版本

- 金蝶云苍穹 V5.0+
- 金蝶云星空（K3Cloud）

## 核心概念

操作插件在服务端执行，与表单插件的区别：
- **表单插件**：运行在客户端，处理界面交互
- **操作插件**：运行在服务端，处理业务逻辑、数据校验、数据库操作

## 执行顺序

```
onPreparePropertys
  → onAddValidators
  → beforeExecuteOperationTransaction
  → beginOperationTransaction
  → [数据库操作]
  → endOperationTransaction
  → [事务提交]
  → afterExecuteOperationTransaction
  → setContext
  → initializeOperationResult
  → onReturnOperation
```

## 核心事件详解

### 1. onPreparePropertys

**触发时机**：准备操作需要的字段

**用途**：添加需要用到的字段到操作上下文

```java
@Override
public void onPreparePropertys(PreparePropertysEventArgs e) {
    base.onPreparePropertys(e);
    // 添加需要用到的字段
    e.FieldKeys.Add("FBillNo");
    e.FieldKeys.Add("FId");
    e.FieldKeys.Add("FEntryID");
}
```

### 2. onAddValidators

**触发时机**：系统预置操作校验器加载完，执行校验前

**用途**：添加自定义校验器

### 3. beforeExecuteOperationTransaction

**触发时机**：校验通过后，开启事务前

**用途**：
- 最终业务校验
- 设置操作参数

**注意**：
- 不要在此事件直接跨库更新数据
- 跨库需采用 KDTX 框架实现数据一致性
- 不要通过 `e.setCancelOperation(true)` 取消操作（不会回滚已更新的关联数据）

```java
@Override
public void beforeExecuteOperationTransaction(BeforeExecuteOperationTransaction e) {
    base.beforeExecuteOperationTransaction(e);

    // 获取操作数据
    DynamicObject[] dataEntities = e.SelectedRows;

    // 业务校验
    foreach (DynamicObject data in dataEntities) {
        string billNo = data["FBillNo"].ToString();
        // 校验逻辑...
    }
}
```

### 4. beginOperationTransaction

**触发时机**：开启事务后，提交到数据库前

**用途**：在事务中执行额外的数据库操作

**注意**：
- 不能在此事件检查数据合法性（应在 beforeExecuteOperationTransaction 中检查）
- 不要通过 `e.setCancelOperation(true)` 取消操作

### 5. endOperationTransaction

**触发时机**：提交数据库后，事务未提交前

**用途**：执行操作后的业务逻辑

### 6. afterExecuteOperationTransaction

**触发时机**：事务提交后

**用途**：
- 发送消息通知
- 触发外部系统接口
- 记录操作日志

```java
@Override
public void afterExecuteOperationTransaction(AfterExecuteOperationTransaction e) {
    base.afterExecuteOperationTransaction(e);

    // 调整操作结果提示
    var resultSuccess = new OperateResult();
    resultSuccess.Message = string.Format(
        "单据【{0}】处理成功！",
        resultSuccess.Number
    );
    this.OperationResult.OperateResult.Add(resultSuccess);
}
```

### 7. onReturnOperation

**触发时机**：操作结束

## 常用开发技巧

### 获取表单插件传递的参数

表单插件中使用 `e.Option.SetVariableValue` 传递参数：

```java
// 表单插件中设置参数
public override void beforeDoOperation(BeforeDoOperationArgs e) {
    e.Option.SetVariableValue("CustomParam", "value");
}
```

操作插件中获取参数：

```java
public override void beforeExecuteOperationTransaction(BeforeExecuteOperationTransaction e) {
    // 通过 Option 属性获取参数
    object customParam = this.Option.GetVariableValue("CustomParam");
}
```

### 实现消息提示

服务插件不能直接 ShowMessage，必须通过操作结果返回：

```java
// 调整操作结果
var resultSuccess = new OperateResult();
resultSuccess.Message = "操作成功，已通知第三方系统！";
resultSuccess.Number = billNo;
this.OperationResult.OperateResult.Add(resultSuccess);
```

### 抛出异常中断操作

```java
// 普通错误（中断操作）
throw new KDException("单据编号不能为空");

// 交互式提示（需要用户确认）
throw new KDInteractionException("确认删除该单据吗？");
```

## 校验器开发

### 定义校验器

```java
public class CustomValidator : AbstractValidator {

    public override void Validate(ValidateContext e) {
        foreach (DynamicObject data in e.DataEntities) {
            string billNo = data["FBillNo"].ToString();
            if (string.IsNullOrEmpty(billNo)) {
                e.AddError(data, "单据编号不能为空");
            }
        }
    }
}
```

### 注册校验器

```java
public override void onAddValidators(AddValidatorsEventArgs e) {
    base.onAddValidators(e);
    e.Validators.Add(new CustomValidator());
}
```

## 注意事项

1. **事务一致性**：不要在 `beginOperationTransaction` 中跨库操作，会破坏事务一致性
2. **取消操作**：不要用 `e.setCancelOperation(true)`，应抛出异常
3. **消息提示**：服务插件不能直接 ShowMessage，通过 `OperationResult` 返回
4. **调试技巧**：通过服务接口保存单据时，需要附加到 SI 服务站点的 w3wp 进程

## 与表单插件的事件对照

| 场景 | 表单插件 | 操作插件 |
|-----|---------|---------|
| 操作前校验 | beforeDoOperation | beforeExecuteOperationTransaction |
| 操作后处理 | afterDoOperation | afterExecuteOperationTransaction |
| 传递参数 | e.Option.SetVariableValue | this.Option.GetVariableValue |
| 提示消息 | this.View.ShowMessage() | OperationResult.OperateResult.Add() |

## 相关链接

- [苍穹插件执行顺序详解](https://vip.kingdee.com/article/640131822910510848)
- [服务插件开发指南](https://vip.kingdee.com/article/285118883487407967)
- [校验器开发文档](https://vip.kingdee.com/article/1319605)
