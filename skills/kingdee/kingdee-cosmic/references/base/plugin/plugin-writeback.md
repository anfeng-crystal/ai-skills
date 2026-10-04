# 单据反写插件

## TL;DR
- 适用：反写插件，处理下游结果回写上游、超额校验、行关闭和补偿。
- 先抓：`AbstractWriteBackPlugIn` 的回写事件顺序，先区分下推阶段和反写阶段。
- 跳转：只是调用下推/选单业务动作时，优先读 `adv/botp-convert.md`。
- 继续读全文：当你要改数量金额反写、关闭控制或回滚补偿逻辑时。

## 概述
单据反写插件用于下游单据在保存/审核等操作时，把计算结果反写回上游单据，并参与关闭行、超额检查、保存回滚等完整流程。

> **适用边界**
> ✅ 本文档是原生兜底：反写插件没有 Ext 封装，直接读本文档。
> ❌ 下推/选单的业务调用优先用 `BotpUtils`，参见 `references/adv/botp-convert.md`。

- 适用场景：数量金额反写、上游行关闭控制、超额校验定制、反写补偿

## 核心基类
- 基类：`kd.bos.entity.botp.plugin.AbstractWriteBackPlugIn`
- 继承关系：`AbstractWriteBackPlugIn implements IWriteBackPlugIn`

## 核心事件

- `preparePropertys`：// 读取下游目标单前，准备所需目标字段
- `beforeTrack`：// 构建关联记录前，可取消本关联主实体反写
- `beforeCreateArticulationRow`：// 构建单行关联记录前，可取消该行反写
- `beforeExecWriteBackRule`：// 分析当前反写公式前，可取消当前公式条目
- `afterCalcWriteValue`：// 反写值计算后，修正分配量
- `beforeReadSourceBill`：// 读取源单前，准备源单字段
- `afterReadSourceBill`：// 读取源单后，补充第三方数据
- `afterCommitAmount`：// 反写写入源单行后，做连锁更新
- `beforeExcessCheck`：// 超额检查前，可取消检查
- `afterExcessCheck`：// 超额检查后，决定提示/中断
- `beforeCloseRow`：// 关闭上游行前，可跳过本次该行的关行处理
- `afterCloseRow`：// 上游行关闭状态写入后
- `beforeSaveTrans`：// 开启保存事务前，准备第三方数据
- `beforeSaveSourceBill`：// 源单保存前
- `afterSaveSourceBill`：// 源单保存后
- `rollbackSave`：// 保存失败回滚补偿
- `finishWriteBack`：// 反写结束释放资源（如网控）

## 取消的范围

| 入口 | 取消作用范围 | 不能据此推断 |
|---|---|---|
| `beforeTrack` 的 `setCancel(true)` | 本关联主实体的关联与反写 | 仅取消一条反写公式 |
| `beforeCreateArticulationRow` 的 `setCancel(true)` | 当前关联数据行的关联与反写 | 只暂停关行 |
| `beforeExecWriteBackRule` 的 `setCancel(true)` | 当前 `getRuleItem()` 返回的反写公式 | 一次调用已禁用整张反写规则的全部公式 |
| `beforeCloseRow` 的 `setCancel(true)` | 当前源单行本次关行处理 | 不检查条件直接强制关闭该行 |

实际 7.0 对同一规则逐公式触发 `beforeExecWriteBackRule`，事件 `setContext(rule, ruleItem)` 每次重置取消标记。按已确认的规则、公式标识逐次判断；若业务要求停用整个规则，需要对该规则的每个公式都作出取消决定，不缓存“已处理一次”后跳过后续条目。

实际 7.0 `CloseRowLogic` 检查 `beforeCloseRow` 的取消标记后直接继续下一行，因此该行的关闭条件计算、关闭成功/失败状态填写和 `afterCloseRow` 均不再执行。它不撤销此前反写值，不取消循环后的整单关闭判断或整个保存，也不是强制关行开关。事件自身属性名是 `isCancel()` / `setCancel(boolean)`，不要根据手册概述中的 `IsCancelCheck` 拼造方法。

## 插件内上下文方法

```java
// 上下文
BillEntityType targetSubMainType = this.getTargetSubMainType();
String opType = this.getOpType();  // Draft/Save/Audit/UnAudit/Delete/...
LinkSetItemElement currLinkSetItem = this.getCurrLinkSetItem();
```

- `setContext(...)`：框架设置当前上下文的初始化入口；直接继承基类的上下文 getter，不用返回 `null` 的占位实现覆盖它们。`preparePropertys` 早于此入口，目标实体类型从 `e.getMainType()` 读取，不能依赖上述 getter 已初始化。

## 示例代码

示例代码统一维护在模板文件中，直接参考：

- [WriteBackPlugInTemplate.java](../../../assets/WriteBackPlugInTemplate.java)

## 实践建议

1. `preparePropertys` 与 `beforeReadSourceBill` 必须明确字段准备，避免后续空值。
2. 超额场景优先在 `afterExcessCheck` 做统一提示策略。
3. `beforeSaveTrans` 在开启保存事务前，可预读待保存的第三方数据；不能据此把外部系统写入视为受本地事务保护。`beforeSaveSourceBill` / `afterSaveSourceBill` 的 `e.isNewThread()` 为 `true` 时是跨库异步保存，不能靠抛异常取消反写或保证回滚；`rollbackSave` 也不构成外部系统原子性保证。
4. 资源申请（网控、缓存句柄）必须在 `finishWriteBack` 释放。

## 常见坑位

- 忽略 `rollbackSave`，保存失败后外部系统数据不一致。
- 在 `beforeExcessCheck` 一律取消检查，导致业务失控。
- `beforeTrack`/`beforeCreateArticulationRow` 误取消后反写缺失。
- `finishWriteBack` 未释放资源引发后续并发问题。

依据：[社区帮助中心《反写插件手册》](https://vip.kingdee.com/article/407846501084544512?productLineId=29&isKnowledge=2)，正文适用金蝶AI苍穹 4.0.004 以上，更新于 2026-08-03。手册事件参数段明确取消的是“本反写公式”，比概述“当前反写规则”更精确；关行段仅说不再做条件检查，本文补充的整行跳过分支以实际 7.0 JAR 为据。上下文初始化、取消消费及 `isNewThread()` 合同均按目标 SDK 核对，不外推其他版本或业务运行结果。
