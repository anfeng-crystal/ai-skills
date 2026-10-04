# 分布式事务与本地事务 (KDTX / TX)

## 适用与选型

普通单库操作先沿用本地事务。跨库、跨服务且允许失败后向前重试的业务，可考虑 KDTX 最终一致性；需要撤销已占用资源时，读下方 TCC 的 Try/Confirm/Cancel 合同。最终一致性不能回滚已完成的远端业务，不是所有同步需求的默认模式。

本卡依据官方最终一致性与 TCC 案例、V7.0.1 Javadoc，并以本地实际 7.0 JAR 核对签名；最终一致性案例未标适用版本，TCC 插件特性范围见专节。编译兼容不证明目标部署、数据库提交或故障恢复已验证。

## 最终一致性：注册与执行入口

| 类/方法 | 已确认合同 |
|---|---|
| `kd.bos.kdtx.sdk.session.ec.ECGlobalSession.begin(String scenesCode, DBRoute dbRoute)` | 开始全局事务；作用域为当前 Request 请求上下文，可跨方法、插件使用 |
| `ECGlobalSession.register(String cloudId, String appId, String serviceName, Param param, String branchScenesCode)` | 注册分支；返回 `void`，不是可链式 `addProperty` 的任务 |
| `kd.bos.kdtx.common.Param` | 业务参数接口，继承 `java.io.Serializable`；实现对象的属性也需可序列化 |
| `kd.bos.kdtx.sdk.api.EventualConsistencyService.execute(Object param, Object lastReturn)` | 返回 `kd.bos.kdtx.common.invoke.DtxResponse`，可抛 `Exception`；入参分别为当前业务参数、前一个服务的返回值 |
| `kd.bos.kdtx.sdk.ext.provider.BaseECService.doExecute(Object, Object)` | 官方案例使用的另一种服务基类扩展点，`protected`、返回 `DtxResponse`、可抛 `Exception`；不要与上一行的 `execute` 混写 |

业务参数使用项目约定的 `Param` 实现，注册端与执行端保持同一结构；不要直接假定任意 `DynamicObject` 都可跨节点序列化恢复。参数反序列化、类部署及升级兼容需在目标环境验证；`lastReturn` 与当前参数是独立输入。

本地 7.0 的 `EventualConsistencyService` 没有 `register/invoke/getProperty/addProperty`。服务子类应重写 `execute`，按已约定的参数类型取值。幂等键与失败处理按实际业务确定，不能吞异常或无条件返回成功掩盖同步失败。

## 接入顺序、服务发现与提交边界

1. 确认全局场景、当前本地数据库路由、参与应用及最终一致性模式。官方案例在操作插件 `beginOperationTransaction` 中调用 `begin`，在 `endOperationTransaction` 注册分支；这不是任意事件都可照搬的事务模板。
2. `cloudId/appId/serviceName` 定位参与服务。官方案例按 `kd.<cloudId>.<appId>.servicehelper.ServiceFactory` 提供工厂，将服务名映射到实现类；私有云节点还需对应应用路由。沿用目标应用真实服务发现/部署方式，不能只写服务类就宣称完成注册。
3. 区分全局场景编码（`begin` 第一参）、服务名（`register` 第三参）、分支场景编码（第五参）。V7.0.1 Javadoc 将第五参标为可选，传入时检查场景是否存在。知识库案例把“场景编码”指向第三参，示例中的名称恰好相同；不要据此混同三个含义。
4. 官方案例随后调用 `ECGlobalSession.txCommit()`；Javadoc 明确它是**手动事务提交**。本地 7.0 字节码显示其调用当前 `TXHandle.commit()`，不能解释为“只登记，等最外层自动提交”。接入前核实谁拥有事务、后续校验/回滚是否仍应覆盖本次写入，不能为触发分支随意提前提交共享事务。
5. Javadoc 还提供 `setAsync(boolean)` 和 `setProcessMode(boolean waitAllDone, boolean oneByOne)`，不能笼统承诺注册都异步、严格顺序或必定等待全部分支。按目标配置核实执行方式。

