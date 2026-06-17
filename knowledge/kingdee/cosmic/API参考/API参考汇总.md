# 金蝶云苍穹 API 参考

> 更新时间: 2026-04-15

## 文档索引

| 分类 | 文档 | 说明 |
|---|---|---|
| KORM | [DynamicObject详解](KORM/DynamicObject详解.md) | DynamicObject 操作指南 |
| KORM | [DynamicObject与BusinessDataServiceHelper指南](KORM/DynamicObject与BusinessDataServiceHelper指南.md) | 数据访问与服务助手 |
| KORM | [QFilter查询详解](KORM/QFilter查询详解.md) | QFilter 查询条件写法 |
| KORM | [事务管理指南](KORM/事务管理指南.md) | KORM 事务管理 |
| 服务助手 | [OperationServiceHelper-executeOperate参数说明](服务助手/OperationServiceHelper-executeOperate参数说明.md) | 操作服务助手方法全量、参数、重载和集合转数组规则 |
| 常用工具类 | [DataSet-全量API参考](常用工具类/DataSet-全量API参考.md) | DataSet API 参考 |
| 常用工具类 | [KingScript-KDE脚本API与事件参考](常用工具类/KingScript-KDE脚本API与事件参考.md) | KingScript 脚本 API 与事件 |

## 插件基类

### 表单插件

#### AbstractFormPlugin
用于动态表单、PC端界面。

**常用事件：**

| 事件 | 触发时机 | 用途 |
|------|----------|------|
| `preOpenForm` | 显示界面前，准备构建界面显示参数时 | 取消界面显示、修改显示参数 |
| `afterCreateNewData` | 新建表单数据包成功，填写默认值后 | 重设字段默认值 |
| `afterBindData` | 数据包构建完毕，刷新前端字段后 | 设置控件可用性、可见性 |
| `registerListener` | 用户与界面控件交互时 | 侦听控件事件 |
| `beforeClick` | 用户点击按钮或标签前 | 取消点击处理 |
| `click` | 用户点击按钮或标签时 | 响应点击事件 |
| `beforeItemClick` | 点击菜单按钮，执行操作前 | 拦截菜单操作 |
| `itemClick` | 点击菜单按钮时 | 处理菜单点击 |
| `beforeDoOperation` | 点击按钮，执行绑定操作前 | 拦截操作 |
| `afterDoOperation` | 执行完绑定操作后 | 操作后处理 |
| `confirmCallBack` | 前端交互提示确认后 | 确认回调处理 |
| `closedCallBack` | 子界面关闭时 | 子界面关闭回调 |
| `propertyChanged` | 字段值更新后 | 字段变更处理 |

**代码示例：**
```java
public class MyFormPlugin extends AbstractFormPlugin {

    @Override
    public void preOpenForm(PreOpenFormEventArgs e) {
        super.preOpenForm(e);
        // 可以在此取消界面显示
        // e.setCancel(true);
    }

    @Override
    public void afterCreateNewData(EventObject e) {
        // 重设字段默认值
        this.getModel().setValue("fieldKey", defaultValue);
    }

    @Override
    public void afterBindData(EventObject e) {
        super.afterBindData(e);
        // 设置控件属性
    }

    @Override
    public void beforeDoOperation(BeforeDoOperationArgs args) {
        super.beforeDoOperation(args);
        // 操作前拦截
    }
}
```

#### AbstractBillPlugIn
用于单据界面（继承自 AbstractFormPlugin）。

### 列表插件

#### AbstractListPlugin
用于标准单据列表。

**常用事件：**

| 事件 | 触发时机 |
|------|----------|
| `beforeQueryData` | 查询数据前 |
| `queryData` | 查询数据后 |
| `listRowClick` | 列表行点击时 |
| `listRowDoubleClick` | 列表行双击时 |

#### AbstractTreeListPlugin
用于左树右表单据列表。

#### AbstractMobListPlugin
用于移动端单据列表。

### 操作服务插件

#### AbstractOperationServicePlugIn
用于单据操作服务。

### 其他插件

| 插件基类 | 用途 |
|----------|------|
| `AbstractMobFormPlugin` | 移动端界面 |
| `StandardTreeListPlugin` | 树型基础资料列表 |
| `AbstractConvertPlugIn` | 单据转换 |
| `AbstractReportFormPlugin` | 报表界面 |
| `AbstractReportListDataPlugin` | 报表查询 |
| `IWorkflowPlugin` | 工作流 |
| `IBillWebApiPlugin` | 自定义开放接口 |
| `AbstractPrintServicePlugin` | 打印数据处理 |
| `IImportPlugin` | 引入数据加工 |

## 数据操作（KORM）

### DynamicObject

DynamicObject 类似于键值对，是金蝶云苍穹的核心数据对象。

