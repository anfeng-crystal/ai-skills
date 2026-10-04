# BeforeDoCheckDataPermissionArgs

## 基本信息

- 名称：`BeforeDoCheckDataPermissionArgs`
- Java 类名：`kd.bos.form.events.BeforeDoCheckDataPermissionArgs`
- TS 导出名：`BeforeDoCheckDataPermissionArgs`
- 所属模块：`@cosmic/bos-core`
- 所属包：`kd/bos/form/events`
- 类型：数据权限校验前事件参数
- 来源：
  - TS 声明：已核验 7.0 构件中的 `kd/bos/form/events` 导出；其他补丁仍按目标声明确认
  - 相关示例：[beforeDoCheckDataPermission.md](../../examples/plugins/插件示例/表单插件-事件拆分/beforeDoCheckDataPermission.md)
  - Javadoc：Cosmic V8.0.1

## 用途概述

用于 `beforeCheckDataPermission(e: BeforeDoCheckDataPermissionArgs)` 事件。回调由 `IFormPlugin` 声明，参数类名中的 `Do` 不属于回调名。可决定是否跳过本次数据权限检查、取消当前行为或给出取消原因；参数对象没有 `getFormId()` 和通用 `put()` 方法。

## 典型场景

- 特殊角色跨组织查看数据时跳过数据权限校验
- 校验失败时自定义取消提示
- 列表多选场景下调整待校验的选择行顺序

## 常用方法

| 方法 | 作用 | 关键参数 | 返回值 | 说明 |
|------|------|----------|--------|------|
| `getSource` | 获取事件源 | 无 | `Object` | 常见为 `FormOperate` |
| `getListSelectedData` | 获取列表选择行 | 无 | `ListSelectedRowCollection` | 列表多选场景常用 |
| `isSkipCheckDataPermission` | 是否跳过权限检查 | 无 | `boolean` | 读取当前策略 |
| `setSkipCheckDataPermission` | 设置跳过权限检查 | `boolean` | `void` | 只跳过本次数据权限检查，不代表其他校验放行 |
| `setCancel` | 取消当前行为 | `boolean` | `void` | 取消会导致相关权限校验失败，可配合取消原因 |
| `setCancelMessage` | 设置取消原因 | `String` | `void` | 让用户知道被拦截原因 |

## 运行时注意事项

- 跳过数据权限检查是高风险能力，必须同时说明角色、组织和账套边界。
- `setCancel(true)` 和 `setSkipCheckDataPermission(true)` 语义不同，不要混用。
- 列表场景下如果依赖选中行，需要先确认事件源是列表操作还是表单操作。

## 常见搭配

- 搭配类：`RequestContext`、`FormOperate`
- 搭配示例：[beforeDoCheckDataPermission.md](../../examples/plugins/插件示例/表单插件-事件拆分/beforeDoCheckDataPermission.md)
- 搭配 FAQ：
  - 能不能跳过权限
  - 怎么给用户返回权限提示

## 常见错误

### 1. 无边界跳过权限校验

高概率原因：
- 只关注“能否操作”，忽略组织和角色边界
- 缺少明确的特权场景说明

### 2. 只取消不提示

高概率原因：
- 忘记设置取消原因
- 以为前端会自动给出默认提示

## 相关示例

- [beforeDoCheckDataPermission.md](../../examples/plugins/插件示例/表单插件-事件拆分/beforeDoCheckDataPermission.md)

## 关键词

- 中文关键词：数据权限、权限前置校验、跳过权限、权限拦截
- 英文关键词：`BeforeDoCheckDataPermissionArgs`
- 常见别名：权限校验前事件、权限前置参数
- 常见报错词：无权限查看、权限被拦截、数据权限检查失败
