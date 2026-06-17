# KingScript-V7建设行业财务HR复杂脚本案例

> 来源: 建设行业、财务、HR 复杂需求拆解，金蝶云社区官方 V7 KingScript 文章，本项目 V7 `.ts` 示例; 已按知识库规范清洗掉页面导航、登录提示、推荐阅读和无关分享信息。
> 日期: 2026-04-13
> 标签: KingScript, 建设行业, 财务风控, HR合规, V7脚本, 报表取数

---

## 摘要

本文保留 12 个复杂业务需求，但将脚本写法统一修正为 V7 KingScript 官方风格：`@cosmic` 模块导入、插件类继承、导出插件实例，并补充代码红线和报表取数边界。

## 适用版本

- 金蝶云苍穹 V7 KingScript。
- 项目型建设企业的表单、列表、操作、工作流、工具脚本。
- 示例字段、实体、服务类、审批节点均需按目标租户元数据替换。

## 代码红线

- 不写 `require("kd.bos...")`、`new java.*`、本机绝对路径、未开放内部类。
- 不在脚本中拼 SQL，不绕过权限、组织隔离和多库边界。
- 不把旧 KDE 对象式插件作为 V7 主示例。
- 不把复杂统计都塞进工作流节点，工作流只读写变量和控制路由。

## 详细内容

### 案例 1: 项目产值确认、合同履约与收入偏差联动

| 项目 | 内容 |
|---|---|
| 业务目标 | 月度产值填报后联动合同、履约进度、收入确认和回款，识别产值超合同、收入确认超前、回款滞后 |
| 数据输入 | 项目、合同、月度产值单、结算单、收入确认单、回款计划 |
| KingScript API 使用点 | `AbstractBillPlugIn.afterBindData`, `propertyChanged`, `beforeDoOperation`, `itemClick`, `BigDecimal` from `@cosmic/bos-script/java/math` |
| 报表输出字段 | 项目编码、期间、合同金额、累计产值、累计收入、偏差金额、偏差率、风险等级 |
| 异常边界 | 多合同、红冲产值、合同金额为 0、暂停项目、已生成凭证反审核 |
| 验收标准 | 提交前拦截超合同/超履约收入，审核后能生成风险提示 |
| 可转译示例 | `form/ks_project_revenue_form_plugin.ts` |
| 取数建议 | 当前单据用模型取数，合同/收入累计由 Java 服务按项目+合同+期间批量聚合 |

### 案例 2: 工程进度计划、现场日报与资源投入偏差预警

| 项目 | 内容 |
|---|---|
| 业务目标 | 联动 WBS、现场日报、劳务人数、机械台班、材料消耗和产值，识别滞后、缺报、资源低效 |
| 数据输入 | WBS 计划、现场日报、资源投入、产值、天气停工、关键节点参数 |
| KingScript API 使用点 | `AbstractBillPlugIn.afterCreateNewData`, `propertyChanged`; 工具脚本分片扫描 |
| 报表输出字段 | WBS、计划完成率、实际完成率、滞后天数、资源效率、风险等级 |
| 异常边界 | WBS 调整、停工免责、补录日报、多班组重复工程量、单位不一致 |
| 验收标准 | 日报提交识别重复填报和无计划任务，工具脚本输出项目/日期/任务/原因 |
| 可转译示例 | `tool/ks_batch_project_risk_scan.ts` |
| 取数建议 | WBS 树汇总由计划服务完成，脚本接收聚合结果并写风险标签 |

### 案例 3: 合同变更、签证、索赔与结算风险闭环

| 项目 | 内容 |
|---|---|
| 业务目标 | 建立变更、签证、索赔、结算到合同金额调整的闭环校验 |
| 数据输入 | 合同台账、变更申请、签证单、索赔单、结算单、附件资料 |
| KingScript API 使用点 | `AbstractOperationServicePlugIn.onAddValidators`, `afterExecuteOperationTransaction`, `WorkflowPlugin.afterNodeLeave` |
| 报表输出字段 | 合同编号、变更金额、签证金额、索赔金额、结算差异、闭环状态 |
| 异常边界 | 一签多合同、索赔金额未定、附件未同步、合同终止、变更撤销 |
| 验收标准 | 能识别缺附件、超期索赔、未转合同、未结算、结算差异五类异常 |
| 可转译示例 | `operate/ks_month_close_operation_plugin.ts` |
| 取数建议 | 关联单据按合同维度批量读取并缓存，单条异常进入结果集不阻断整批 |

### 案例 4: 项目重大风险分级、整改任务与责任追踪

| 项目 | 内容 |
|---|---|
| 业务目标 | 对安全、质量、工期、成本、合同、资金风险自动分级、派发、逾期升级和闭环验证 |
| 数据输入 | 风险登记、整改任务、现场检查单、项目岗位、进度/成本/合同影响数据 |
| KingScript API 使用点 | `propertyChanged`, `beforeDoOperation`, `WorkflowPlugin.beforeNodeEnter`, 工具脚本批量扫描 |
| 报表输出字段 | 风险类型、评分、等级、责任人、整改期限、逾期天数、关闭率 |
| 异常边界 | 岗位角色缺失、重复风险、跨组织协同、人工调级、附件缺失 |
| 验收标准 | 重大风险自动升级审批，逾期任务进入提醒队列 |
| 可转译示例 | `workflow/ks_hr_certificate_workflow_plugin.ts`, `tool/ks_batch_project_risk_scan.ts` |
| 取数建议 | 风险评分模型由配置驱动，脚本只读取规则结果和责任人解析结果 |