最终一致性通过重试推动业务完成，执行逻辑应幂等；重试次数、间隔、最终失败处置与补偿以实际场景配置为准。验收检查事务查询日志、主事务和分支结果，并覆盖分支失败、重复执行。注册返回、编译通过或主单保存成功均不代表远端业务已完成。

## TCC：绑定操作的本地事务

适用于“本单审核 + 余额预占 + 序列资源预占”等必须在 Try 失败时取消本单操作的场景。官方插件接入特性适用 **V5.0.002 及以上**；以下签名由 V7.0.1 Javadoc 与实际 7.0 依赖核对。Try 预留资源，Confirm 完成业务变更，Cancel 释放预留；不能用空方法或无条件成功构成所谓一致性保证。

| 入口 | 合同 |
|---|---|
| `kd.bos.kdtx.sdk.session.tcc.TCCGlobalSession.Try` | 大写 `Try`、静态、返回 `void`、可抛 `TCCTryException`；插件本地事务中调用 |
| `kd.bos.kdtx.sdk.api.TCCAdapterService` | 子类重写 `Try(Object)`、`confirm(Object,Object): DtxResponse`、`cancel(Object)`；三者可抛 `Exception`。其 `doTry/doConfirm/doCancel` 在实际 7.0 为 `final`，不要重写 |
| `kd.bos.kdtx.sdk.api.TCCService` | 直接实现接口时才实现 `doTry/doConfirm/doCancel`；不能与适配器子类方法混写 |
| `kd.bos.kdtx.common.invoke.DtxResponse` | Confirm 的业务返回对象，`lastReturn` 是上个分支返回值；本地接口没有统一 `isSuccess/getCode` 等状态读取方法，不猜成功码 |

### 接入与注册

1. 先定义资源预占、确认、撤销的真实业务状态与可序列化 `Param`。区分业务幂等键与事务/分支 ID；重复调用、资源不足、超时和未知结果都要有可验证处置。
2. 复用参与应用的服务工厂与路由。本地 7.0 调用链按 `kd.<cloudId>.<appId>.servicehelper.ServiceFactory` 定位应用工厂，再反射调用 **`public static getService(String serviceName)`，返回实际服务实例**。文章的字符串 Map 只是注册示意，不是完整工厂实现；不要用 SDK 内部同名工厂的 `putService` 取代目标应用服务发现。类部署、应用路由及协调器可用性均属于目标接入验收。
3. 官方案例在操作插件 `beginOperationTransaction` 内调用静态 `Try`。下面仅封装调用，参数由调用方从真实场景配置、目标依赖和当前本地事务取得；不另开或手动提交共享事务。

```java
import kd.bos.db.DBRoute;
import kd.bos.kdtx.common.Param;
import kd.bos.kdtx.common.exception.TCCTryException;
import kd.bos.kdtx.sdk.session.tcc.TCCGlobalSession;

/** Called by an operation plug-in while its local transaction is active. */
public final class TccOperationBranch {
    private TccOperationBranch() { }

    public static void reserve(String scenesCode, String cloudId, String appId,
            String serviceName, Param param, String branchScenesCode,
            DBRoute localRoute) throws TCCTryException {
        TCCGlobalSession.Try(scenesCode, cloudId, appId, serviceName,
                param, branchScenesCode, localRoute);
    }
}
```

`scenesCode` 为全局场景编码，`serviceName` 为服务名；`branchScenesCode` 可选，传入时会校验场景存在。`localRoute` 要与当前事务真实写入路由一致，不从全局固定库名猜测。SDK 还提供 6 参（无显式路由）和 8 参（含业务 ID 集合）等重载；使用前核对目标依赖与路由获取条件。

实际 7.0 静态 `Try` 会校验当前本地事务、事务传播、已有分布式事务类型及本地事务 ID，并关联本地事务监听；缺会话时由该入口建立所需会话。不要把 EC 的 `txCommit()` 模板套到 TCC，`TCCGlobalSession` 没有该静态方法。需要显式 `begin(scenesCode, route, isReentrant)` 时另核重入语义，不能将该 boolean 当异步开关。

### 失败、恢复与完成判定

