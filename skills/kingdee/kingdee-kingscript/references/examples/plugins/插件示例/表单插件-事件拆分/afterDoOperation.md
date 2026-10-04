# afterDoOperation - 操作结果提示与后台下推

## 事件与事务边界

`afterDoOperation(e: AfterDoOperationEventArgs): void` 处于表单界面层。用户执行绑定操作后，成功或失败都可能进入，因此先将 `getOperationResult()` 保存为局部变量并判断非空及 `isSuccess()`，再按 `getOperateKey()` 分流。

[官方 afterDoOperation 说明](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=222756398046529280&type=Knowledge&productLineId=29&lang=zh-CN)明确此事件没有事务保护，不能在其中同步修改数据库。审核成功之后直接调用转换、保存下游单据会把界面回调与数据库写入混在一起。下例保留“审核后自动下推采购入库、提交成功提示”的业务能力，将实际转换保存放到独立后台任务。

## KingScript 界面事件最小示例

只需要提交结果提示时使用此段。它不实现自动下推；需要完整审核后下推时，改用下一段 Java 表单插件和配套 KingScript 任务，两个表单插件选择其一，不同时挂载。

```typescript
import { AbstractBillPlugIn } from "@cosmic/bos-core/kd/bos/bill";
import { AfterDoOperationEventArgs } from "@cosmic/bos-core/kd/bos/form/events";

/** 仅展示操作结果提示；审核后后台派发使用另列的 Java 表单替代实现。 */
class OperationResultFormPlugin extends AbstractBillPlugIn {
  /** 事件进入不代表操作成功；结果缺失或失败时不追加成功提示。 */
  afterDoOperation(e: AfterDoOperationEventArgs): void {
    super.afterDoOperation(e);
    const result = e.getOperationResult();
    if (result == null || !result.isSuccess()) return;
    if (e.getOperateKey() === "submit") {
      this.getView().showSuccessNotification("单据提交成功，请等待审核");
    }
  }
}
let plugin = new OperationResultFormPlugin();
export { plugin };
```

## 审核后派发任务的 Java 表单替代实现

所核 7.0 构件中，`JobInfo`、`JobFormInfo`、`JobForm` 有脚本声明，但 `PluginType` 没有对应模块导出；Java 类则有 `PluginType.KING_SCRIPT`。`new JobInfo()` 默认是 Java 类型，单独 `setKsScriptId` 不改变插件类型。不能用数字断言、虚构脚本导入或未知全局对象绕过。本段利用真实 Java API 完成派发，后台业务仍由 KingScript 实现；其他目标若有匹配的公开脚本导出，可重新核实后选择纯脚本实现。

填写目标环境已发布任务所属应用编码及真实 KingScript 脚本 ID。`export { plugin }` 中的变量名、Java 类名和脚本文件名都不能直接冒充该 ID。主键从审核成功的当前单据取；未配置或主键为空时不派发。

`JobForm.dispatch` 打开任务进度表单并携带任务信息。调用返回只表示这次界面调用返回，不表示调度受理、转换完成或目标已保存；后续任务状态需从实际任务结果查看。该入口覆盖当前页面操作，不能冒称覆盖没有页面的批量审核、接口或后台操作。

