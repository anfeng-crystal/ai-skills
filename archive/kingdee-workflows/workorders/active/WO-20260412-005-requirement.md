# 工单 WO-20260412-005-requirement

## 基本信息
- **工单ID**: WO-20260412-005-requirement
- **需求主题**: healthcare 行业需求接入包
- **派发对象**: requirement
- **创建时间**: 2026-04-12 11:16 UTC
- **状态**: 已完成

## 任务目标
将首轮通用需求接入基线转化为 healthcare 工程可直接复用的《行业需求接入包》，明确行业上下文、现有工程模块映射、待业务方补齐的信息，以及允许进入 metadata/frontend/backend/testing 的闸门条件。

## 验收标准
1. 输出必须包含医疗行业上下文、现有模块映射、建议优先业务入口和需求收集模板。
2. 必须明确哪些信息补齐后可以进入 metadata/frontend/backend/testing。
3. 结果必须落地到 `/Users/anfeng/Code/Study/healthcare/deliverables/dispatch/20260412/`。

## 交付物清单
- [x] `healthcare-requirement-intake-pack.md`
- [x] healthcare 需求缺口摘要（已并入 intake pack）

## 关联信息
- **工程路径**: /Users/anfeng/Code/Study/healthcare
- **元数据地址**: /Users/anfeng/Code/Study/healthcare/datamodel
- **需求文档**: /Users/anfeng/Code/Study/test/deliverables/dispatch/20260412/requirement-intake-baseline.md
- **前置工单**: WO-20260412-001-requirement

## 核心规则
- 不得臆造具体医院业务需求；只能做行业化接入包和模块映射。
- 必须结合 healthcare 现有模块结构，不得脱离真实工程空谈。
- 结论必须能被主代理直接用于下一轮派单闸门判断。

## 执行记录
### 2026-04-12 11:16 UTC - 主代理派单
healthcare 已被主代理选为下一轮绑定工程，要求输出行业化需求接入包。

### 2026-04-12 11:43 UTC - requirement 分代理完成接入评审
- 已读取通用接入基线、healthcare 工程 README、工程绑定报告、当前工单、主调度状态。
- 已按 `settings.gradle`、README 与现有源码目录完成医疗行业上下文和工程模块映射。
- 已确认当前最适合承接的真实入口为 `med-outpatient-register` 对应的门诊挂号登记场景。
- 已明确：当前只能形成**行业级接入包**，尚不能形成具体医院业务需求包。
- 已输出交付文件：`/Users/anfeng/Code/Study/healthcare/deliverables/dispatch/20260412/healthcare-requirement-intake-pack.md`

### 2026-04-12 12:33 UTC - requirement 分代理执行逆向补全需求包
- 已按主代理追加要求，直接读取 `med-outpatient-register`、`med-base-common`、`med-base-helper` 源码，基于代码事实逆向补全门诊挂号需求。
- 已提炼挂号单业务对象、字段、引用关系、状态口径、主流程、退号边界、关键校验与异常分支，并标记无法从源码确认的“待确认假设”。
- 已执行工程验证命令 `gradle --no-daemon :med-outpatient-register:build`，确认当前构建失败，阻塞点位于 `med-base-helper/RegisterSourceHelper.java` 的 BOS 查询相关依赖解析。
- 已新增交付文件：`/Users/anfeng/Code/Study/healthcare/deliverables/dispatch/20260412/healthcare-outpatient-demand-package.md`

## 交付结果
- **完成时间**: 2026-04-12 11:43 UTC
- **交付摘要**: 已将通用需求接入基线转为 healthcare 行业接入包，补充了医疗行业上下文、现有工程模块映射、优先业务入口建议、业务方待补齐信息清单、metadata/frontend/backend/testing 放行条件，并明确当前结论仅为行业级接入包，暂不允许进入开发派单。
- **质量评分**: 8.8/10
- **本次补充结果**:
  - **补充完成时间**: 2026-04-12 12:33 UTC
  - 已形成“基于现有代码事实反推”的门诊挂号具体需求包，而非泛化行业说明。
  - 当前结论调整为：
    - `metadata`：**可以进入下一轮最小建模工单**
    - `backend`：**暂不进入**（构建失败 + 状态/支付闭环未完整确认）
    - `testing`：**暂不进入**（尚不可稳定编译执行）
