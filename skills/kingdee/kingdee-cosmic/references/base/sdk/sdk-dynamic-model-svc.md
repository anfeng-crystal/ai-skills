# 动态领域模型 - 公共服务索引

## 按业务选择入口

本卡索引数据存取、业务操作、编号、基础资料、参数、时间和微服务分发。Helper 是调用入口，不等于统一具备权限校验、事务、插件或跨节点时间保证；按具体方法合同核验，不能凭类名猜重载。

|场景|入口与边界|
|---|---|
|加载/查询|`BusinessDataServiceHelper`、`QueryServiceHelper`；区分对象加载、投影、DataSet和数据范围|
|持久化|`SaveServiceHelper` / `DeleteServiceHelper`；底层持久化不能替代业务操作链|
|审核/提交等|`OperationServiceHelper`，按已配置操作及结果处理；见 [操作插件](../plugin/plugin-operation.md)|
|单据编码|`kd.bos.servicehelper.coderule.CodeRuleServiceHelper`；区别预读、消耗编号、注入对象|
|基础资料|`kd.bos.servicehelper.basedata.BaseDataServiceHelper`；分配和组织使用范围按管控配置|
|参数|`kd.bos.servicehelper.parameter.SystemParamServiceHelper`；区分公共/应用参数|
|时间|`kd.bos.servicehelper.TimeServiceHelper`；不承诺集群严格一致|
|微服务|`kd.bos.servicehelper.DispatchServiceHelper`；先核实际发布服务与方法合同|

以下签名已对照 V7.0.1 Javadoc 和实际 7.0 依赖；`kd.bos.servicehelper.CodeRuleServiceHelper` 根包类在该依赖中继承 coderule 包类，示例使用后者。

## 编号：预读、取号与注入

|目的|真实方法|结果|
|---|---|---|
|预读|`readNumber(String entityId, DynamicObject dataInfo, String orgId)`|`String`，不占用流水号；官方说明不支持“不允许断号”模式|
|单笔取号|`getNumber(String entityId, DynamicObject dataInfo, String orgId)`|`String`，消耗流水号/断号；无 `(String, DynamicObject)` 重载|
|同条件批量|`getBatchNumber(String entityId, DynamicObject dataInfo, String orgId, int count)`|`String[]`；没有 `getBatchCodes(String,int)`|
|逐对象批量|`getNumbers(String entityId, List<DynamicObject> dataInfos)`|`List<String>` 与输入顺序对齐，未匹配项仍占位 `null`|
|注入对象|`injectNumbers(String entityId, List<DynamicObject> dataInfos)`|`void`，填入对象编号；不等于保存|

第三个 String 是**受控组织 ID**，不是编码规则编号。对象需具备规则所需字段；组织为空的回退按规则/主业务组织/当前上下文合同核验，不能随意硬编码组织。需要指定规则对象时另有 `getNumber(CodeRuleInfo, DynamicObject)`。

取号与保存分开：`getNumber` 返回编号，不自动把返回值写入 `billno`；按已核编号属性赋值。已有平台保存自动编号时保留原链路，不在打开页面、重试或每次保存前重复主动取号。预读编号不能当已占用编号；批量结果不能先过滤 null 再按位置回填，也不保证号码连续。取号后异常/取消不等于自动归还编号；回收需按实际规则和单据状态确认，不能盲目补偿或调整最大号表。

## 公共参数与应用参数

- `Object loadPublicParameterFromCache(String key)`：公共参数。
- `Object loadAppParameterFromCache(AppParam appParam, String key)`；另有只传 AppParam 返回 `Map<String,Object>` 的重载。
- `kd.bos.entity.param.AppParam` 可由 `new AppParam(String appId, Long orgId)` 构造；参数类型或多维隔离需用该参数定义要求的构造/属性，不能只凭 key 猜应用、组织、账簿或类型。
- 本地 7.0 无 `getValue(String)` / `getValue(String,long)`。缓存入口返回 `Object`，保留未配置的 null 与真实类型，不把 null、false、0、空串混为一类。平台已有缓存，只有明确失效/隔离合同才再加业务缓存。

下面示例接收已初始化的业务对象/上下文参数；只展示 API，不保存单据、不运行编号服务。是否调用消耗编号的入口由业务保存流程决定。

```java
import java.util.Date;
import java.util.List;
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.entity.param.AppParam;
import kd.bos.servicehelper.coderule.CodeRuleServiceHelper;
import kd.bos.servicehelper.parameter.SystemParamServiceHelper;
import kd.bos.servicehelper.TimeServiceHelper;

public final class CodeAndParameterExample {
    public String preview(String entityId, DynamicObject bill, String orgId) {
        return CodeRuleServiceHelper.readNumber(entityId, bill, orgId);
    }

    public String allocate(String entityId, DynamicObject bill, String orgId) {
        return CodeRuleServiceHelper.getNumber(entityId, bill, orgId);
    }

    public String[] allocateBatch(String entityId, DynamicObject basis,
                                  String orgId, int count) {
        return CodeRuleServiceHelper.getBatchNumber(entityId, basis, orgId, count);
    }

    public List<String> allocateEach(String entityId, List<DynamicObject> bills) {
        return CodeRuleServiceHelper.getNumbers(entityId, bills);
    }

    public Object publicParameter(String key) {
        return SystemParamServiceHelper.loadPublicParameterFromCache(key);
    }

    public Object applicationParameter(String appId, Long orgId, String key) {
        return SystemParamServiceHelper.loadAppParameterFromCache(
                new AppParam(appId, orgId), key);
    }

    public Date now() {
        return TimeServiceHelper.now();
    }
}
```