```java
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import kd.bos.bill.AbstractBillPlugIn;
import kd.bos.context.RequestContext;
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.dataentity.entity.LocaleString;
import kd.bos.entity.operate.result.OperationResult;
import kd.bos.form.events.AfterDoOperationEventArgs;
import kd.bos.schedule.api.JobInfo;
import kd.bos.schedule.api.JobType;
import kd.bos.schedule.api.PluginType;
import kd.bos.schedule.form.JobForm;
import kd.bos.schedule.form.JobFormInfo;

/** 审核成功后打开后台下推任务进度；与仅提示的 KingScript 表单示例二选一挂载。 */
public class PmPurorderAutoPushFormPlugin extends AbstractBillPlugIn {
    /** 界面回调只判定结果、提示或派发；不在此处同步下推保存。 */
    @Override
    public void afterDoOperation(AfterDoOperationEventArgs e) {
        super.afterDoOperation(e);
        OperationResult result = e.getOperationResult();
        if (result == null || !result.isSuccess()) {
            return;
        }
        String opKey = e.getOperateKey();
        if ("submit".equals(opKey)) {
            getView().showSuccessNotification("单据提交成功，请等待审核");
            return;
        }
        if (!"audit".equals(opKey)) {
            return;
        }
        DynamicObject entity = getModel().getDataEntity();
        Object billId = entity == null ? null : entity.getPkValue();
        String sourceBillId = billId == null ? "" : String.valueOf(billId).trim();
        if (sourceBillId.isEmpty() || "0".equals(sourceBillId)) {
            getView().showTipNotification("审核已完成，当前单据主键无效，未发起下推任务");
            return;
        }
        dispatchInboundTask(sourceBillId);
    }

    /** 只传源单主键；应用编码及脚本 ID 必须来自目标环境已发布的 KingScript 任务。 */
    private void dispatchInboundTask(String sourceBillId) {
        final String taskAppId = ""; // 填写任务所属应用编码。
        final String taskScriptId = ""; // 填写已发布后台任务的实际 KingScript 脚本 ID。
        if (taskAppId.trim().isEmpty() || taskScriptId.trim().isEmpty()) {
            getView().showTipNotification("审核已完成，自动下推任务尚未配置");
            return;
        }
        try {
            Map<String, Object> params = new HashMap<>();
            params.put("sourceBillId", sourceBillId);
            RequestContext context = RequestContext.get();
            JobInfo job = new JobInfo();
            job.setId(UUID.randomUUID().toString());
            job.setNumber("pm_purorder_auto_push");
            job.setlName(new LocaleString("采购订单审核后下推入库"));
            job.setAppId(taskAppId);
            job.setJobType(JobType.REALTIME);
            job.setPluginType(PluginType.KING_SCRIPT);
            job.setKsScriptId(taskScriptId);
            job.setRunByUserId(context.getCurrUserId());
            job.setRunByOrgId(context.getOrgId());
            job.setRunByLang(context.getLang());
            job.setRetryTime(0);
            job.setParams(params);
            JobForm.dispatch(new JobFormInfo(job), getView());
            // 返回仅表示本次进度页调用返回，不代表后台受理、下推或保存成功。
        } catch (Exception ex) {
            getView().showTipNotification("审核已完成，无法确认下推任务是否发起；请先核查后台任务和目标单据，避免重复发起");
        }
    }
}
```

## 独立 KingScript 后台任务

将下列代码作为后台任务发布，再把真实脚本 ID 配到上面的派发插件。`sourceBillId` 经任务参数传递为字符串，避免将大整数主键先转为 JavaScript number。源 `pm_purorder`、目标 `im_purinbill` 和真实规则 ID 必须一致；下例留空规则 ID，并在未配置时明确失败，避免随意使用默认规则。

真实接口是 `new PushArgs(sourceEntity, targetEntity, ListSelectedRow列表)` 和 `setRuleId`，不是空构造器后 `setSourceFormId/setTargetFormId/setBillIds/setConvertRuleKey`。`ConvertServiceHelper` 位于 `servicehelper/botp`。这里使用 `pushAndSave` 执行转换并保存，避免把只构造目标数据包的 `push` 当成已入库，也不使用不存在的 `getTargetDataEntities`。