#### 创建对象
```java
// 创建新的 DynamicObject
DynamicObject dynamicObject = BusinessDataServiceHelper.newDynamicObject("entityKey");
```

#### 取值
```java
// 取出来的值是 object 类型，需要转换
String name = (String) dynamicObject["Name"];
// 或使用 get 方法
Object value = dynamicObject.get("fieldKey");
```

#### 赋值
```java
// 直接赋值
dynamicObject["Name"] = newName;
// 或使用 set 方法
dynamicObject.set("fieldKey", value);
```

#### 获取分录
```java
// 获取单据体分录
DynamicObjectCollection entries = dynamicObject.getDynamicObjectCollection("entryKey");

// 遍历分录
for (DynamicObject entry : entries) {
    String value = entry.getString("fieldKey");
}

// 新增分录行
DynamicObject newRow = entries.addNew();
newRow.set("fieldKey", value);
```

#### 复制对象
```java
DynamicObjectType dynamicObjectType = dynamicObject.DynamicObjectType;
DynamicObject newDynamicObject = new DynamicObject(dynamicObjectType);
foreach (DynamicProperty property in dynamicObjectType.Properties) {
    newDynamicObject[property.Name] = dynamicObject[property.Name];
}
```

### 数据服务助手

#### BusinessDataServiceHelper
```java
// 创建新对象
DynamicObject obj = BusinessDataServiceHelper.newDynamicObject("entityKey");

// 加载对象
DynamicObject obj = BusinessDataServiceHelper.loadSingle(pk, "entityKey");

// 从缓存加载
DynamicObject[] objs = BusinessDataServiceHelper.loadFromCache("entityKey", new Object[]{pk1, pk2});
```

#### SaveServiceHelper
```java
// 保存数据
SaveServiceHelper.saveOperate("entityKey", new DynamicObject[]{dynamicObject}, null);
```

#### OperationServiceHelper

用于执行实体操作服务，例如保存、提交、审核、反审核、删除和设计器自定义操作。

| 方法 | 说明 |
|---|---|
| `executeOperate(String operationKey, String entityNumber, DynamicObject[] dataEntities, OperateOption option)` | 按实体对象执行操作。 |
| `executeOperate(String operationKey, String entityNumber, Object[] ids, OperateOption option)` | 按主键数组执行操作。 |

集合不是 `executeOperate` 的合法第三参，必须先转为数组：

```java
OperationServiceHelper.executeOperate(
        "submit",
        formId,
        ids.toArray(new Object[0]),
        OperateOption.create());
```

方法全量、内部私有方法说明和详细参数规则见：[OperationServiceHelper-executeOperate参数说明](服务助手/OperationServiceHelper-executeOperate参数说明.md)。

#### QueryServiceHelper
```java
// 查询数据
QFilter filter = new QFilter("fieldKey", "=", value);
DynamicObject[] objs = QueryServiceHelper.query("entityKey", "field1,field2", new QFilter[]{filter});

// 查询单条
DynamicObject obj = QueryServiceHelper.queryOne("entityKey", "field1,field2", new QFilter[]{filter});
```

### 模型层操作

在插件中获取模型数据：
```java
// 获取模型
IDataModel model = this.getModel();

// 获取字段值
Object value = model.getValue("fieldKey");

// 设置字段值
model.setValue("fieldKey", value);

// 获取分录
DynamicObjectCollection entries = model.getEntryEntity("entryKey");

// 获取当前用户
Long userId = RequestContext.get().getCurrUserId();
```

## 服务开发

### 操作服务

```java
public class MyOperationService {

    public OperationResult myOperation(Map<String, Object> params) {
        OperationResult result = new OperationResult();

        try {
            // 业务逻辑

            result.setSuccess(true);
            result.setMessage("操作成功");
        } catch (Exception e) {
            result.setSuccess(false);
            result.setMessage(e.getMessage());
        }

        return result;
    }
}
```

## 常用工具类

| 工具类 | 用途 |
|--------|------|
| `RequestContext` | 获取当前请求上下文、用户信息 |
| `BusinessDataServiceHelper` | 业务数据加载、创建 |
| `SaveServiceHelper` | 数据保存操作 |
| `OperationServiceHelper` | 执行实体操作服务，如提交、审核、删除、自定义操作 |
| `QueryServiceHelper` | 数据查询 |
| `DynamicObject` | 数据对象操作 |
| `DynamicObjectCollection` | 分录集合操作 |

## 版本差异

### 7.0 vs 8.0

目前收集的资料主要针对 7.0 版本。8.0 版本的新特性需要进一步收集官方文档。

已知变化：
- 8.0 版本在 AI 能力、低代码开发方面有增强
- 部分 API 可能有调整，需要参考官方迁移指南
