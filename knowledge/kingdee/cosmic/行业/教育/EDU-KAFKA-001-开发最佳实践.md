# EDU-KAFKA-001 开发最佳实践

> 来源: `/Users/anfeng/Code/Study/edu-course-approval-compile/README.md`、`/Users/anfeng/Code/Study/edu-course-approval-compile/build.log`、`/Users/anfeng/Code/Study/edu-course-approval-compile/code/course/edu-course-approval/plugin/`
> 日期: 2026-04-13
> 标签: 教育, 最佳实践, IWorkflowPlugin, 编译优先, 工程转线
> 领域: 后端开发
> 行业: 教育

---

## 摘要
本案例沉淀两条真实有效的经验：
1. `IWorkflowPlugin` 采用 `validate(...) + beforeNodeApprove(...)` 双入口兼容写法；
2. DockerHub 阻塞时，停止空耗，切换到“复制模板 → 裁剪模块 → `./gradlew clean build`”的编译优先路线。

## 实践一：IWorkflowPlugin 双入口兼容写法
### 推荐模板
```java
public class XxxWorkflowPlugin implements IWorkflowPlugin {

    public boolean validate(DynamicObject bill, Map<String, Object> params) {
        String status = bill.getString("status");
        if (status == null || status.trim().isEmpty()) {
            params.put("errorMessage", "状态字段不能为空");
            return false;
        }
        return true;
    }

    public boolean beforeNodeApprove(DynamicObject bill, String nodeId, Map<String, Object> params) {
        String nodeName = params.get("nodeName") == null ? "" : params.get("nodeName").toString();
        if ("教研室审核".equals(nodeName)) {
            return validateDepartmentApprove(bill, params);
        }
        if ("教务审核".equals(nodeName)) {
            return validateAcademicApprove(bill, params);
        }
        return true;
    }
}
```

### 核心结论
- `validate(...)`：负责保存/提交前的数据合法性校验；
- `beforeNodeApprove(...)`：负责节点级拦截与 `nodeName` 分派；
- `params.put("errorMessage", msg)` + `return false` 是标准阻断写法；
- **默认不要给 `beforeNodeApprove(...)` 加 `@Override`**，除非目标 SDK 文档明确声明。

### 反例
```java
@Override
public boolean beforeNodeApprove(DynamicObject bill, String nodeId, Map<String, Object> params) {
    ...
}
```
在本次真实工程中，上述写法直接触发编译失败。

## 实践二：DockerHub 阻塞时的编译优先转线
### 触发条件
- DockerHub / 镜像源拉取失败；
- 用户优先要交付，而不是继续等待容器恢复；
- 当前功能以插件编译交付为主，不依赖即时 MQ 联调。

### 推荐步骤
1. 复制已验证模板工程；
2. 裁剪无关模块，仅保留公共层、目标业务模块和 debug 模块；
3. 修正 `settings.gradle`、`gradle.properties`、模块依赖；
4. 保持 `cosmic_home=/Users/anfeng/utils/cosmic/home`；
5. 用 `./gradlew clean build` 做首轮验收；
6. 编译通过后再补需求、元数据、测试和迭代文档。

### 适用边界
- 适合：表单插件、操作插件、工作流插件、公共常量/Helper；
- 不适合：需要真实 MQ、缓存、WebAPI 网关联调的场景。

## 实践三：闭环不止代码
本次交付证明，真正的闭环应包含：
1. 工程创建与代码落地；
2. 编译回归；
3. Skills 版本升级；
4. 知识库归档。

只完成第 1 步和第 2 步，不算完整沉淀。