## 基础资料、删除与时间

- 分配的真实入口之一是 `BaseDataResponse assign(String entityId, Long assignOrgId, String appId, Set<Long> dataIds, Set<Long> orgIds)`；调用前确认分配主体组织、应用、数据与目标组织，检查响应及逐项失败。无三参 `(String,long[],long[])` 重载；另有基于 List 的 `batchAssign` 等方法，按所需返回合同选用。
- 缓存查询是 `Map<Object,DynamicObject> queryBaseDataFromCache(String entityId, Long orgId, QFilter filter, String selectFields)`。组织非空且非 0 并处于受控策略时按合同追加组织使用范围；这不证明满足当前用户全部数据/字段权限。补值、过滤、分配是不同能力，不互相替代。
- 低层 `DeleteServiceHelper.delete(String entityName, QFilter[] filters)` 返回 `int`；另有 `(IDataEntityType,Object[])` 返回 `void`，没有 `(String,Object[])` 重载。低层删除与业务删除操作不同，不能靠替换参数就声称执行了操作插件/校验。
- `new DeleteServiceHelper().deleteOperate(String entityName, Object[] pkids, OperateOption option)` 返回 `OperationResult`，是**实例方法**；另有不带 option 及带 operationKey 的重载。是否成功以操作结果、失败明细和实际业务状态判断，不能以未抛异常替代。
- 时间方法为 `Date TimeServiceHelper.now()` 和 `long getTimeStamp()`，没有 `getSystemDate()`。本地 7.0 的 now 最终调用 `new Date()`；单靠 Helper 不保证集群各节点严格同一时刻，跨节点时钟、业务时区与日期口径需另行确认。

## 微服务分发与工厂

真实静态泛型入口：`<T> T invokeBizService(String cloudName, String appName, String serviceName, String methodName, Object... args)` 与 `invokeService(String factoryQualifiedPrefix, String appName, String serviceName, String methodName, Object... args)`。`invokeService` 第一参是工厂类限定前缀，例如 `isv.ti.bo` 对应 `isv.ti.bo.ServiceFactory`，不是完整工厂类名。服务名、参数顺序、返回类型、授权和远程副作用须有发布合同；调用异常或超时不等于远端未执行，不能仅改为异步后盲重试。

```java
import kd.bos.servicehelper.DispatchServiceHelper;

public final class DispatchExample {
    public Object invoke(String cloud, String app, String service,
                         String method, Object[] args) {
        // 四个标识和参数由已确认的目标服务合同提供。
        return DispatchServiceHelper.invokeBizService(cloud, app, service, method, args);
    }
}
```

自定义工厂模式仍可使用真实 `kd.bos.dataentity.TypesContainer.getOrRegisterSingletonInstance(String)`；下面仅是业务包约定，类须确实存在。生产工厂的 serviceName 应来自受控注册/映射，不能让外部请求任意选择待实例化类。此示例本身不完成微服务注册或授权。

```java
import kd.bos.dataentity.TypesContainer;

public class ServiceFactory {
    public static Object getService(String serviceName) {
        String impl = "com.isv.mservice.impl." + serviceName + "Impl";
        return TypesContainer.getOrRegisterSingletonInstance(impl);
    }
}
```

## 来源与验证边界

[官方编码规则接口介绍](https://vip.kingdee.com/knowledge/522375605967170048)（更新 2023-12-12 14:51）明确预读/消耗编号、orgId 和批量空值占位；较早文章须结合目标版本。精确 API 另核 [V7.0.1 CodeRuleServiceHelper](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/servicehelper/coderule/CodeRuleServiceHelper.html)、[SystemParamServiceHelper](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/servicehelper/parameter/SystemParamServiceHelper.html) 和本地 7.0 对应类。

分配、参数维度、删除、分发和时间分别参见 V7.0.1 [BaseDataServiceHelper](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/servicehelper/basedata/BaseDataServiceHelper.html)、[AppParam](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/entity/param/AppParam.html)、[DeleteServiceHelper](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/servicehelper/operation/DeleteServiceHelper.html)、[DispatchServiceHelper](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/servicehelper/DispatchServiceHelper.html)、[TimeServiceHelper](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/servicehelper/TimeServiceHelper.html)。

上述代码仅完成 Java 8 / 实际依赖的离线编译。未执行取号、参数缓存读取、资料分配、删除、远程服务或保存；签名正确不替代规则配置、权限、事务及真实业务验收。
