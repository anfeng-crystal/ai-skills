# EDU-KAFKA-001 测试验收报告

> 来源: `/Users/anfeng/Code/Study/edu-course-approval-compile/build.log`、`/Users/anfeng/Code/Study/edu-course-approval-compile/deliverables/dispatch/20260413/edu-course-approval-test-report.md`
> 日期: 2026-04-13
> 标签: 教育, 测试验收, Gradle, IWorkflowPlugin
> 领域: 后端开发
> 行业: 教育

---

## 摘要
本轮按“新工程编译交付”口径完成验证：环境探针成功，`./gradlew clean build` 最终通过，并识别出一个真实兼容性问题——`beforeNodeApprove(...)` 直接加 `@Override` 会导致编译失败。

## 测试环境
- 操作系统：macOS
- 工程路径：`/Users/anfeng/Code/Study/edu-course-approval-compile`
- Java：21.0.10（构建脚本 source/target 仍为 1.8）
- Gradle：8.14.4
- SDK 根路径：`/Users/anfeng/utils/cosmic/home`

## 执行项
### 1. 环境探针
- 执行：`./gradlew -v`
- 结果：通过

### 2. 首轮全量编译
- 执行：`./gradlew clean build`
- 结果：失败
- 失败点：`CourseApprovalWorkflowPlugin` 中 `beforeNodeApprove(...)` 标记了 `@Override`
- 典型报错：`方法不会覆盖或实现超类型的方法`

### 3. 修复后回归编译
- 修复动作：
  1. 移除 `beforeNodeApprove(...)` 上的 `@Override`；
  2. 保留 `validate(...) + beforeNodeApprove(...)` 双入口兼容实现；
  3. 重新执行全量构建。
- 结果：`BUILD SUCCESSFUL`

## 验收结论
| 项目 | 结果 |
|------|------|
| 新工程已创建 | 通过 |
| 根工程可解析 `edu-course-approval` 模块 | 通过 |
| 公共类与插件代码可编译 | 通过 |
| 全量 `clean build` | 通过 |
| 兼容性问题已沉淀为知识 | 通过 |

## 核心发现
1. `IWorkflowPlugin` 的默认模板不能盲目给 `beforeNodeApprove(...)` 加 `@Override`；
2. 当前项目中，`validate(...)` 与 `beforeNodeApprove(...)` 的双入口写法能够稳定通过编译；
3. 当容器拉取被阻塞时，先保住 Gradle 编译链路，是更高收益的交付策略。

## 风险说明
- Java 21 下仍会出现 `source/target 8 已过时` 警告，但不影响本轮构建成功；
- 本验收报告不覆盖 Kafka runtime、Redis、消息消费等联调验证。
