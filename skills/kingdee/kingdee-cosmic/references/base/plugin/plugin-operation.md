# 单据操作插件

## TL;DR
- 适用：服务端单据操作插件，用于校验、状态转换和级联同步；各事件的事务边界不同。
- 先抓：`AbstractOperationServicePlugIn` 的事件顺序，先分清事务前、事务中和事务后。
- 跳转：若 `AbstractOperationServicePlugInExt` 足够，优先回 `adv/plugin-base.md`；纯 UI 联动别读本页。
- 继续读全文：当你要确认 `onPreparePropertys`、回滚边界、预置操作清单或常见误用时。

## 概述
单据操作插件在服务端干预保存、提交、审核、删除等操作，包含事务前、事务内和提交后的事件；不能把所有回调都当作有同一事务保护。

> **适用边界**
> ✅ 本文档是原生兜底：当 `plugin-base.md`(封装层) 未覆盖你需要的操作事件时使用。
> ❌ 如果封装层 `AbstractOperationServicePlugInExt` 已满足需求，优先读 `references/adv/plugin-base.md`。

- 适用场景：单据操作的权限校验、数据校验、状态转换、级联数据同步
- 执行环境：**服务端**，事务边界见下方事件说明。

## 核心基类
- 基类：`kd.bos.entity.plugin.AbstractOperationServicePlugIn`
- 继承关系：`AbstractOperationServicePlugIn implements IOperationServicePlugIn, IOperationService`
- 执行位置：**服务端**。

## 核心事件（时间顺序）

- `onPreparePropertys(PreparePropertysEventArgs e)`：// 加载单据数据包前触发；用于补齐操作所需字段，避免后续取值为空
- `onAddValidators(AddValidatorsEventArgs e)`：// 校验器加载完毕后、执行校验前触发；用于增删校验器
- `beforeExecuteOperationTransaction(BeforeOperationArgs e)`：// 校验通过后、开启事务前触发；用于最后整理数据
- `beginOperationTransaction(BeginOperationTransactionArgs e)`：// 事务开启后、数据库提交前触发；用于事务内同步处理
- `endOperationTransaction(EndOperationTransactionArgs e)`：// 数据写库后、事务提交前触发；用于事务内后置处理
- `rollbackOperation(RollbackOperationArgs e)`：// 事务提交失败回滚后触发；用于无事务资源补偿
- `afterExecuteOperationTransaction(AfterOperationArgs e)`：// 事务提交后触发；用于消息通知、日志等后续处理

## 插件内上下文方法

```java
// 引擎注入上下文后，在插件实例方法中使用
MainEntityType billType = this.billEntityType;  // kd.bos.entity.MainEntityType
Map<String, Object> meta = this.operateMeta;
OperationResult result = this.getOperationResult();

// 获取自定义参数
OperateOption options = this.getOption();  // kd.bos.dataentity.OperateOption
String customParam = options.getVariableValue("paramKey", "");

// 修改返回提示不等于执行校验、保存或回滚
result.setMessage("处理结果提示");
```

逐单错误使用 `addErrorInfo(OperateErrorInfo)`，业务校验优先使用校验器；`setSuccess(false)` 仅设置结果状态，不能代替事务异常或取消机制。以上类型、参数与结果方法以 [V7.0.1 操作插件](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/entity/plugin/IOperationServicePlugIn.html)及 [AbstractOperationResult](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/entity/operate/AbstractOperationResult.html) 为据，目标依赖仍须匹配。

## 示例代码

示例代码统一维护在模板文件中，直接参考：

- [OpPluginTemplate.java](../../../assets/OpPluginTemplate.java)

## 实践建议

1. **必须理解状态转换逻辑**
   - 单据状态有固定转换路径，不是任意转换
   - 同一操作绑定多个插件时避免重复状态转换

2. **onPreparePropertys中不要漏字段**
   - 若操作依赖某字段，必须在此添加
   - 否则系统加载的数据包会缺失此字段

3. **规则校验优先放onAddValidators，事务前事件只做最后整理**
   - 明确的业务规则优先注册校验器，失败会在事务开启前阻断
   - `beforeExecuteOperationTransaction` 更适合最后整理数据、轻量兜底校验与整体取消

4. **区分写库和提交**
   - `beginOperationTransaction` 尚未写库，`endOperationTransaction` 已写库但尚未提交；两者都在当前操作事务内
   - 需要随主操作回滚的数据库更新必须参与该事务；外部服务、独立事务不因此获得回滚保护

5. **提交后的处理放afterExecuteOperationTransaction**
   - 此时主事务已提交，只放允许独立失败的后续动作，并处理重试与幂等
   - 需要与主操作原子完成的级联更新不能统一后移到此事件

## 基础资料异步删除：区分操作返回与物理删除

