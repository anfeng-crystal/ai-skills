# TimerElapsed - 看板汇总轮询与空结果刷新

## 事件前提

实际事件是大写 `TimerElapsed(e: TimerElapsedArgs)`，基类为 `AbstractFormPlugin`；声明没有 `IFormView.startTimer/stopTimer`。开启、生命周期与回调入口复用 [聚合定时事件](../表单插件.md#51-timerelapsed)，先由目标宿主提供已验证的定时请求；不能把下面的查询函数当作定时器注册。

销售看板保留每 **30000 毫秒**刷新 `bos_dashboard_summary` 的需求，首次展示和手动刷新也复用同一函数。实际间隔由宿主实现；若用已核页面缓存节流，以 30000 毫秒为阈值，不承诺浏览器休眠时准点执行。页面释放时按宿主生命周期清理已注册资源，不调用不存在的停止方法。

## queryOne 的真实合同

实际 7.0 脚本声明存在 `QueryServiceHelper.queryOne(entityName, selectFields, QFilter[])`，返回拉平的 `DynamicObject`。它只取第一条符合条件的记录，无匹配返回 null；见 [官方说明](https://vip.kingdee.com/knowledge/135712557746099968)。该查询不会自动计算汇总，也不能把返回对象作为完整单据保存。

- `bos_dashboard_summary` 必须是真实存在的汇总实体；`todo_count/warning_count` 与界面 `ftodoqty/fwarningqty` 按目标元数据核实。
- 过滤条件由调用方明确传入，并限定唯一汇总记录；空数组只适用于已确认的全表单例。无排序的第一条不能解释为“最新汇总”或“全部组织合计”；多行可能时，应先明确聚合/排序规则或校验重复，不能静默任选一条。
- 条件还应包含业务需要的范围与权限约束，不能因页面用户已登录就假定查询自动沿用其数据权限。不在通用示例中虚构组织或用户过滤字段。
- 本机 Java `queryOne` 直接透传 filters；脚本严格类型下参数是 `QFilter[]`。不能由脚本的 null 类型诊断推断 Java 必然拒绝 null，也不能据此判定方法不存在。

## 可复用的刷新函数

无行时明确清空旧显示，区别于查到数值 0；有行的字段 null 保留为 null。如此从“存在汇总”变为“无记录”时，不会继续显示上一次数字。页面字段需支持此未取得数据状态；若业务要求零值或状态提示，由调用方依据真实合同配置，不默认把无记录当零。

```typescript
import { QueryServiceHelper } from "@cosmic/bos-core/kd/bos/servicehelper";
import { IFormView } from "@cosmic/bos-core/kd/bos/form";
import { QFilter } from "@cosmic/bos-core/kd/bos/orm/query";

/**
 * 由首次刷新、TimerElapsed 和手动刷新共同调用，读取并显示销售看板汇总。
 * summaryFilters 由调用方按真实元数据限定唯一汇总行；仅全表单例已确认时允许空数组。
 * 返回 true 表示有汇总行，false 表示无行且已清空旧显示；字段 null 与数值 0 保持原值。
 * 查询结果为只读拉平数据；本函数不生成业务权限条件，不注册定时请求。
 */
export function refreshDashboardSummary(view: IFormView, summaryFilters: QFilter[]): boolean {
  const summary = QueryServiceHelper.queryOne(
    "bos_dashboard_summary",
    "todo_count,warning_count",
    summaryFilters
  );
  const model = view.getModel();
  model.setValue("ftodoqty", summary == null ? null : summary.get("todo_count"));
  model.setValue("fwarningqty", summary == null ? null : summary.get("warning_count"));
  view.updateView("ftodoqty");
  view.updateView("fwarningqty");
  return summary != null;
}
```

已启用事件的插件中，把 `this.getView()` 和已核过滤条件传给 `refreshDashboardSummary`；首次加载、`TimerElapsed`、手动刷新按钮调用相同函数。查询异常原样传播，不吞异常并显示成功，也不在查询失败时用零覆盖数据。本函数未注册定时器、未执行保存，未证明真实权限过滤、数据库结果或页面清空渲染；这些仍需目标环境验证。
