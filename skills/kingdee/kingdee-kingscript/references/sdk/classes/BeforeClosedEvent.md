# BeforeClosedEvent

## 基本信息

- 名称：`BeforeClosedEvent`
- Java 类名：`kd.bos.form.events.BeforeClosedEvent`
- TS 导出名：`BeforeClosedEvent`
- 所属模块：`@cosmic/bos-core`
- 所属包：`kd/bos/form/events`
- 类型：页面关闭前事件参数
- 相关示例：[beforeClosed.md](../../examples/plugins/插件示例/表单插件-事件拆分/beforeClosed.md)

## 用途概述

用于在页面关闭前做最后一次确认或取消关闭；其中数据变更检查参数面向 `BillView`，不能把单据的未保存提示效果推广到所有动态表单。

## 典型场景

- 页面存在未保存修改时弹确认提示
- 单据页面按业务要求跳过数据变更检查
- 页面关闭前阻止用户离开，先补齐关键输入

## 常用方法

| 方法 | 作用 | 说明 |
|------|------|------|
| `setCancel(boolean)` | 取消关闭 | `true` 拦截本次关闭；与是否检查数据变更分别控制 |
| `isCancel()` | 判断是否已取消 | 便于复用校验逻辑 |
| `setCheckDataChange(boolean)` | 控制 `BillView` 的数据变更检查 | V8.0.1 SDK 索引：`false` 不检测，`true` 检测；开启检测不等于必定弹提示 |
| `isCheckDataChange()` | 查看是否检查数据变更 | V8.0.1 SDK 索引：`false` 不检测，`true` 检测 |
| `setSkipNoField(boolean)` | 跳过未绑定物理字段的改动检查 | 适合纯展示或扩展字段场景 |
| `isSkipNoField()` | 查看是否跳过未绑定字段检查 | 用于排查误提示 |

## 运行时注意事项

- `beforeClosed` 负责关闭前判断，`pageRelease` 负责资源清理，职责不要混用。
- 关闭拦截和脏数据提示是两层概念，不要只改其中一层就期待整体行为都变。
- `setCheckDataChange(false)` 不是取消关闭，也不是保存数据；禁止关闭使用 `setCancel(true)`，保留修改仍需正常保存。
- 跳过未绑定字段检查时，仍要确认真正绑定到模型的字段是否需要保留提示。

## 布尔方向与版本依据

[V8.0.1 SDK Javadoc](https://dev.kingdee.com/sdk/Cosmic%20V8.0.1/javadoc/kd/bos/form/events/BeforeClosedEvent.html) 的本地索引明确注明 `false` 不检测、`true` 检测 `BillView` 中 Model 数据变化并给出提示。本地 `bos-form-mvc` 的 `hotfix_7.0.16_20250901` 构建中，`BillView.close()` 的消费分支与此一致：仅在开启检查且检测到变化时进入确认提示；同构建的 `FormView.close()` 未消费这个检查参数。这是该构建的静态旁证，没有验证其他版本或 KingScript 引擎运行行为。

[官方 beforeClosed 事件页](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=222768769984991488&productLineId=29) 的布尔说明写为 `true` 退出时不提示，与上述 SDK 注释及本地消费分支冲突。复用本卡或示例前须按目标 SDK/Javadoc 与实际依赖确认方向和生效范围；不把任一来源扩展为全版本合同。

## 常见搭配

- 搭配事件：`beforeClosed`
- 搭配事件：`pageRelease`
- 搭配示例：[beforeClosed.md](../../examples/plugins/插件示例/表单插件-事件拆分/beforeClosed.md)
- 延伸示例：[pageRelease.md](../../examples/plugins/插件示例/表单插件-事件拆分/pageRelease.md)

## 常见错误

### 1. 误把资源释放写到 beforeClosed

高概率原因：
- 没区分“关闭前判断”和“页面释放”

### 2. 一直弹未保存提示

高概率原因：
- `setCheckDataChange` 与 `setSkipNoField` 配置不符合页面实际字段结构

## 关键词

- 中文关键词：关闭前校验、未保存提示、取消关闭、脏数据检查
- 英文关键词：`BeforeClosedEvent`
- 常见别名：beforeClosed 参数、关闭前事件参数
