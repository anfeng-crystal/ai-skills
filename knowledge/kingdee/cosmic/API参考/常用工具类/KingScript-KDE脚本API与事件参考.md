# KingScript-V7官方脚本API与事件参考

> 来源: 金蝶云社区官方文章《V7版本，脚本开发使用合集》、金蝶云社区官方知识《KingScript 金蝶云苍穹·脚本开发平台（新版）》、金蝶云社区文章《KingScript轻脚本开发：自定义控件接口开发案例》、本地官方包 `script_modules/@cosmic/bos-core`, `script_modules/@cosmic/bos-script`, 本地运行包 `sdk-bos-kingscript-7.0.jar`; 清洗时已去除导航、登录提示、推荐阅读和广告噪音。
> 日期: 2026-04-13
> 标签: KingScript, KDE, V7脚本, 代码红线, 表单插件, 列表插件, 操作插件, 工作流插件

---

## 摘要

本文按 V7 KingScript 官方写法重新整理脚本 API、事件入口和代码红线。V7 示例优先采用 `import { ... } from '@cosmic/...'`、插件类继承、`let plugin = new XxxPlugin(); export { plugin };` 的写法；旧版 `require("kd.bos...")` 和 `var plugin = new FormPlugin({...})` 只作为历史 KDE 兼容线索，不作为本项目知识库推荐代码。

## 适用版本

- 金蝶云苍穹 V7 KingScript 脚本开发平台。
- 本地模块: `@cosmic/bos-core` 版本 `1.0.0@1758959503000`, `@cosmic/bos-script` 版本 `1.0.0@1756792030000`。
- 本地运行包: `sdk-bos-kingscript-7.0.jar`, `sdk-bos-kingscript-service-7.0.jar`, `bos-kscript-7.0.jar`。

## 核心结论

| 项目 | V7 推荐写法 | 本轮禁止写法 |
|---|---|---|
| 引入平台类 | `import { AbstractBillPlugIn } from '@cosmic/bos-core/kd/bos/bill';` | `require("kd.bos.bill.AbstractBillPlugIn")` |
| 引入 Java 常用类型 | `import { BigDecimal } from '@cosmic/bos-script/java/math';` | `new java.math.BigDecimal(...)` |
| 插件声明 | `class MyPlugin extends AbstractBillPlugIn { ... }` + `export { plugin }` | `var plugin = new FormPlugin({...})` 作为 V7 主示例 |
| 自定义控件数据 | `ArrayList`、`HashMap` 从 `@cosmic/bos-script/java/util` 引入 | 直接塞 TS `{}` 到自定义控件导致运行期数据丢失 |
| 公共工具 | 导出实例或普通函数 | 转译器不支持的 `static` 工具类成员 |
| 脚本依赖 | 官方 `@cosmic` 模块或租户已注册脚本模块 | 本机绝对路径、未开放内部类、跨租户路径 |

## 代码红线准则

| 红线 | 原因 | 替代方式 |
|---|---|---|
| 禁止在 V7 示例中写 `require("kd.bos...")` | 这是旧 KDE/JS 风格，容易与 V7 模块系统混用 | 使用 `@cosmic/bos-core` 模块导入 |
| 禁止 `new java.*`、`org.apache.*`、`com.kingdee.*` 全类名 | 可读性差，也容易误用未开放内部类 | 使用 `@cosmic/bos-script/java/*` 导入开放类型 |
| 禁止绝对路径导入脚本 | 换机器、换租户、换环境立即失效 | 注册为脚本模块或保持示例自包含 |
| 禁止脚本里拼 SQL 或绕过服务助手 | 容易破坏权限、组织隔离和多库边界 | 用 `BusinessDataServiceHelper`、`QueryServiceHelper` 或 Java 服务封装 |
| 禁止事务内跨库保存 | 会触发多库事务风险 | 操作插件事务内只更新当前对象，事务后做通知/补偿 |
| 禁止把旧对象式插件写法当 V7 主方案 | 与官方 V7 文章的 `class + export` 样式不一致 | 统一用类继承与导出实例 |

## 事件矩阵

| 脚本类型 | V7 基类/模块 | 常用事件 | 示例 |
|---|---|---|---|
| 单据/表单脚本 | `AbstractBillPlugIn` from `@cosmic/bos-core/kd/bos/bill` | `afterCreateNewData`, `afterBindData`, `propertyChanged`, `beforeDoOperation`, `afterDoOperation`, `itemClick`, `customEvent` | `form/ks_project_revenue_form_plugin.ts` |
| 列表脚本 | `AbstractListPlugin` from `@cosmic/bos-core/kd/bos/list/plugin` | `filterContainerInit`, `filterContainerSearchClick`, `filterColumnSetFilter`, `setMultiSortFields`, `setEnableCustomSum`, `sumDataLoadOnFirstSet`, `itemClick` | `list/ks_ar_cashflow_list_plugin.ts` |
| 操作脚本 | `AbstractOperationServicePlugIn` from `@cosmic/bos-core/kd/bos/entity/plugin` | `onPreparePropertys`, `onAddValidators`, `beforeExecuteOperationTransaction`, `beginOperationTransaction`, `endOperationTransaction`, `afterExecuteOperationTransaction`, `rollbackOperation`, `onReturnOperation` | `operate/ks_month_close_operation_plugin.ts` |
| 工作流脚本 | `WorkflowPlugin` from `@cosmic/bos-core/kd/bos/workflow/engine/extitf` | `notify`, `beforeNodeEnter`, `afterNodeEnter`, `beforeNodeLeave`, `afterNodeLeave`, `beforeNodeBack`, `beforeTaskReturn` | `workflow/ks_hr_certificate_workflow_plugin.ts` |
| 工具脚本 | 普通导出类、实例或函数 | 由调用方显式调用 | `common/ks_common_risk_tools.ts`, `tool/ks_batch_project_risk_scan.ts` |

## 标准脚本骨架

```typescript
import { AbstractBillPlugIn } from '@cosmic/bos-core/kd/bos/bill';
import { EventObject } from '@cosmic/bos-script/java/util';

class MyBillPlugin extends AbstractBillPlugIn {
    afterBindData(e: EventObject): void {
        super.afterBindData(e);
        this.getView().showTipNotification('KingScript ready');
    }
}

let plugin = new MyBillPlugin();
export { plugin };
```

## 注意事项

- 官方文章中 V7 示例使用 TypeScript 风格；本项目示例文件统一保存为 `.ts`。
- `@cosmic/bos-script/java/*` 是 V7 脚本模块导入，不等同于在代码里写全类名。
- 金额计算可以使用 `BigDecimal`，但必须通过模块导入，禁止散落 `new java.math.BigDecimal`。
- 平台对象只能在苍穹运行期执行，本地验证只做转译、红线扫描、Java 编译和资源处理。

## 相关链接

- https://vip.kingdee.com/article/712266362965667328
- https://vip.kingdee.com/knowledge/474603833067386624?isKnowledge=2&lang=zh-CN&productLineId=29
- https://vip.kingdee.com/article/650018166822744576
- `script_modules/@cosmic/bos-core`
- `script_modules/@cosmic/bos-script`
