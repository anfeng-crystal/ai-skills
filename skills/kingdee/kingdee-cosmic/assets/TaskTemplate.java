package kd.cd.common;

import kd.bos.context.RequestContext;
import kd.bos.dataentity.resource.ResManager;
import kd.bos.exception.KDException;
import kd.bos.schedule.executor.AbstractTask;

import java.util.Map;

/**
 * 后台任务骨架模板（原生 AbstractTask）。
 * 无额外业务参数的最小骨架；生成后实现已确认的业务并替换资源标识。
 */
public class TaskTemplate extends AbstractTask {
    private static final String RES_APP_ID = "kd-cd-common-template";

    /**
     * 触发时机: 调度中心触发任务执行时。
     * 参数要点:
     * - context: 请求上下文，包含用户、组织、租户等信息。
     * - params: 框架传入的调度参数；仅按已确认的业务键与类型读取，无业务参数时无需使用。
     * 典型用途: 编排任务主流程、分阶段回传进度、按需检查中止标记。
     */
    @Override
    public void execute(RequestContext context, Map<String, Object> params) throws KDException {
        // AbstractTask 未实现 execute；任务入口不调用抽象的 super.execute。
        this.checkIsStop();
        this.feedbackProgress(0, ResManager.loadKDString("任务开始", "TaskTemplate_0", RES_APP_ID), null);

        // 在此实现已确认的任务业务；批次或耗时步骤边界按需检查停止。

        this.checkIsStop();

        this.feedbackProgress(100, ResManager.loadKDString("任务完成", "TaskTemplate_1", RES_APP_ID), null);
    }

    // 沿用父类 stop() 的终止异常；业务资源在 execute 的 finally 或 try-with-resources 中释放。
}
