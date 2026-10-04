# 后台任务插件模板

## 适用场景

- 调度任务、后台任务、长耗时异步处理

## 标准 import

```typescript
import { AbstractTask } from "@cosmic/bos-core/kd/bos/schedule/executor";
import { RequestContext } from "@cosmic/bos-core/kd/bos/context";
import { Map } from "@cosmic/bos-script/java/util";
```

## 模板代码

```typescript
import { AbstractTask } from "@cosmic/bos-core/kd/bos/schedule/executor";
import { RequestContext } from "@cosmic/bos-core/kd/bos/context";
import { Map } from "@cosmic/bos-script/java/util";

class MyPlugin extends AbstractTask {

  /** 调度入口；参数键、类型及可执行范围由调用方约定并在业务实现中校验。 */
  execute(context: RequestContext, params: Map): void {
    // 在此实现已授权的任务逻辑；不要以 setter 或 stop 代替执行入口。
  }
}

let plugin = new MyPlugin();

export { plugin };
```

## 起手建议

- `execute` 是任务入口；保留明确的 `RequestContext` / Java `Map` 参数，不用 `any` 隐去事件合同。
- 后台任务要优先考虑任务标识、日志、消息处理和可停止性；消息、进度及停止流程须核对目标脚本声明，不从 Java 同名类直接移植。
- 如果只是页面按钮点击后的即时逻辑，不要误用任务插件。
- 长耗时任务优先把输入参数设计成简单值，不要直接传页面对象。

依据：[官方调度插件 KingScript 开发指南](https://vip.kingdee.com/knowledge/720667855817283072)。使用前仍核对目标声明；此入口与已核验的 7.0 脚本声明一致，不代表所有补丁已验证。

## 下一步去哪看

- 后台任务示例：`../examples/plugins/插件示例/后台任务.md`
- 前端任务提醒点击处理（独立于后台 `execute`）：[大任务插件](../examples/plugins/插件示例/大任务插件.md)
