package kd.cd.common;

import kd.bos.context.RequestContext;
import kd.bos.dataentity.resource.ResManager;
import kd.bos.exception.KDException;
import kd.bos.schedule.executor.AbstractTask;

import java.util.HashMap;
import java.util.Map;

/**
 * 后台任务骨架模板（原生 AbstractTask）。
 * 该类仅用于示例写法，生成后请按实际业务删除无用逻辑并替换占位常量。
 */
public class TaskTemplate extends AbstractTask {
    private static final String RES_APP_ID = "kd-cd-common-template";

    /**
     * 触发时机: 在需要了解当前插件可访问上下文能力时调用。
     * 参数要点: 无入参；仅展示当前插件可通过 this. 访问的方法能力。
     * 典型用途: 作为模板提示，指导在各事件内选择正确的上下文 API。
     */
    private void getContextSample() {
        // this.taskId; // 7.0 中为受保护字段，由调度框架注入。
        // this.checkIsStop();
        // this.isStop();
        // this.feedbackProgress(10);
        // this.feedbackProgress(30, "处理中", null);
        // this.feedbackCustomdata(new java.util.HashMap<>());
        // this.getMessageHandler();
        // this.setTaskId("task-id");
        // this.isSupportReSchedule();
    }

    // ===== 核心事件 =====

    /**
     * 触发时机: 调度中心触发任务执行时。
     * 参数要点:
     * - context: 请求上下文，包含用户、组织、租户等信息。
     * - params: 调度参数 map，通常承载任务业务入参。
     * 典型用途: 编排任务主流程、分阶段回传进度、按需检查中止标记。
     */
    @Override
    public void execute(RequestContext context, Map<String, Object> params) throws KDException {
        // AbstractTask 未实现 execute；任务入口不调用抽象的 super.execute。
        this.checkIsStop();
        this.feedbackProgress(0, ResManager.loadKDString("任务开始", "TaskTemplate_0", RES_APP_ID), null);

        Object taskParam = params == null ? null : params.get("taskParam");
        doStep(taskParam);

        this.checkIsStop();

        Map<String, Object> customData = new HashMap<>();
        customData.put("result", "ok");
        customData.put("taskParam", taskParam);
        this.feedbackProgress(100, ResManager.loadKDString("任务完成", "TaskTemplate_1", RES_APP_ID), customData);
    }

    // 沿用父类 stop() 的终止异常；业务资源在 execute 的 finally 或 try-with-resources 中释放。

    private void doStep(Object taskParam) {
        if (taskParam == null) {
            this.feedbackProgress(30, ResManager.loadKDString("未传入 taskParam，按默认逻辑执行", "TaskTemplate_3", RES_APP_ID), null);
            return;
        }
        Map<String, Object> customData = new HashMap<>();
        customData.put("taskParam", taskParam);
        this.feedbackProgress(60, ResManager.loadKDString("正在处理 taskParam", "TaskTemplate_4", RES_APP_ID), customData);
    }
}