### 案例 5: 现场劳务实名制、证书合规与岗位履职

| 项目 | 内容 |
|---|---|
| 业务目标 | 识别证书过期仍在岗、关键岗位缺岗、培训缺失、考勤异常、跨项目重复在岗 |
| 数据输入 | 项目人员台账、证书资料、考勤、培训、岗位配置标准、项目状态 |
| KingScript API 使用点 | `WorkflowPlugin.beforeNodeLeave`, `afterNodeLeave`, `AbstractListPlugin.filterColumnSetFilter` |
| 报表输出字段 | 人员、岗位、证书状态、培训状态、考勤状态、重复在岗项目、合规状态 |
| 异常边界 | 身份证同人异名、注册单位不一致、停工期间缺勤、临时豁免 |
| 验收标准 | 进场提交准确校验证书/培训/重复在岗，证书临期预警准确 |
| 可转译示例 | `workflow/ks_hr_certificate_workflow_plugin.ts` |
| 取数建议 | 身份证、证书、任职台账按人员批量取数，避免人员列表逐行查证书 |

### 案例 6: 项目现场物资到货、验收、消耗与成本偏差

| 项目 | 内容 |
|---|---|
| 业务目标 | 联动采购计划、合同、到货、验收、领用、库存和成本，识别逾期、超合同、超耗、积压 |
| 数据输入 | 材料计划、采购合同、到货单、验收单、领用单、库存、成本数据 |
| KingScript API 使用点 | `AbstractListPlugin.itemClick`, `setMultiSortFields`, `sumDataLoadOnFirstSet` |
| 报表输出字段 | 物资、供应商、合同数量、累计到货、累计验收、领用数量、库存风险、成本偏差 |
| 异常边界 | 多供应商、单位不一致、不合格退货、领用退库、批次管理 |
| 验收标准 | 验收提交判断超合同/超计划/缺质检附件，月度工具输出消耗偏差 |
| 可转译示例 | `list/ks_ar_cashflow_list_plugin.ts` 的列表风险模式 |
| 取数建议 | 库存和成本口径必须由库存/成本服务统一返回，脚本不要自行合并单位 |

### 案例 7: 收入确认与履约进度偏差自动校验

| 项目 | 内容 |
|---|---|
| 业务目标 | 校验合同、履约进度、产值、结算、收入、凭证之间的一致性 |
| 数据输入 | 项目、合同、履约进度单、结算单、收入确认单、财务凭证 |
| KingScript API 使用点 | `AbstractBillPlugIn.propertyChanged`, `beforeDoOperation`, `BigDecimal` 模块导入 |
| 报表输出字段 | 累计收入、履约上限、偏差金额、偏差率、凭证状态、风险等级 |
| 异常边界 | 合同金额异常、审批中变更、负数收入、税率变更、多合同项目 |
| 验收标准 | 提交时识别超合同、超履约、无合同、有收入无进度四类风险 |
| 可转译示例 | `form/ks_project_revenue_form_plugin.ts` |
| 取数建议 | 累计金额按项目+合同+期间一次性汇总，金额比较统一走模块导入的 `BigDecimal` |

### 案例 8: 应收账款、回款核销与账龄穿透风控

| 项目 | 内容 |
|---|---|
| 业务目标 | 建立应收、开票、收款、核销、账龄自动校验，识别长期逾期、超收、跨项目核销 |
| 数据输入 | 应收单、收款单、发票、核销记录、客户、项目、合同 |
| KingScript API 使用点 | `filterContainerInit`, `filterContainerSearchClick`, `sumDataLoadOnFirstSet`, `itemClick` |
| 报表输出字段 | 账龄区间、逾期天数、未核销金额、匹配置信度、风险标签 |
| 异常边界 | 同一业主多编码、无项目回款、部分核销、红字应收、跨组织核销 |
| 验收标准 | 账龄结果与财务表一致，收款审核前识别未匹配项目、超收、跨项目核销 |
| 可转译示例 | `list/ks_ar_cashflow_list_plugin.ts` |
| 取数建议 | 账龄计算封装为服务，脚本只传客户、项目、期间和核销结果 |

### 案例 9: 项目现金流预测、付款计划与实际资金偏差

