# IWorkflowPlugin兼容写法与编译验证

> 来源: `/Users/anfeng/Code/Study/edu-course-approval-compile/build.log`、`/Users/anfeng/Code/Study/edu-course-approval-compile/code/course/edu-course-approval/src/main/java/edu/course/approval/plugin/workflow/CourseApprovalWorkflowPlugin.java`
> 日期: 2026-04-13
> 标签: 插件开发, 工作流插件, IWorkflowPlugin, 编译验证
> 领域: 后端开发
> 行业: 通用

---

## 摘要
基于真实工程回归结果，`IWorkflowPlugin` 的默认推荐模板应从旧的单一事件写法，调整为 `validate(...) + beforeNodeApprove(...)` 双入口兼容写法，并把 `beforeNodeApprove(...)` 上的 `@Override` 视为风险项而不是默认项。

## 背景
在 `edu-course-approval-compile` 工程中，首次构建失败，报错信息明确指向：
- `beforeNodeApprove(DynamicObject bill, String nodeId, Map<String, Object> params)`
- 原因：`@Override` 与当前 SDK 接口定义不匹配

修复后重新执行 `./gradlew clean build`，构建成功。

## 推荐写法
```java
public class XxxWorkflowPlugin implements IWorkflowPlugin {

    public boolean validate(DynamicObject bill, Map<String, Object> params) {
        if (bill.getString("status") == null) {
            params.put("errorMessage", "状态不能为空");
            return false;
        }
        return true;
    }

    public boolean beforeNodeApprove(DynamicObject bill, String nodeId, Map<String, Object> params) {
        String nodeName = params.get("nodeName") == null ? "" : params.get("nodeName").toString();
        if ("初审".equals(nodeName)) {
            return validateStep1(bill, params);
        }
        if ("终审".equals(nodeName)) {
            return validateStep2(bill, params);
        }
        return true;
    }
}
```

## 编译验证要点
1. 修改工作流模板后，优先执行 `./gradlew clean build`；
2. 若报“方法不会覆盖或实现超类型的方法”，先检查是否误加 `@Override`；
3. 不要把某个行业工程里的工作流写法直接无脑复用到所有项目；
4. 若需要更高级的 `onNodeArrive` / `onNodeComplete` 等事件，必须先核对目标 SDK 文档或项目内已验证样例。

## 风险点与注意事项
- `params.put("errorMessage", msg)` + `return false` 是节点阻断的标准提示方式；
- `beforeNodeApprove(...)` 是否属于接口覆盖点，取决于目标 SDK，而不是单个旧样例；
- 兼容性模板的第一优先级是“能编译并可复用”，不是“功能写得炫”。
