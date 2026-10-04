# 业务操作与操作链 OpUtils / OperateChain

详细知识、官方来源与验证边界：[云端专题](https://chatgpt.com/space/page_2b50d50ff9c4819185f5844aafffd657)。

## 范围与版本

单次保存、提交、审核等可复用 `kd.cd.common.operate.OpUtils`；多步操作使用 `kd.cd.common.operate.chain.OperateChain`。它们是项目包装，本页核于 `kd-cd-cosmic-commons` 的 `RELEASE-26-0424`（manifest 声明 `Cosmic-Version: 7.0+`），不是所有苍穹工程自动具备的原生 API。事务与平台结果以目标依赖、操作配置和调用上下文为准。

下推/选单读 [BOTP](../botp-convert.md)，事件与字段准备读[操作插件](../base/plugin/plugin-operation.md)，事务传播读[事务合同](../base/sdk/sdk-tx.md)。

## OpUtils 已核 API

| 能力 | 方法与重载 | 返回/边界 |
|---|---|---|
| 执行并检查 | `executeOperateOrThrow(String opKey, String entityId, DynamicObject[] dataEntities)`；末尾可加 `OperateOption`；数据参数也可为 `Object[] pks`，同样有带 option 重载 | 四个重载返回 `OperationResult`；失败时抛 `OperationFailureException`。包装本身不调用 TX 回滚，不能保证先前操作被撤销。 |
| 手动结果检查 | `throwIfFail(OperationResult)` | 检查 `isSuccess()`，失败抛同类异常；可复用它，也可明确处理结果，不能忽略失败。 |
| 补偿删除 | `rollbackAndDelete(String entityId, Object pkValue)` / `(String, Object, boolean)`；`rollbackAndDelete(IFormView)` / `(IFormView, boolean)` | 返回补偿 `OperateChain`，某些未取得状态/不存在分支返回 null；boolean 默认 false，控制每阶段新事务，不是数据库隔离级别。 |
| 字段准备 | `List<String> prepareEntryFields(MainEntityType, String... entryKeys)`；`List<String> prepareAllFields(MainEntityType)` | 按包装遍历/过滤规则生成字段清单，不是无条件加载每一种属性。显式核实际用到的字段；全量方式仅在确需通用插件能力时使用。 |
| 操作错误 | `addErrorMessage(AbstractOperationServicePlugIn, DynamicObject, String message)`；带 `title, message` / `title, errCode, message` 重载 | 3 个重载保留；回填错误信息不等于调用方已正确结束操作或事务。 |
| 校验错误 | `addValidatorErrorMsg(AbstractValidator, ExtendedDataEntity, String errCode, String message)`；`addValidatorMsg(..., String errCode, String message, ErrorLevel)` | 记录校验错误/指定级别信息；消息按项目多语言规则处理。 |
| 错误对象 | `OperateErrorInfo newErrorInfo(DynamicObject, String title, String errCode, String message)` | 构造错误信息；按真实对象与脱敏规则输出。 |
| 消息提取 | `String getCompleteFailMsg(OperationResult)` / `(OperationResult, String separator)`；`getErrorOrValidateMsg(OperationResult, String separator)`；`getErrorOrValidateMsgRaw(OperationResult, String separator)` | 聚合结果已有消息，不等于掌握所有外部副作用或所有分录状态。 |
| 操作名称 | `String getChsName(String entityId, String opKey)` | 读取配置中的操作中文名，不能猜实际操作 Key。 |

`executeOperateOrThrow` 会在传入/创建的 option 中设置 `ishasright="true"`。操作链的默认全局控制另含 `ignoreinteraction`、`ignoreconfirm`，合并时会覆盖同名参数。按实际权限与交互合同核这些设置；不能把包装默认参数当作业务授权，也不要假定传入的 option 原样不变。

## OperateChain 已核 API

- 工厂：`of(String entityId, Object pkValue)`、`of(DynamicObject)`、`of(IFormView)`。数据包方式首阶段使用对象，成功后改用主键；视图方式调用 `IFormView.invokeOperation`，不能把它与服务端入口混同。
- `save()`、`submit()`、`submitNoWF()`、`audit()`、`unSubmit()`、`unAudit()`、`delete()` 均有末尾 `OperateOption` 重载，返回操作链。`submitNoWF` 通过 `WF="false"` 请求不触发工作流；实际流程行为仍核目标配置。
- `operate(String opKey)`、`operate(String opKey, OperateOption)` 执行自定义操作，返回操作链。
- `isSuccess()` 查看最后阶段结果；空链为 false。收到失败结果后后续操作短路；服务直接抛出的异常仍向外传播，不能当作已自动补偿。
- `storage()` 返回 `ChainStorage`，可取 `getErrMsg()`、`getLastOperationResult()`、`getAllStages()`、`getPkValue()` 和 `getRollBackChain()` 等结果。原操作链与补偿链的结果分别检查。
- `failThenDelete()` 返回原链的 `ChainStorage`，失败时尝试补偿；`failThenDeleteAndThrow()` / `(String tip)` 在失败补偿后抛异常；`failThenThrow()` / `(String tip)` 只在失败时抛异常。这些终结方法均声明返回 `ChainStorage`。
- `requireNewTXForEachStage(boolean)` 返回操作链；`getGlobalOptionControl()` 返回 `OptionControl`，供已确认的参数控制使用。

## 事务与补偿合同

`OrThrow` 的核心合同是失败结果转异常。是否回滚取决于真实事务是否仍覆盖该操作、异常如何穿过事务边界，以及操作/平台自身的事务处理；操作插件也有事务外事件，不能笼统说调用都加入当前事务。`OperationResult.isSuccess()==false` 表示未完全成功，不证明所有记录都失败或此前写入全部回滚。

`requireNewTXForEachStage` 默认 false，此时包装直接执行每一阶段，不额外建立覆盖整条链的事务；它不自动赋予整链原子性。true 时逐阶段经 `TXSupport.NEW` 调用 `TX.requiresNew()`，属于事务传播选择。已完成的独立阶段不因之后调用 `failThenThrow` 就全部撤销；需按真实事务边界设计恢复。

`rollbackAndDelete` 是按状态执行反向业务操作的补偿链：本版状态 `C` 走反审核→删除，`B` 走撤销提交→删除，`A` 和其他非 null 状态走删除。它不是数据库 rollback，也不是任意状态/流程都能安全撤销的保证。仅用于明确允许删除的目标（例如本业务新建且可补偿的单据），执行前核目标状态编码与操作规则。

补偿也可能失败、被短路或直接抛异常。`failThenDelete` 正常返回、补偿链为 null、或原链仍失败都不能解释为“已删除”；分别保留原结果、补偿结果和待恢复状态，必要时按业务证据核删除是否最终完成。

## 完整示例

下面仅展示已核调用与结果处理。实体、主键、操作 Key、权限、事务范围和可补偿对象由实际业务提供；不用于直接操作未知现有单据。

```java
package kd.cd.common.demo;

import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.entity.operate.result.OperationResult;
import kd.cd.common.operate.OpUtils;
import kd.cd.common.operate.chain.ChainStorage;
import kd.cd.common.operate.chain.OperateChain;

public final class OpDemo {
    public OperationResult auditBill(String entityId, Object pkId) {
        return OpUtils.executeOperateOrThrow("audit", entityId, new Object[]{pkId});
    }

    public ChainStorage chainOperation(DynamicObject dataEntity, String nextOpKey) {
        OperateChain chain = OperateChain.of(dataEntity);
        chain.save().submit().audit().operate(nextOpKey);
        // 抛出失败，不承诺此前阶段已回滚。
        return chain.failThenThrow("操作链未完成：");
    }

    // 仅在该业务明确允许失败后删除目标时调用。
    public ChainStorage compensateFailedChain(OperateChain chain) {
        if (chain.isSuccess()) return chain.storage();
        ChainStorage storage = chain.failThenDelete();
        OperateChain compensation = storage.getRollBackChain();
        if (compensation == null) {
            throw new IllegalStateException("未取得补偿结果；原操作：" + storage.getErrMsg());
        }
        if (!compensation.isSuccess()) {
            throw new IllegalStateException("补偿失败：" + compensation.storage().getErrMsg()
                    + "；原操作：" + storage.getErrMsg());
        }
        return chain.failThenThrow("原操作失败，补偿操作返回成功：");
    }
}
```

字段准备保留项目扩展基类能力；以下分录标识须替换为真实元数据。公共插件确需更广清单时，可在同一追加位置用 `allFields()` 替代 `entryFields(...)`，不要连续 `setFieldKeys` 覆盖前一次结果。包装清单有过滤规则，必需字段仍按实际模型补充。

```java
import kd.bos.entity.plugin.PreparePropertysEventArgs;
import kd.cd.common.plugin.AbstractOperationServicePlugInExt;

public final class MyOperationPlugin extends AbstractOperationServicePlugInExt {
    @Override
    public void onPreparePropertys(PreparePropertysEventArgs e) {
        e.getFieldKeys().addAll(entryFields("entry1", "entry2"));
    }
}
```

## 执行前后检查

- 主键数组使用目标模型的真实类型；链内部还使用项目 `EntityUtils.isEmptyPk`，其值类型边界见[实体元数据包装](entity-metadata.md)。不把“混合类型必然找不到”或所有主键都是 Long 当作通用合同。
- 已审核单据再次审核是否允许，由操作配置、校验和当前状态决定；先核规则，不硬编码“必然失败”。
- 返回失败要明确处理或抛出；不要吞掉服务直接异常后继续报告成功。补偿是显式业务动作，不能为了隐藏原失败而无条件删除已有单据。