| 项目 | 内容 |
|---|---|
| 业务目标 | 形成 30/60/90 天现金流滚动预测，识别资金缺口、计划外付款、回款延迟 |
| 数据输入 | 回款计划、实际收款、付款计划、实际付款、银行流水、预算、资金规则 |
| KingScript API 使用点 | `AbstractListPlugin.setMultiSortFields`, `sumDataLoadOnFirstSet`, `WorkflowPlugin.afterNodeLeave` |
| 报表输出字段 | 计划流入、实际流入、计划流出、实际流出、净现金流、最大缺口、偏差率 |
| 异常边界 | 无项目流水、流水拆分、内部调拨、多币别、退款、计划多次调整 |
| 验收标准 | 付款申请识别计划外、超计划、资金缺口三类风险 |
| 可转译示例 | `list/ks_ar_cashflow_list_plugin.ts` |
| 取数建议 | 现金流预测由资金服务按项目/期间批量返回，列表脚本负责展示和筛选 |

### 案例 10: 项目成本预算、合同成本与毛利异常控制

| 项目 | 内容 |
|---|---|
| 业务目标 | 校验预算、合同、实际成本、暂估、付款、收入之间关系，识别超预算、毛利异常 |
| 数据输入 | 项目预算、成本合同、采购入库、工程计量、应付、成本凭证、收入、暂估 |
| KingScript API 使用点 | `AbstractOperationServicePlugIn.onAddValidators`, `beforeExecuteOperationTransaction`, `WorkflowPlugin.beforeNodeEnter` |
| 报表输出字段 | 预算金额、已发生成本、预算余额、合同金额、动态毛利率、成本偏差率 |
| 异常边界 | 多预算版本、科目调整、跨合同付款、暂估冲回、负成本、联合体项目 |
| 验收标准 | 应付审核前识别超预算、超合同、未映射科目，月结工具输出暂估清单 |
| 可转译示例 | `operate/ks_month_close_operation_plugin.ts` |
| 取数建议 | 成本科目映射和毛利口径由财务服务统一，脚本不硬编码科目树 |

### 案例 11: 项目班子配置、任职资格与证书准入

| 项目 | 内容 |
|---|---|
| 业务目标 | 校验项目经理、技术负责人、安全负责人、商务经理等关键岗位是否齐备且资格合规 |
| 数据输入 | 项目、班子明细、人员、证书、任职台账、组织权限、岗位标准 |
| KingScript API 使用点 | `WorkflowPlugin.beforeNodeLeave`, `afterNodeLeave`, 工具脚本批量扫描 |
| 报表输出字段 | 合规状态、缺失岗位、冲突任职、证书不匹配、超限兼岗 |
| 异常边界 | 筹备阶段岗位暂缺、小型项目一人多岗、证书即将过期、借调人员 |
| 验收标准 | 保存时识别岗位缺失，跨项目任职超限阻断，工作流追加 HR/项目管理审批 |
| 可转译示例 | `workflow/ks_hr_certificate_workflow_plugin.ts` |
| 取数建议 | 任职冲突按人员+生效日期一次性查询，证书和组织权限结果缓存到流程变量 |

### 案例 12: 人员调动、项目交接与权限回收断档预警

| 项目 | 内容 |
|---|---|
| 业务目标 | 调动、离职、借调、休假时识别关键岗位断档、待办未转移、权限未回收、交接未完成 |
| 数据输入 | 调动申请、任职台账、流程待办、权限信息、交接清单、人员状态 |
| KingScript API 使用点 | `AbstractOperationServicePlugIn.beforeExecuteOperationTransaction`, `afterExecuteOperationTransaction`, `WorkflowPlugin.afterNodeLeave` |
| 报表输出字段 | 调动风险等级、交接事项、待办转移、权限任务、断档项目、补偿任务 |
| 异常边界 | 未来生效不立即收权、离职待办阻断、接收人无权限、多项目任职、调动撤销 |
| 验收标准 | 调动申请识别关键岗位和待办，离职确认前阻断未完成交接，权限失败可补偿 |
| 可转译示例 | `operate/ks_month_close_operation_plugin.ts`, `workflow/ks_hr_certificate_workflow_plugin.ts` |
| 取数建议 | 待办和权限服务异常时输出“同步失败”并生成重试任务，不误报业务不合规 |

## 注意事项

- 示例只用于知识库，不直接绑定生产对象。
- V7 示例统一为 `.ts`，不再保留错误的 `.ks` Java 风格脚本。
- 报表取数优先服务批量聚合，KingScript 负责触发、过滤、展示、路由和异常汇总。
- 高风险阻断和中低风险提示要分级处理，避免所有异常都阻断业务。

## 相关链接

- `code/ztjg-cosmic-debug/src/main/resources/kingscript/knowledge/common/ks_common_risk_tools.ts`
- `code/ztjg-cosmic-debug/src/main/resources/kingscript/knowledge/form/ks_project_revenue_form_plugin.ts`
- `code/ztjg-cosmic-debug/src/main/resources/kingscript/knowledge/list/ks_ar_cashflow_list_plugin.ts`
- `code/ztjg-cosmic-debug/src/main/resources/kingscript/knowledge/operate/ks_month_close_operation_plugin.ts`
- `code/ztjg-cosmic-debug/src/main/resources/kingscript/knowledge/workflow/ks_hr_certificate_workflow_plugin.ts`
- `code/ztjg-cosmic-debug/src/main/resources/kingscript/knowledge/tool/ks_batch_project_risk_scan.ts`
