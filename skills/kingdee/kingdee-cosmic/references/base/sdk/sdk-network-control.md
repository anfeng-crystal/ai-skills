# 网络控制 (Data Mutex / NetCtrl)

实例上下文、时长资料冲突与证据范围见 [云端知识：网控实例与释放边界](https://chatgpt.com/space/page_84dfd3c11a188191964de7308f2137de)；本页保留执行合同与示例。

## 选路与生命周期

用于单据的功能互斥（冲突操作）和数据互斥（同一数据并发操作）。跨服务通用资源锁见 [分布式锁](sdk-lock.md)。标准页面和操作已有网控时，先核元数据和 `MutexHelper` 的管理边界，避免额外申请后释放了原页面仍需持有的锁。

- **编辑锁**：通常从进入编辑持有到退出编辑；不能套用方法结束即释放的短任务示例。
- **短操作锁**：确认申请成功后执行业务，结束时显式释放并检查结果。
- `DataMutex` 继承 `java.io.Closeable`；try-with-resources 关闭资源，**不等于释放已申请的业务网控**。申请返回失败不得继续业务，也不补一次无条件释放。

## 已核 API（V7.0.1 Javadoc / 实际 7.0 依赖）

|能力|真实签名或类型|注意|
|---|---|---|
|创建|`DataMutex.create()`|`kd.bos.mutex.DataMutex`|
|单条申请|`boolean require(MutexLockInfo info)`|实际类型 `kd.bos.mutex.impl.MutexLockInfo`|
|填写锁信息|无参构造及 `setDataObjId`、`setGroupId`、`setEntityNumber`、`setOperationKey`、`setStrict`、`setCallSource`|没有 `setEntityKey`；实体编码用 `setEntityNumber`|
|批量申请|`Map<String, Boolean> batchrequire(List<Map<String, Object>> data)`|方法名中的 `require` 确为小写；逐项检查|
|单条释放|`boolean release(String dataObjId, String entityKey, String operationKey)`|第二、三参是实体和操作，不能填互斥组|
|批量释放|`Map<String, Boolean> batchRelease(List<Map<String, Object>> data)`|逐项检查释放结果|
|占用信息|`Map<String, String> getLockInfo(String dataObjId, String groupId, String entityKey)`|与 `release` 参数语义不同；无参重载限同线程内使用，并复用同一 `DataMutex` 实例此前单条申请保存的上下文（本机已核 7.0 实现）|
|页面辅助|`kd.bos.form.operate.MutexHelper`|有页面/实体等重载，按目标页面生命周期选用，不能把 DataMutex 签名直接套过去|

同线程新建 `DataMutex` 不会继承另一实例的申请上下文；已知数据、组、实体标识或使用新实例诊断时，调用带参 `getLockInfo(dataObjId, groupId, entityKey)`。无参方法在新实例返回 `null` 不等于目标没有锁。此实例范围依据本机 `bos-mutex-7.0.jar`（manifest 分支 `hotfix_7.0.16_20250925`），不能仅凭在线“同线程”等表述推定跨实例共享，其他目标版本仍按实际依赖核验。

批量 Map 使用 `DataMutex.PARAMNAME_DATAOBJID`、`PARAMNAME_GROUPID`、`PARAMNAME_ENTITYKEY`、`PARAMNAME_OPERATIONKEY`、`PARAMNAME_ISSTRICT`；申请可补 `PARAMNAME_DATA_OBJ_NUMBER` 和 `PARAMNAME_DATA_CALL_SOURCE`。为避免把重入已有锁当作本次新获取，示例批量申请同样显式设 `PARAMNAME_ISSTRICT=true`。返回 Map 按数据 ID 给出布尔结果，不把非空 Map 当整批成功。部分成功时只对本次确认获取的锁执行业务/释放；需要“全成功才执行”时，先收集成功项，任一失败就释放已获项并报告失败。不要无条件对整批输入解锁。

## 分组、重入与异常

- `DataMutex.DEFAULT_GROUPID` 的值为 `default_netctrl`，用于与标准修改、提交、审核、删除等操作互斥。只有业务明确不需要与标准操作互斥时才用自定义组；改组不能作为规避已有冲突的修复。
- `isStrict=true` 表示有锁即失败，包括自己已有的锁；`false` 允许同 sessionId / userId 的重入条件。不能只凭“同用户”推断任意操作、客户端或页面都会成功；依实际锁和操作配置判断。
- `callSource` 用于区分标准操作与自定义申请来源，不是独占令牌或权限凭证。
- `getLockInfo` 可用 `KEY_USERID`、`KEY_SESSION`、`KEY_OPKEY`、`KEY_LOCKEDTIME`、`KEY_CLIENT` 解读占用信息；只显示当前用户有权查看的必要信息，不把原始 session 输出给用户。
- 释放失败或异常需要可见；不只记日志后返回成功。申请/业务/释放阶段发生异常，不代表业务未写或锁未建立；核本次数据、组、操作、占用者及业务结果后恢复，不能自动重跑业务或调用强制释放。

## 短时自定义逻辑示例

以下代码需在有效平台 `RequestContext` 中执行；标识来自已核实体和操作。它使用标准组和严格申请，保留业务主异常，并将同时发生的释放异常作为 suppressed exception。若 `action` 调用自身带网控的标准操作，先核其网控重入路径，不能直接叠加该示例。调用方需把异常转换为失败结果；`action` 不应持有页面对象跨线程，也不代表新增事务或回滚保证。

```java
import java.io.IOException;
import java.util.Objects;
import kd.bos.mutex.DataMutex;
import kd.bos.mutex.impl.MutexLockInfo;

public final class NetworkMutexExample {
    private NetworkMutexExample() { }

    // 在平台有效 RequestContext 中执行短时自定义逻辑。
    // 本示例固定使用标准互斥组；页面编辑锁应由其页面生命周期释放。
    public static void run(String billId, String billNumber, String entityNumber,
                           String operationKey, Runnable action) throws IOException {
        Objects.requireNonNull(action, "action");
        try (DataMutex mutex = DataMutex.create()) {
            MutexLockInfo info = new MutexLockInfo();
            info.setDataObjId(billId);
            info.setDataObjNumber(billNumber);
            info.setEntityNumber(entityNumber);
            info.setOperationKey(operationKey);
            info.setGroupId(DataMutex.DEFAULT_GROUPID);
            info.setStrict(true);
            info.setCallSource("custom_short_task");
            if (!mutex.require(info)) {
                throw new IllegalStateException("申请网控失败，请查询当前占用信息后重试");
            }
            Throwable primary = null;
            try {
                action.run();
            } catch (RuntimeException | Error failure) {
                primary = failure;
                throw failure;
            } finally {
                try {
                    // 顺序为数据ID、实体编码、操作标识；并非groupId。
                    if (!mutex.release(billId, entityNumber, operationKey)) {
                        throw new IllegalStateException("网控释放失败，请核查锁状态");
                    }
                } catch (RuntimeException | Error releaseFailure) {
                    if (primary != null) {
                        primary.addSuppressed(releaseFailure);
                    } else {
                        throw releaseFailure;
                    }
                }
            }
        }
    }
}
```

## 超时不能代替释放

不要写成“忘记释放后等 Session 超时即可”。两篇同标 V6.0.1 及以上的官方知识存在冲突：较新 FAQ 称编辑页默认 8 小时、不支持改时长；排查指南说明 `mutex.maxkeeptime_h`、MC 配置和每小时清理任务 `bos_ReleaseTimeoutMutex_SKDP_S`，默认阈值 8 小时可能到 9 小时才清理。实际本地 7.0 Redis/ZK 实现均读取该系统属性，默认 `8`，这只确认代码支持该值，不能证明现网配置、发布和调度已生效。

因此以目标补丁、实际生效参数与清理任务状态核实；不承诺固定 8/9 小时释放、不为排错擅自修改 MC 或发布集群。持锁期间避免长时间外部等待；退出编辑、正常完成和失败路径仍应按各自生命周期释放。

## 依据与验证边界

- [官方网络互斥开发](https://vip.kingdee.com/knowledge/596780097458402560)，更新 2026-07-30 03:17：批量参数、标准组与调用来源。
- [官方时长 FAQ](https://vip.kingdee.com/knowledge/882067358360539392)，更新 2026-08-31 01:00；[失效时间排查](https://vip.kingdee.com/knowledge/558387898114695168)，更新 2026-07-30 03:45：以上冲突需保留，不能凭更新时间自行裁定所有版本。
- [V7.0.1 DataMutex](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/mutex/DataMutex.html) 与本地 `bos-mutex-7.0.jar` 核实签名、参数及实现；Java 8 离线编译只证明示例兼容依赖，未执行网控争用、页面退出、批量部分成功或超时清理。
