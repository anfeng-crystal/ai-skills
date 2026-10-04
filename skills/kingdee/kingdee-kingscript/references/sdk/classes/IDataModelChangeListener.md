# IDataModelChangeListener

## 基本信息

- 名称：`IDataModelChangeListener`
- Java 类名：`kd.bos.entity.datamodel.events.IDataModelChangeListener`
- TS 导出名：`IDataModelChangeListener`
- 所属模块：`@cosmic/bos-core`
- 所属包：`kd/bos/entity/datamodel/events`
- 类型：模型变更监听接口
- 来源：
  - TS 声明：待按本地 `@cosmic/bos-core` 中 `kd/bos/entity/datamodel/events` 相关声明核对
  - 相关示例：[表单插件.md](../../examples/plugins/插件示例/表单插件.md)
  - 相关案例：[表单插件-事件拆分/index.md](../../examples/plugins/插件示例/表单插件-事件拆分/index.md)
  - Javadoc：Cosmic V8.0.1

## 用途概述

统一承接字段值变化、分录增删改、批量填充和分录移动等模型层事件，是单据联动、分录汇总和批量赋值性能优化的核心入口。

## 典型场景

- `beforePropertyChanged` 中读取待变更值，做前置通知或联动
- `propertyChanged` 中根据新值联动金额、税额或状态
- 分录删除、移动、批量填充后重算合计
- 通过 `isSupportBatchPropChanged()` 打开批量值更新能力

## 常用方法

| 方法 | 作用 | 关键参数 | 返回值 | 说明 |
|------|------|----------|--------|------|
| `beforePropertyChanged` | 字段变更前通知或联动 | `PropertyChangedArgs` | `void` | 从 `getProperty()` / `getChangeSet()` 读取字段与各行变更；无 `setCancel` |
| `propertyChanged` | 字段变更后联动 | `PropertyChangedArgs` | `void` | 常与 `ChangeData` 配合读取变化集 |
| `initPropertyChanged` | 初始化阶段字段变更 | `PropertyChangedArgs` | `void` | 下推、复制、引入时常见 |
| `beforeDeleteRow` / `afterDeleteRow` | 删除分录前后处理 | 对应事件参数 | `void` | 常用于校验与重算 |
| `beforeBatchFillEntry` | 批量填充分录前处理 | `BeforeBatchFillEntryArgs` | `void` | 常用于金额预估和额度校验 |
| `isSupportBatchPropChanged` | 是否启用批量值更新 | 无 | `boolean` | 批量选择基础资料时影响性能 |

## 运行时注意事项

- `beforePropertyChanged` / `propertyChanged` 都通过 `getChangeSet()` 读取变化集合，不要默认只处理第一条变更。
- `beforePropertyChanged` 的 `PropertyChangedArgs` 没有取消 API，页面提示或回调 `return` 不阻止赋值；硬约束应使用目标已确认支持的校验或编辑控制路径。初始化阶段（包括 `afterCreateNewData` 中改值）不触发该前置事件。
- 不建议在 `propertyChanged` 中回滚字段值，容易和其他已触发逻辑冲突。
- `initPropertyChanged` 和用户交互触发的 `propertyChanged` 不是同一个时机。
- TS 声明存在不代表所有事件在当前插件类型和页面场景都一定触发。

前置事件依据：[官方 beforePropertyChanged](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=228912833529089024&productLineId=29)（2026-07-31 11:59 更新，未标完整版本范围），及本地 `@cosmic/bos-core` 声明包 `1.0.0`（buildTime `2025-11-12 15:28:03`）、`7.0` 标记 JAR。这里只核对该事件合同，不将卡片的 V8.0.1 来源或本地 JAR 标签视作所有事件/目标补丁的兼容证明。

## 常见搭配

- 搭配类：`ChangeData`、`AbstractFormDataModel`、`AbstractBillPlugIn`
- 搭配示例：
  - [beforePropertyChanged.md](../../examples/plugins/插件示例/表单插件-事件拆分/beforePropertyChanged.md)
  - [propertyChanged.md](../../examples/plugins/插件示例/表单插件-事件拆分/propertyChanged.md)
- 搭配 FAQ：
  - 批量选择资料为什么很慢
  - 联动计算写在哪个事件

## 常见错误

### 1. 只处理第一条变更

高概率原因：
- 把 `e.getChangeSet()` 当成单条数据用
- 忽略批量赋值和批量选择场景

### 2. 在错误阶段做联动

高概率原因：
- 初始化阶段逻辑写进了用户交互阶段
- 页面事件和模型事件没有分层

## 相关示例

- [表单插件.md](../../examples/plugins/插件示例/表单插件.md)
- [propertyChanged.md](../../examples/plugins/插件示例/表单插件-事件拆分/propertyChanged.md)

## 关键词

- 中文关键词：模型变更监听、字段联动、分录事件、批量值更新
- 英文关键词：`IDataModelChangeListener`
- 常见别名：字段变化监听、分录监听
- 常见报错词：字段联动不生效、批量赋值很慢、分录汇总不更新