- Try 失败应让本地操作失败并进入已设计的撤销路径；不能 catch 后继续报告审核成功。Confirm/Cancel 的恢复和重复调用由实际场景与协调器配置驱动，必须验证业务状态不会重复扣减或重复释放。已决定提交后的 Confirm 失败应按恢复合同处理，不能宣称自动撤销已提交的本地主事务。
- V7.0.1 `TCCAdapterService` 文档包含空回滚、防悬挂及部分幂等处理；这些基础处理不替代业务资源预占、幂等和恢复设计，不外推为所有业务自动正确。
- `setAsync(boolean)` 控制提交/回滚是否异步；`Try` 正常返回只表明该预留步骤完成，不能当作所有 Confirm 已执行的证明。检查本地操作结果、主事务及各分支结果、资源业务状态；故障场景至少覆盖资源不足、本地操作回滚、Confirm/Cancel 重试和重复调用。
- 普通本地数据库回滚不能自动撤回已完成的外部 HTTP 行为。不得在业务未定义补偿的情况下承诺跨系统原子性；同样不因使用 TCC 就主动改变用户既有事务、权限或部署方式。

官方部署文档将 `kdtx-server` 作为协调器，并给出事务查询页及系统库表检查方法；文档最低代码版本为 BOS_V4.0.006，不能替代本插件特性的 V5.0.002 门槛。使用目标环境现有部署配置做只读确认；旧文中的节点资源和线程池建议不能无核实直接写入当前环境。

## 本地 TX：保留调用方事务边界

`kd.bos.db.tx.TX.required(String tag)` 有事务时加入，否则新建；`requiresNew(String tag)` 开启新事务，不能为了尽快提交替换 `required`。不要在本地事务块执行耗时外部 HTTP，也不要在 DataSet 所属事务关闭后继续使用它。

下面只包装本地写入：正常退出由句柄关闭处理，业务异常先标回滚再保留原异常向上传播。若加入外层事务，离开本方法不代表最外层已提交。

```java
import kd.bos.db.tx.TX;
import kd.bos.db.tx.TXHandle;

public final class LocalTransactionWork {
    public static void run(Runnable localWrites) {
        try (TXHandle tx = TX.required("app_bill_localwrites")) {
            try {
                localWrites.run();
            } catch (RuntimeException | Error ex) {
                tx.markRollback();
                throw ex;
            }
        }
    }
}
```

`Runnable` 是此例的业务边界；实际代码若抛受检异常，同样在本作用域标回滚后原样抛出。不要把显式 `commit()` 当作嵌套作用域的成功标记。通知/外部同步接已确认的提交后入口或可靠事务任务，不能仅因保存方法返回而发送；另见[事务回滚案例](../../issue-analysis/examples.md#案例二十五事务回滚导致的数据不一致)。

## 官方依据

- [如何通过KDTX实现分布式事务（最终一致性）](https://vip.kingdee.com/knowledge/590315739999976448)，更新于 2026-07-30 03:22，未标适用版本；2026-10-02 已登录读正文。
- [ECGlobalSession · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/kdtx/sdk/session/ec/ECGlobalSession.html)：注册参数、执行方式和手动提交。
- [EventualConsistencyService · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/kdtx/sdk/api/EventualConsistencyService.html) 与 [Param · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/kdtx/common/Param.html)：执行、参数合同。
- [TX · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/db/tx/TX.html) 与 [TXHandle · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/db/tx/TXHandle.html)：传播、关闭、回滚。采用方法表及实际 JAR 的 `requiresNew`，不复制文档片段的 `requireNew` 拼写。

- [插件中使用 KDTX TCC](https://vip.kingdee.com/knowledge/338326404326484736)，更新于 2026-07-30 11:59，适用 V5.0.002+；2026-10-02 已登录读取正文。
- [TCCGlobalSession · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/kdtx/sdk/session/tcc/TCCGlobalSession.html) 与 [TCCAdapterService · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/kdtx/sdk/api/TCCAdapterService.html)：本地事务关联、重载、适配器方法与边界。
- [KDTX 分布式事务部署文档](https://vip.kingdee.com/knowledge/220645444102566144?productLineId=29&isKnowledge=2&lang=zh-CN)，更新于 2023-11-14 17:02；2026-10-02 已登录读取正文，部署配置仍核对当前目标。
