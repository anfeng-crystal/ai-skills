# EDU-KAFKA-001 课程开设审批与发布需求

> 来源: `/Users/anfeng/Code/Study/edu-course-approval-compile/README.md`、`/Users/anfeng/Code/Study/edu-course-approval-compile/deliverables/dispatch/20260413/edu-course-approval-demand-package.md`
> 日期: 2026-04-13
> 标签: 教育, 课程审批, 工作流插件, 编译优先, Gradle
> 领域: 后端开发
> 行业: 教育

---

## 摘要
在 DockerHub 镜像拉取阻塞的前提下，将原本依赖 Kafka runtime 的课程审批需求转为“编译优先交付”路线，先完成可编译工程、表单/操作/工作流插件和交付文档，再保留后续集成扩展位。

## 业务目标
建设“课程开设申请 → 教研室审批 → 教务审批 → 课程发布”的最小闭环，覆盖：
1. 课程审批单字段定义；
2. 表单保存前校验；
3. 状态流转校验；
4. 工作流节点拦截；
5. 发布动作；
6. 编译级交付验证。

## 工程决策
### 1. 转线原因
- DockerHub / 镜像源无法稳定拉取运行时镜像；
- 用户优先要结果，而不是继续耗在容器层排障；
- 课程审批需求的当前阶段以插件编译落地为主，适合先走 Gradle 验收。

### 2. 转线路线
- 模板工程：`/Users/anfeng/Code/Study/education`
- 新工程：`/Users/anfeng/Code/Study/edu-course-approval-compile`
- 保留模块：`edu-base-common`、`edu-base-helper`、`edu-course-approval`、`edu-cosmic-debug`
- SDK 路径：`/Users/anfeng/utils/cosmic/home`
- 验收命令：`./gradlew clean build`

## 核心字段
| 字段标识 | 含义 | 规则 |
|---------|------|------|
| `edu_academic_year` | 学年 | 必填 |
| `edu_term` | 学期 | 必填 |
| `edu_course_code` | 课程编码 | 必填 |
| `edu_course_name` | 课程名称 | 必填 |
| `edu_teacher` | 任课教师 | 必填 |
| `edu_department` | 开课院系 | 必填 |
| `edu_credit` | 学分 | 必须 > 0 |
| `edu_total_hours` | 总学时 | 必须 ≥ 学分 × 8 |
| `edu_capacity` | 计划人数 | 必须在 10~300 |
| `edu_reason` | 开课说明 | 至少 20 字 |
| `edu_bill_status` | 单据状态 | A/B/C/D/E/F |
| `edu_publish_flag` | 发布标志 | 发布后为 true |

## 状态机
| 状态 | 含义 | 允许动作 |
|------|------|---------|
| A | 草稿 | 保存、提交 |
| B | 已提交 | 教研室审核、驳回 |
| C | 教研室已审 | 教务审核、驳回 |
| D | 教务已审 | 发布 |
| E | 已驳回 | 修改后重提 |
| F | 已发布 | 终态 |

## 关键技术要求
1. 表单插件使用 `AbstractBillPlugIn`；
2. 状态/发布动作使用 `AbstractOperationServicePlugIn`；
3. 工作流插件使用 `IWorkflowPlugin`；
4. 当前已验证的工作流兼容模式为：`validate(...) + beforeNodeApprove(...)` 双入口；
5. `beforeNodeApprove(...)` 默认不加 `@Override`，否则在当前工程会出现编译失败。

## 当前边界
- 当前工程只保留 Kafka 事件口径常量，不做容器级联调；
- 若后续需要 Kafka 联调，应单独开启集成波次，不回滚当前编译交付成果；
- 本文档对应的是“编译优先交付版”需求，不等价于完整运行时联调版需求。
