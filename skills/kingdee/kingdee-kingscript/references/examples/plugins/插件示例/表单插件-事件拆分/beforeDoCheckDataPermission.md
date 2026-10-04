# beforeCheckDataPermission - 数据权限校验前置处理

## 基本信息

| 属性 | 说明 |
|------|------|
| 所属接口 | `IFormPlugin`，由 `AbstractFormPlugin` 继承 |
| 触发时机 | 执行数据权限校验前触发 |
| 方法签名 | `beforeCheckDataPermission(e: BeforeDoCheckDataPermissionArgs): void` |

参数类名中的 `Do` 不属于回调名。参数对象提供明确的取消、跳过检查与取消原因接口，不是可任意 `put` 键值的 Map。

## 事件入口

```typescript
import { AbstractFormPlugin } from "@cosmic/bos-core/kd/bos/form/plugin";
import { BeforeDoCheckDataPermissionArgs } from "@cosmic/bos-core/kd/bos/form/events";

/** 数据权限校验入口；默认保留平台及其他插件已有的校验决定。 */
class PermissionPreparePlugin extends AbstractFormPlugin {
  /** 接收平台事件；项目权限规则未提供时，不设置取消或跳过标志。 */
  beforeCheckDataPermission(e: BeforeDoCheckDataPermissionArgs): void {
    super.beforeCheckDataPermission(e);
  }
}

let plugin = new PermissionPreparePlugin();
export { plugin };
```

## 共享查询看板的实施要求

共享看板按 `fqueryorg` 选择组织，并用 `fisadminview` 表示页面查询模式。若后续权限实现需要 `queryOrg`、`viewMode`，应先确认该实现实际读取的上下文入口与类型；`BeforeDoCheckDataPermissionArgs` 没有通用 `put` 方法。仅从页面读取这两个字段，不能证明组织上下文已经传入权限服务，也不能把页面开关当作管理员权限依据。

保留组织切换需求，但须由项目既有权限模型核验可查看组织，再按已确认的权限扩展接口传递上下文。上述入口只保留默认验权，不实现组织上下文传递。

## 取消与跳过的区别

- 拦截当前操作：`setCancel(true)`，可配合 `setCancelMessage(...)` 给出原因。
- 明确授权的本次数据权限例外：`setSkipCheckDataPermission(true)`；其他权限和校验仍按各自规则执行。
- 不主动把取消状态设回 `false`，避免覆盖其他插件的决定。

参数和角色示例见 [BeforeDoCheckDataPermissionArgs](../../../../sdk/classes/BeforeDoCheckDataPermissionArgs.md) 与 [表单插件的数据权限事件](../表单插件.md#37-beforecheckdatapermission)。使用前核对目标版本声明和项目权限模型。