官方《基础资料异步删除》标注 V5.0 新特性。先核目标基础资料是否开启同名单据参数、是否带状态字段及实际运行版本，不能按按钮名称推断执行方式。

| 配置/阶段 | 官方描述的结果 |
|---|---|
| 开关关闭 | 同步检查引用；有引用不能删，无引用才物理删除 |
| 开关开启、带状态资料接收删除 | 先禁用并记录删除标记；页面返回不等于物理记录已经消失 |
| 后台检查无引用 | 后续执行物理清除 |
| 后台检查存在引用 | 保留禁用状态且不允许启用；不能仅因记录仍在就判断任务卡住 |

依赖最终删除结果的逻辑不能放在表单 `afterDoOperation` 中做结论或追加删除。官方正文建议移到 `AfterTransAction`，但该写法不能直接复制为 Java 方法名。V7.0.1 文档与实际 7.0 SDK 的服务端提交后入口为：

| 所在对象 | 真实调用 |
|---|---|
| `AbstractOperationServicePlugIn` | `afterExecuteOperationTransaction(AfterOperationArgs e)` |
| `AfterOperationArgs`（继承 `OperationArgs`） | `e.getOperationKey()`；不是表单事件的 `getOperateKey()` |
| 操作插件实例 | `this.getOperationResult()`；不是 `e.getOperationResult()` |
| `AfterOperationArgs` | `e.getDataEntities()` / `e.getSelectedRows()` 只包含**当前操作成功项** |

这是版本化 SDK 的提交后操作合同，尚不能仅凭该回调名认定它就是目标后台物理删除的完成点。将逻辑迁入前，确认插件挂载的真实操作阶段、后台任务及其结果；验收同时核查引用关系、状态/删除标记、任务结果和目标记录是否仍存在。`OperationResult.isSuccess()` 或成功数据包都不能独立证明后续异步步骤完成。需要原子完成的写入仍按事务内事件处理，不能统一搬到提交后。

“禁用资料不可删除”的业务校验可能阻止该后台任务继续删除。先定位具体校验及其业务用途，形成只影响已授权场景的调整方案；不能为修异步删除直接取消所有禁用校验、清引用或绕过平台强删。只读诊断先检查参数、已有校验和任务证据，不以批量删除试探原因。

依据：[基础资料异步删除](https://vip.kingdee.com/knowledge/319851087677120256?productLineId=29&isKnowledge=2&lang=zh-CN)，更新于 2026-07-30 12:23，2026-10-02 已登录读正文；[操作插件 V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/entity/plugin/IOperationServicePlugIn.html)、[AfterOperationArgs V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/entity/plugin/args/AfterOperationArgs.html)、[OperationArgs V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/entity/plugin/args/OperationArgs.html)。文章的异步行为与本地 API 编译证据分别成立，未据此声明目标环境已运行验证。

## 常见坑位

### ❌ 把所有校验都堆进beforeExecuteOperationTransaction
- 这样会弱化校验器机制，后续复用和错误定位都更差
- 明确规则优先放 `onAddValidators`，事务前事件只保留少量兜底检查

### ❌ 把endOperationTransaction当成提交后
- 此事件仍在事务内，失败可进入回滚；已写库不等于已提交
- `afterExecuteOperationTransaction` 才是提交后事件，后续失败不能撤销已提交的主事务

### ❌ 多个操作绑定同一状态转换
```java
// 错误：一级审批和会审都在同意时调用审核通过操作
// 导致单据从"已提交"试图再转为"已审核"->失败

// 正确：应在工作流配置中区分不同路径，操作插件不重复
```

### ❌ 在afterExecuteOperationTransaction里修改单据
- 此时主事务已提交，仅修改内存对象不会自动持久化
- 主操作需要保存的字段应在写库前准备；后续另行保存是独立动作，须明确其事务与失败处理

### ❌ 忽视onPreparePropertys导致字段缺失
```java
// 如果操作插件要读某字段但没在onPreparePropertys添加
// 系统加载的数据包就不含此字段，导致getValue返回null
```

### ❌ 在操作插件里查询与操作无关的数据
- 操作插件应只关注当前操作的单据数据
- 复杂查询逻辑优先写在服务层

## 预置操作清单

系统预置的可绑定操作（其他操作不支持操作插件）：

| 操作 | 功能 |
|------|------|
| save | 保存单据到数据库 |
| saveandnew | 保存后清空界面进入新增 |
| statusconvert | 切换单据状态 |
| submit | 提交单据（状态→已提交） |
| submitandnew | 提交后新增 |
| unsubmit | 撤销提交（回到暂存） |
| audit | 审核（状态→已审核） |
| unaudit | 反审核（状态→暂存） |
| disable | 禁用 |
| enable | 启用 |
| invalid | 作废 |
| valid | 生效 |
| delete | 删除 |
| donothing | 空操作（用于触发事件流程） |