```typescript
import { AbstractTask } from "@cosmic/bos-core/kd/bos/schedule/executor";
import { RequestContext } from "@cosmic/bos-core/kd/bos/context";
import { ListSelectedRow } from "@cosmic/bos-core/kd/bos/entity/datamodel";
import { PushArgs, SourceBillReport } from "@cosmic/bos-core/kd/bos/entity/botp/runtime";
import { ConvertServiceHelper } from "@cosmic/bos-core/kd/bos/servicehelper/botp";
import { LogFactory } from "@cosmic/bos-core/kd/sdk/bos/logging";
import { ArrayList, Map } from "@cosmic/bos-script/java/util";

/** 后台下推任务；源/目标实体及规则需按实际元数据配置，任务失败后先核查已保存目标。 */
class PmPurorderAutoPushTask extends AbstractTask {
  /** 不请求服务重启后的自动重新调度；此设置不能保证业务幂等。 */
  isSupportReSchedule(): boolean { return false; }

  /** 只处理传入的一张源单；引擎可能拆出多张目标，pushAndSave 负责保存，结果单独判断。 */
  execute(context: RequestContext, params: Map): void {
    const rawId = params == null ? null : params.get("sourceBillId");
    const sourceBillId = rawId == null ? "" : String(rawId).trim();
    const ruleId = ""; // 填写实际已启用并核对源/目标实体、数量控制及保存配置的转换规则 ID。
    if (sourceBillId === "" || sourceBillId === "0" || ruleId.trim() === "") {
      throw new Error("源单主键无效或转换规则 ID 为空，未执行下推");
    }
    const rows = new ArrayList();
    rows.add(new ListSelectedRow(sourceBillId));
    const args = new PushArgs("pm_purorder", "im_purinbill", rows);
    args.setRuleId(ruleId);
    args.setHasRight(false); // 交由引擎核验下游新建权限，不声明调用方已验权。
    args.setAutoSave(true);
    args.setBuildConvReport(true);
    let result;
    try {
      result = ConvertServiceHelper.pushAndSave(args);
    } catch (error) {
      try {
        LogFactory.getLog("PmPurorderAutoPushTask").error("源单 " + sourceBillId + " 下推执行异常，目标保存结果待核查；请勿直接重试", error);
      } catch (_) {
        // 日志失败不覆盖原始异常。
      }
      throw error;
    }
    if (result == null) {
      throw new Error("源单 " + sourceBillId + " 下推未返回结果，目标保存结果待核查；请勿直接重试");
    }
    const ids = result.getTargetBillIds();
    const targetIds: string[] = [];
    if (ids != null) {
      const iterator = ids.iterator();
      while (iterator.hasNext()) targetIds.push(String(iterator.next()));
    }
    const relation = "pm_purorder:" + sourceBillId + " -> im_purinbill:[" + targetIds.join(",") + "]";
    const reports = result.getBillReports();
    let reportCount = 0;
    let fullSuccess = true;
    if (reports != null) {
      const reportIterator = reports.iterator();
      while (reportIterator.hasNext()) {
        const report = reportIterator.next() as SourceBillReport;
        reportCount++;
        if (report == null || String(report.getBillId()) !== sourceBillId || !report.isFullSuccess()) {
          fullSuccess = false;
        }
      }
    }
    if (!result.isSuccess() || !fullSuccess) {
      throw new Error("下推未全部成功；结果返回已保存目标 " + targetIds.length + " 张；" + relation + "。请核查转换报告及目标单据后处理，勿直接重试");
    }
    if (reportCount === 0) {
      throw new Error("下推未返回源单转换报告；结果返回已保存目标 " + targetIds.length + " 张；" + relation + "。完整结果待核查，勿直接重试");
    }
    if (targetIds.length === 0) {
      throw new Error("下推结果未返回已保存目标；" + relation + "。请核查转换报告及目标单据");
    }
    // 任务正常结束才代表此脚本判定成功；保存结果和源/目标对应关系记录到任务服务日志。
    try {
      LogFactory.getLog("PmPurorderAutoPushTask").info("已生成并保存采购入库单 " + targetIds.length + " 张；" + relation);
    } catch (_) {
      // 目标已保存，记录日志失败不应触发重新下推。
    }
  }
}
let plugin = new PmPurorderAutoPushTask();
export { plugin };
```

## 结果、权限与重试

- `pushAndSave` 可能按批处理并产生多张目标。结果失败或异常不代表所有目标都未保存；有目标 ID 也不自动代表整批成功。所核引擎存在“有目标 ID 即设成功标志”的路径，因此任务请求转换报告，除结果与目标 ID 外，还逐份检查 `SourceBillReport.isFullSuccess()`；报告缺失也不直接称全部成功。失败后先核查转换报告与已有目标，不盲目重试。
- `setHasRight(false)` 不声明调用方已经完成下游新建权限检查，仍走引擎对应权限检查路径；它不等于完整业务授权或源数据权限保证。
- 审核与后台任务不是同一个事务。源单可能在排队期间反审核或改变；转换规则/保存校验必须按真实元数据核查当前源状态、组织权限和剩余可下推量，不按猜测字段名检查。
- 重复审核、重复事件、并发发起及部分成功恢复必须由实际业务的持久幂等或数量控制约束。随机任务 ID 只用于任务实例标识，不是业务幂等键；本例未加入假定的数据库字段或页面缓存去重。
- 不主动重试下推；任务重调度设置不能替代业务幂等，也不能证明所有运行环境都不会重投。完整任务中保存异常保留原始原因，成功后的日志失败不重新下推。
- 此路线依赖真实任务注册、进度页派发、脚本加载、转换规则与权限、保存和恢复验收。Java/TypeScript 编译及本地 stub 只能分别证明类型与局部逻辑，不能当作平台已运行或部署完成。
