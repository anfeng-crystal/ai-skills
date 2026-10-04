# 工作流插件

## TL;DR
- 适用：工作流运行期扩展，处理参与人、条件、通知和审批记录定制。
- 先抓：`IWorkflowPlugin` 及其接口事件；这是接口型插件，不是常规 `super` 生命周期。
- 跳转：普通单据审核流转别误用本页；那通常是操作插件或下推链路。
- 继续读全文：当你要写动态审批人、条件分支或流程通知时。

## 概述
工作流插件用于在流程运行时参与参与人计算、条件判断、流程通知和审批记录格式化。

> **适用边界**
> ✅ 本文档直接使用：原生 `IWorkflowPlugin` 是带默认方法的接口。没有类继承式的 `super` 生命周期要求；确需委托接口默认实现时可调用 `IWorkflowPlugin.super.<方法>(...)`。项目已继承自有工作流基类时仍核对其行为。

- 适用场景：动态审批人、条件分支、流程通知、审批记录定制

## 核心基类

- 基类：`kd.bos.workflow.engine.extitf.IWorkflowPlugin`

## 核心事件

- `calcUserIds(AgentExecution execution)`：参与人计算阶段触发。
- `hasTrueCondition(AgentExecution execution)`：条件分支判断阶段触发。
- `notify(AgentExecution execution)`：流程通知阶段触发。
- `notifyByWithdraw(AgentExecution execution)`：流程撤回阶段触发。
- `formatFlowRecord(IApprovalRecordItem item)`：审批记录展示格式化时触发。

## 插件内上下文方法

以下更适合作为 `AgentExecution` 上的上下文访问能力，而不是插件“事件”：

- `execution.getBusinessKey()`
- `execution.getEntityNumber()`
- `execution.getCurrentFlowElement()`
- `execution.getVariable(...)`
- `execution.setVariable(...)`
- `execution.getCurrentTaskResult(WFTaskResultEnum.auditMessage)`：返回 `Object`，按需要选择真实结果枚举并处理相应值类型。
- `execution.getStartUserId()`
- 参与人计算通过 `calcUserIds` 返回 `List<Long>`；实际 7.0 `AgentExecution` 没有 `setAssigneeList`。

```java
String businessKey = execution.getBusinessKey();
Object amount = execution.getVariable("amount");
execution.setVariable("lastNodeName", "财务审核");
```

## 其他扩展点

以下方法存在于接口默认实现或扩展能力中，但不建议在模板里与核心事件同层表达：

- `filterParticipant(...)`
- `handleTask(...)`
- `afterHandleTask(...)`
- `afterCancelTask(...)`
- `aggregateBills(...)`
- `getJointAuditResult(...)`
- `getExpireTime(...)`
- `getBillPermissions(...)`
- `validatePlugin(...)`
- `resetYZJGroupProperty(...)`

## 示例代码

示例代码统一维护在模板文件中，直接参考：

- [IWorkflowPluginTemplate.java](../../../assets/IWorkflowPluginTemplate.java)

## 实践建议

1. 参与人计算和条件分支尽量独立实现，避免职责混杂。
2. `notify` 与 `notifyByWithdraw` 尽量成对设计，保证状态可恢复。
3. 耗时逻辑不要放在 `notify` 中阻塞流程。
4. 流程变量与单据数据是两套数据，要显式同步。
5. `IWorkflowPlugin.super.calcUserIds(execution)` 在实际 7.0 默认返回 `null`，不等于已计算参与人。实现业务计算时返回实际用户 ID 集合；空结果的后续处理依赖调用入口和流程配置，不能解释为自动沿用默认审批人或自动通过。
6. `execution.getStartUserId()` 读取框架发起人，`getVariable("startUserId")` 只是读取同名流程变量，二者不保证相同。模板保留流程变量示例；业务若要求框架发起人，应明确换用前者。

## 常见坑位

- 把 `execution.getVariable(...)`、`execution.getCurrentTaskResult(...)` 这类上下文访问方法写成插件事件，或照无参形式调用后者。
- 一个插件同时塞太多流程扩展点，后续维护困难。
- `notify` 修改了单据状态，但 `notifyByWithdraw` 没有补偿恢复。
- 计算了用户 ID 却未从 `calcUserIds` 返回，或把不存在的上下文 setter 当成返回结果的替代。
- 把任意节点阶段都当作拥有当前任务结果；取值须与注册事件时机对应。

## 依据与版本

[calcUserIds 事件](https://vip.kingdee.com/knowledge/226276242965135872)（更新 2026-07-31）明确返回参与人的 `List<Long>`，示例也保留合法的接口默认方法调用。[工作流审批信息示例](https://vip.kingdee.com/knowledge/571758914300221184)（更新 2026-07-30）使用 `WFTaskResultEnum.auditName` / `auditMessage` / `auditNumber` 获取不同结果，并区分任务处理与离开节点的上下文。本文签名与默认返回值另经实际 7.0 工作流 JAR 核验；未据示例声明任意阶段都能取得审批人/结果，也不据此改动业务单据。
