# KingScript-V7官方脚本高级开发指南

> 来源: 金蝶云社区官方文章《V7版本，脚本开发使用合集》、金蝶云社区官方知识《KingScript 金蝶云苍穹·脚本开发平台（新版）》、金蝶云社区文章《KingScript轻脚本开发：自定义控件接口开发案例》、本项目 V7 脚本示例; 已按知识库规范清洗掉页面导航、登录提示、推荐阅读和无关分享信息。
> 日期: 2026-04-13
> 标签: KingScript, V7脚本, 报表取数, QFilter, 事务边界, 代码红线

---

## 摘要

本文给出 KingScript V7 在复杂报表、表单联动、列表筛选、操作事务、工作流路由和批处理场景中的推荐写法。重点不是把 Java 代码翻译成脚本，而是按官方 `@cosmic` 模块、类继承、导出插件实例的方式组织脚本。

## 适用版本

- 金蝶云苍穹 V7 KingScript。
- 本项目 Java 8 + Gradle Wrapper。
- 示例在本地通过 `sdk-bos-kingscript-7.0.jar` 转译和红线扫描，平台对象需在 KDE/苍穹运行期联调。

## 详细内容

### 1. V7 官方写法模板

```typescript
import { AbstractBillPlugIn } from '@cosmic/bos-core/kd/bos/bill';
import { PropertyChangedArgs } from '@cosmic/bos-core/kd/bos/entity/datamodel/events';

class RevenuePlugin extends AbstractBillPlugIn {
    propertyChanged(e: PropertyChangedArgs): void {
        super.propertyChanged(e);
        const key = e.getProperty().getName();
        if (key === 'f_total_revenue') {
            this.getView().showTipNotification('收入字段已变更');
        }
    }
}

let plugin = new RevenuePlugin();
export { plugin };
```

### 2. 报表取数建议

| 场景 | 推荐做法 | 禁止/慎用 |
|---|---|---|
| 表单实时联动 | 当前单据字段用 `this.getModel().getValue()`，外部累计值交给 Java 服务批量聚合 | 字段变化事件里逐行查库 |
| 列表筛选 | `QFilter`, `QCP` 从 `@cosmic/bos-core/kd/bos/orm/query` 导入 | 脚本拼 SQL |
| 金额比较 | `BigDecimal` 从 `@cosmic/bos-script/java/math` 导入 | JS number 直接比较财务金额 |
| 自定义控件数据 | `ArrayList`, `HashMap` 从 `@cosmic/bos-script/java/util` 导入 | 直接传 TS `{}` 给控件 |
| 月结/关账 | 事务前批量检查，事务内只更新当前对象，事务后通知/补偿 | 事务内跨库保存 |

### 3. 列表过滤示例

```typescript
import { AbstractListPlugin } from '@cosmic/bos-core/kd/bos/list/plugin';
import { QFilter, QCP } from '@cosmic/bos-core/kd/bos/orm/query';

class RiskListPlugin extends AbstractListPlugin {
    filterContainerSearchClick(e: any): void {
        const projectId = e.getFilterValue('project_id');
        if (projectId !== null && e.addQFilter) {
            e.addQFilter(new QFilter('project_id', QCP.equals, projectId));
        }
    }
}

let plugin = new RiskListPlugin();
export { plugin };
```

### 4. 操作插件事务边界

| 阶段 | 事件 | 建议 |
|---|---|---|
| 字段准备 | `onPreparePropertys` | 只预加载需要校验和回写的字段 |
| 校验 | `onAddValidators` | 阻断重复关账、重大风险未关闭等硬条件 |
| 事务前 | `beforeExecuteOperationTransaction` | 批量查询、构造上下文、生成批次号 |
| 事务内 | `beginOperationTransaction`, `endOperationTransaction` | 只更新当前操作对象必要字段 |
| 事务后 | `afterExecuteOperationTransaction` | 跨对象通知、异步扫描、补偿任务 |
| 回滚 | `rollbackOperation` | 恢复缓存、追加补偿日志 |

### 5. 工作流脚本边界

工作流脚本适合读写流程变量、控制节点流向、设置审批标签，不适合做大批量取数。复杂规则应在表单、操作或工具脚本阶段计算成变量，例如 `ks_hr_risk_score`、`ks_next_approver_tag`。

### 6. 本轮示例文件

| 文件 | 用途 |
|---|---|
| `common/ks_common_risk_tools.ts` | 金额、风险等级、批次号、分片工具 |
| `form/ks_project_revenue_form_plugin.ts` | 项目产值、履约进度、收入确认偏差表单联动 |
| `list/ks_ar_cashflow_list_plugin.ts` | 应收账龄、现金流缺口列表筛选和合计 |
| `operate/ks_month_close_operation_plugin.ts` | 月结/关账操作事务分段 |
| `workflow/ks_hr_certificate_workflow_plugin.ts` | HR 证书、班子配置、审批路由 |
| `tool/ks_batch_project_risk_scan.ts` | 项目风险批量扫描工具 |

## 注意事项

- V7 脚本示例禁止混入旧 KDE `var plugin = new FormPlugin({...})` 主写法。
- 禁止在脚本中出现本机绝对路径和 Java 全类名。
- 本地转译通过不等于租户运行通过，最终仍需绑定实际表单、列表、操作、流程节点联调。
- 若必须调用复杂 Java 能力，优先封装为开放服务或工具类，再通过官方模块/服务助手调用。

## 相关链接

- https://vip.kingdee.com/article/712266362965667328
- https://vip.kingdee.com/knowledge/474603833067386624?isKnowledge=2&lang=zh-CN&productLineId=29
- https://vip.kingdee.com/article/650018166822744576
- `code/ztjg-cosmic-debug/src/main/resources/kingscript/knowledge/`
