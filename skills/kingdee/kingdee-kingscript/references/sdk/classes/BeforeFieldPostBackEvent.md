# BeforeFieldPostBackEvent

## 基本信息

- Java 类名：`kd.bos.form.events.BeforeFieldPostBackEvent`
- TS 导出：`@cosmic/bos-core/kd/bos/form/events` 中的 `BeforeFieldPostBackEvent`
- 事件：`AbstractFormPlugin.beforeFieldPostBack(e)`
- 使用点证据：实际 7.0 构件 `bos-form-metadata` 的脚本声明与事件类，以及 `bos-form-mvc` 的 `FormController.postFieldState` 调用链；目录版本不代表统一补丁号，其他目标须核对自己的依赖。

## 用途与取消边界

服务端收到客户端字段值后，在字段控件将值写入模型之前进行合法性检查。此时请求已经到达服务端。`setCancel(true)` 拒绝的是本次模型更新，不能减少已经发生的网络请求，也不保证被拒绝的输入在保存时会自动重传。

[官方事件总览](https://vip.kingdee.com/knowledge/474603833067386624)将该事件用于输入合法性检查。备注字段减少即时更新应配置真实控件 `FieldEdit.setFireEvtUp(false)`，并先确认业务依赖；不能将普通文本输入全部取消来代替即时更新配置。

## 常用方法

| 方法 | 返回类型（脚本） | 含义 |
|------|----------------|------|
| `getKey()` | string | 控件 key，不自动等于实体字段 key |
| `getValue()` | any | 本次输入值，按真实字段类型解释 |
| `getRowIndex()` | number | 行索引 |
| `getParentRowIndex()` | number | 父行索引 |
| `isCancel()` | boolean | 当前取消状态 |
| `setCancel(boolean)` | void | 拒绝本次提交模型，保留其他插件已有取消 |
| `setValue(any)` | void | 事件对象有此方法；本次控制器仍传原局部值给 postBack，不能据此承诺改值生效 |

本事件没有 `getFieldKey()` 或 `getRow()`。`FieldEdit.getFieldKey()` 是字段控件的方法；行及父行索引的适用含义由目标控件决定。

## 常见错误

- 把服务端合法性校验当成浏览器发请求之前的优化：会拒绝有效输入，且没有省掉已发生的请求。
- 把不执行本次 `FieldEdit.postBack` 写成全局永久禁用 `propertyChanged`：后续其他模型赋值仍可能触发事件。
- 宣称取消后最终一定保存或一定不保存：需核对后续是否再次提交该值及实际保存链，当前 API 不提供这两种保证。
- 主动 `setCancel(false)` 覆盖其他插件的拒绝，或按控件名称猜字段依赖。

## 相关示例

[字段提交边界与八个文本控件即时更新配置](../../examples/plugins/插件示例/表单插件-事件拆分/beforeFieldPostBack.md)。实际网络、分录分页和保存重开仍需目标平台验证。

## 关键词

字段回传、模型更新、即时更新、合法性检查、联动不触发、`BeforeFieldPostBackEvent`、`setFireEvtUp`
