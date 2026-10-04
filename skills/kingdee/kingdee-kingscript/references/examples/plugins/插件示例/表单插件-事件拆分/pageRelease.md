# pageRelease - 页面释放事件

## 事件合同

`AbstractFormPlugin` 的真实签名为 `pageRelease(e: $.java.util.EventObject): void`，事件源为 `IFormView`。[官方说明](https://vip.kingdee.com/knowledge/222769921389358336)指出其在界面关闭后的资源释放阶段触发，比 `destory` 稍晚。导出类名是 `AbstractFormPlugin`，不是 `AbstractFormPlugIn`。

正常释放路径在派发事件前已释放控件和数据模型，页面缓存则稍后释放。此处可收尾已知资源，不再依赖模型读取或控件交互；不是保存或关闭前取消事件。详细调用顺序及七键打印预览缓存示例见[聚合说明](../表单插件.md#49-pagerelease)。

## 大屏清理需求与最小入口

原场景保留：页面按 `15000` 毫秒刷新并注册自定义监听，关闭后释放对应资源，避免反复打开导致重复监听或资源占用。以下只提供已确认的事件入口，未启动或停止定时器，也未注销任何实际监听：

```typescript
import { AbstractFormPlugin } from "@cosmic/bos-core/kd/bos/form/plugin";

/** 页面释放入口；仅接入已核实的资源释放函数，不在此时依赖控件或模型。 */
class ResourceCleanupPlugin extends AbstractFormPlugin {
  /** e 由平台传入；项目负责接入实际定时机制与自定义监听的释放函数。 */
  override pageRelease(e: $.java.util.EventObject): void {
    super.pageRelease(e);
  }
}

const plugin = new ResourceCleanupPlugin();
export { plugin };
```

- `IFormView` 未公开 `startTimer/stopTimer`。平台定时回调的开启合同见[TimerElapsed](../表单插件.md#51-timerelapsed)；不能用自造视图方法实现 15 秒需求。
- 若项目使用自己的定时器或外部监听，应在创建时确定句柄、所属页面及真实释放函数，再接入本事件；不要关闭其它页面的共享资源，也不要凭一次回调保证故障时完成清理。
- `super.pageRelease(e)` 的默认实现为空，保留调用不意味着已完成项目资源释放。完成实际接线后才验证刷新停止、监听注销与重复打开行为；本例只是声明兼容的入口。
