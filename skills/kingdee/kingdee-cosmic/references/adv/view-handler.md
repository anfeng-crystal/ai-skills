# 后台视图管理 (ViewHandler & AutoCloseViewHandler)

详细知识、官方来源与验证边界：[云端专题](https://chatgpt.com/space/page_d3fe96e694448191860c69c467a432f8)。

## 适用与版本

`kd.cd.common.form.handler.ViewHandler` 是项目 commons 的后台视图包装；`AutoCloseViewHandler` 继承它及 `AutoCloseable`，适合在受支持的平台任务上下文中创建、使用并释放视图。前台弹窗、新页签及关闭回调用当前表单的 `getView().showForm(...)`，见 [表单工具](form-utils.md)；后台包装本身不向用户展示页面。

工厂也会解析表单类型元数据，不是无平台依赖的纯对象构造器。

以下包装合同来自 `kd-cd-cosmic-commons` **RELEASE-26-0424**（声明 Cosmic 7.0+）及实际 7.0 构件；官方 V7.0.1 参数说明与本地补丁分别核对，不据此承诺 V8/V9 或任意 7.0 补丁兼容。

## 工厂、参数与返回

| 工厂 | 返回 |
|---|---|
| `ViewHandler.of(String formId)` | `ViewHandler` |
| `ViewHandler.of(String formId, Object initOrgId)` | `ViewHandler` |
| `AutoCloseViewHandler.of(String formId)` | `AutoCloseViewHandler` |
| `AutoCloseViewHandler.of(String formId, Object initOrgId)` | `AutoCloseViewHandler` |

参数方法均返回 **void**，分条调用，不能按 fluent API 连缀：

| 方法 | 执行合同 |
|---|---|
| `addCustomParam(String name, Object value)` | 首次打开时合入自定义参数，同名键以后设置为准；不负责跨会话缓存或授权 |
| `beforeOpen(Consumer<FormShowParameter> c)` | 添加首次创建前的参数回调，按注册顺序执行；包装默认回调仍可能后置覆盖，见权限边界 |
| `setOpenOnDesignerPage()` | 添加设计器父页面相关参数处理，会涉及缓存设计器父视图的取得/创建；不是普通许可开关，不作为绕过许可或权限的通用建议 |

| 打开/关闭方法 | 返回与行为 |
|---|---|
| `openAddNewView()` | `IFormView`；`ADDNEW`，另执行空主业务组织补值分支 |
| `openAddNewViewAndInit(DynamicObject dataEntity)` | `IFormView`；`ADDNEW` 后 `model.createNewData(dataEntity)`，不经过上行的空主业务组织补值段 |
| `openModifyView(Object pkValue)` | `IFormView`；`EDIT` 打开已有单据 |
| `openPeekView(Object pkValue)` | `IFormView`；`VIEW` 打开已有单据；不能当作绝对无锁或禁止服务端写入的保证 |
| `openListView()` | `IListView`；构造列表参数，默认显示风格及多选 |
| `openView(Object pkValue, OperationStatus operationStatus)` | `IFormView`；按表单类型生成打开参数 |
| `openViewByShowParameter(FormShowParameter sp)` | `IFormView`；使用与目标类型相符的参数，单据使用 `BillShowParameter` 或适用子类 |
| `closeView()` | `void`；显式释放后台视图 |
| `AutoCloseViewHandler.close()` | `void`；调用关闭路径，可配合 try-with-resources |

每个 handler 只负责一次视图生命周期。实际实现仅在内部 view 为空时应用参数和创建视图；已打开后再调用 `open*` 主要是对既有视图 `loadData()`，不会按新参数切换单据。关闭后也不重新使用该 handler。

## 权限、许可与锁

- 首次打开时，包装在调用方已注册的 `beforeOpen` 回调之后追加默认回调，写入 `setHasRight(true)`；报表还有相应自定义标记。这是“已验权”参数事实，**不是替调用者完成了业务授权**。仅在调用方已有身份、租户/账套、组织及目标数据授权的入口使用，不能凭外部传入的 formId/PK 直接暴露后台视图。
- 官方 V7.0.1 对 `setHasRight(true)` 的含义是已验权、不再重复验权。用较早的 `beforeOpen` 设置相反值不能当作恢复检查的可靠方式；需要平台正常验权的路径时选择既有受控入口，不在示例中改许可或权限参数。
- `setOpenOnDesignerPage()` 涉及 `ide_formdesigner` 父表单及父页面；不能把方法名概括成“忽略全部许可”。本地原生配置路径仍有许可检查调用，实际分支依赖版本与上下文。
- 本地单据控制器的 `VIEW` 跳过普通编辑互斥判断，但既有单据加载路径仍可能在 `intentlocks` 条件下申请意向锁。不能承诺 `openPeekView()` 不访问锁服务；这里没有实际加锁验证。

## 组织与初始化

`initOrgId` 非 null 时，单据分支写入字符串参数 `SELECT_ORG_ID`；基础资料仅在 `useorg` 别名状态为 true 且字段名为空的分支写 `useorgId`，并调用 `BaseShowParameter.setUseOrgId(Long.parseLong(...))`，不能泛化为所有基础资料，组织值也须可转换为 long。该分支会强转参数为 `BaseShowParameter`，自定义打开参数须满足这个具体类型。

仅 `openAddNewView()` 另在组织参数非 null、主业务组织字段 key 非空且当前值为 null 时用 `setItemValueByID` 补值，不覆盖已有组织值。按目标元数据核对这些前提。

`openAddNewViewAndInit()` 先打开新增视图，再调用模型初始化；包装方法没有直接保存调用。当前本地模型会直接使用传入的非 null DynamicObject，不保证深复制，避免跨任务共享可变输入。初始化可能触发默认值、规则和插件事件，不能据此断言整个调用链绝无写入，也不能把初始化当成保存成功。

要求“用户点击保存时才落库”的前台新增场景，应通过前台 `showForm` 以 `ADDNEW` 打开，在未保存模型中完成初始化，保留用户保存/取消行为；不要为获得主键或打开页面而先保存。后台视图没有用户点击保存这个交互环节，不用后台包装替代该流程。

## 完整示例：三种后台场景

调用方先确认目标表单、应用、主键/组织类型、数据实体类型和业务授权。`process` 是由业务实现的同步处理点，不能保留视图供 try 块外或其他线程使用；示例本身不执行保存。三个场景均在同一资源作用域内完成处理。

```java
package kd.cd.common.demo;

import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.form.IFormView;
import kd.cd.common.form.handler.AutoCloseViewHandler;

public abstract class ViewHandlerDemo {
    /** 在调用方已获授权的后台上下文中处理已有单据。 */
    public final void backendOperation(String formId, String appId, Object pkValue) {
        try (AutoCloseViewHandler vh = AutoCloseViewHandler.of(formId)) {
            vh.beforeOpen(sp -> sp.setAppId(appId));
            IFormView view = vh.openModifyView(pkValue);
            process(view);
        }
    }

    /** 以初始化组织打开新增模型，不预先保存。 */
    public final void openWithOrg(String formId, String appId, Long orgId) {
        try (AutoCloseViewHandler vh = AutoCloseViewHandler.of(formId, orgId)) {
            vh.beforeOpen(sp -> sp.setAppId(appId));
            IFormView view = vh.openAddNewView();
            process(view);
        }
    }

    /** 将同类型初始数据交给新增模型；保存由独立业务动作负责。 */
    public final void openWithInit(String formId, DynamicObject initData) {
        try (AutoCloseViewHandler vh = AutoCloseViewHandler.of(formId)) {
            IFormView view = vh.openAddNewViewAndInit(initData);
            process(view);
        }
    }

    /** 同步处理当前视图；具体业务自行实现，方法返回前完成使用。 */
    protected abstract void process(IFormView view);
}
```

## 调试、关闭与使用边界

| 调试方法 | 返回 |
|---|---|
| `peek()` | `Map<String, ?>`，当前模型的调试表示，不是全库或不可变深快照 |
| `peekUIMsg()` | `Map<String, ?>`，查看已缓冲的部分 UI 消息；不等于前端已展示 |
| `peekUIMsgFlat()` | `List<String>`，扁平化 UI 消息 |
| `flatList(String field)` | `List<?>`，提取指定字段的扁平值 |

没有 view 时四个调试方法返回空集合，不将其当作业务空数据或成功证明。成功打开后的输出仍须按业务数据脱敏；UI 消息并非全部操作成败的证明，细节见 [FormUtils](form-utils.md)。

- 默认用 `AutoCloseViewHandler` 的 try-with-resources；使用普通 `ViewHandler` 时在 `finally` 调用 `closeView()`。关闭先清除模型 dataChanged 标记，再关闭及释放会话/控制器；它不是保存、提交或回滚，释放后不要访问模型。
- 包装关闭/释放路径会记录部分异常而不重抛，初次创建失败也可能尚未将 view 赋给 handler。try-with-resources 不能保证所有失败分支均清理成功；有创建或释放异常时按平台日志核查残留，不把正常返回等同于全部资源已释放。
- 异步任务仍需有效的平台执行上下文、可用会话/元数据服务及独立的 handler；AutoCloseable 只处理关闭，不创建租户身份、传播事务或提供线程安全。按需读 [线程池](../base/sdk/sdk-threadpool.md) 与 [请求上下文](../base/sdk/sdk-request-context.md)。
- 主键和组织 ID 以目标实体及实际 API 支持的类型为准；Object 参数不表示任意 JSON 数值都可直接传入。自定义 PageId 要避免跨用户和并发冲突。
- 大参数确需页面缓存时按 [缓存合同](../base/sdk/sdk-cache.md) 选择生命周期、隔离和清理方式；不能用一个 CacheKey 自动解决跨用户访问。前台返回处理通过 `CloseCallBack`/`closedCallBack`，不套用到后台资源关闭。

简短依据：[官方视图模型](https://vip.kingdee.com/knowledge/221674425806898944)、[FormShowParameter V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/index.html?nav=class&package=kd.bos.form&name=FormShowParameter)、[BillShowParameter V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/index.html?nav=class&package=kd.bos.bill&name=BillShowParameter)。静态核验和离线编译仅证明对应构件的签名/类型，不代表平台运行通过。
