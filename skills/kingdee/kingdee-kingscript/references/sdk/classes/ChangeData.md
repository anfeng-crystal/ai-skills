# ChangeData

## 基本信息

- 名称：`ChangeData`
- Java 类名：`kd.bos.entity.datamodel.events.ChangeData`
- TS 导出名：`ChangeData`
- 所属模块：`@cosmic/bos-core`
- 所属包：`kd/bos/entity/datamodel/events`
- 类型：字段变化记录对象
- 来源：
  - TS 声明：已核对 `@cosmic/bos-core` 1.0.0（包构建时间 2025-11-12）的 `kd/bos/entity/datamodel/events` 导出与 `RowDataEntity` 继承；包版本不代表平台版本，使用时仍按目标声明核对
  - 相关示例：[propertyChanged.md](../../examples/plugins/插件示例/表单插件-事件拆分/propertyChanged.md)
  - Javadoc：Cosmic V8.0.1
  - [官方 propertyChanged 事件](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=228917111786574080&productLineId=29)：2026-07-31 更新，正文未标完整版本范围

## 用途概述

表示一次字段变化的明细记录，通常从 `PropertyChangedArgs.getChangeSet()` 里逐条读取，用来拿到当前行、新旧值和对应数据实体。

## 典型场景

- 从事件 `e.getProperty().getName()` 识别字段，再逐条处理变化集
- 读取当前分录行索引，回写当前行金额或税额
- 比较新旧值，决定是否提示或跳过重复处理
- 在复杂分录结构里通过父行索引定位上级数据

## 常用方法

| 方法 | 作用 | 关键参数 | 返回值 | 说明 |
|------|------|----------|--------|------|
| `getNewValue` | 获取新值 | 无 | `Object` | 联动计算最常用入口 |
| `getOldValue` | 获取旧值 | 无 | `Object` | 判断是否真的变化 |
| `getRowIndex` | 获取当前行号 | 无 | `int` | 表头常需结合实际上下文判断 |
| `getParentRowIndex` | 获取父行号 | 无 | `int` | 多级分录或嵌套结构时使用 |
| `getDataEntity` | 获取当前数据包 | 无 | `DynamicObject` | 读取更多上下文字段 |

## 运行时注意事项

- 返回值通常是 Java 侧对象，不要想当然按 JS 原生类型处理。
- `rowIndex` 和 `parentRowIndex` 的含义依赖当前实体结构，不能跨实体硬套。
- 一次事件通过 `PropertyChangedArgs.getProperty()` 指明变化字段，`getChangeSet()` 可包含该字段的多条变更；逐条读取行号与新旧值，不只处理首条。
- `ChangeData` 的行号、父行号和数据包方法来自 `RowDataEntity`；不要把字段名读取写成 `change.getPropertyName()`。其他事件参数须按其声明核对，不能套用此类的接口。

## 常见搭配

- 搭配类：`IDataModelChangeListener`、`PropertyChangedArgs`
- 搭配示例：[propertyChanged.md](../../examples/plugins/插件示例/表单插件-事件拆分/propertyChanged.md)
- 搭配 FAQ：
  - 怎么拿当前变化行
  - 怎么比较新旧值

## 常见错误

### 1. 把 `Object` 直接当成 JS 原生类型

高概率原因：
- 忽略 Java 桥接对象
- 没结合 `BigDecimal`、`Date` 等运行时类型处理

### 2. 只按字段名处理，不看行号

高概率原因：
- 忽略分录场景
- 用表头逻辑覆盖了分录逻辑

## 相关示例

- [propertyChanged.md](../../examples/plugins/插件示例/表单插件-事件拆分/propertyChanged.md)

## 关键词

- 中文关键词：变更集、字段变化、新旧值、行索引
- 英文关键词：`ChangeData`
- 常见别名：字段变更项、变化明细
- 常见报错词：拿不到当前行、取值类型不对、联动重复触发
