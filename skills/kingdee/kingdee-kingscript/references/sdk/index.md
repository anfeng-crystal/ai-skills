# Kingscript SDK 知识层

## 检索入口
- 已知类名：`indexes/class-index.md`
- 已知方法名：`indexes/method-index.md`、`indexes/methods-by-name.md`
- 已知生命周期：`indexes/methods-lifecycle.md`、`indexes/plugin-index.md`
- 已知场景：`indexes/scenario-index.md`
- 已知关键词：`indexes/keyword-index.md`
- 已知报错：`indexes/error-index.md`
- 已知模块或包：`indexes/module-index.md`、`indexes/package-index.md`

## 目录
```text
sdk/
├─ index.md
├─ strategy.md
├─ docs/
├─ indexes/
├─ classes/
├─ packages/
├─ plugins/
├─ microservices/
├─ manifests/
└─ templates/
```

## 使用规则
- 先用索引缩小范围，再读取具体类卡片、包卡片或示例。
- 方法级问题先走 `indexes/method-index.md`，不要直接整类通读。
- 生成代码前必须确认方法属于当前变量类型或其声明继承链。
- 事件参数不得默认写成 `any`；有明确类型就用明确类型，只剩声明层类型时按声明原样写。
- 没有可靠来源时，不伪造 SDK 类、方法、参数或返回值。

## 高频入口
- Java 与 Kingscript 类型桥接：`docs/java-kingscript-bridge.md`
- 数据操作：`classes/DynamicObject.md`、`classes/DynamicObjectCollection.md`
- 操作结果与校验：`classes/OperationResult.md`、`classes/ValidationErrorInfo.md`、`classes/ValidateResult.md`、`classes/ErrorLevel.md`
- 模型联动：`classes/PropertyChangedArgs.md`
- 插件基类：`classes/AbstractListPlugin.md`、`classes/AbstractConvertPlugIn.md`、`classes/AbstractWriteBackPlugIn.md`
- 操作上下文与扩展参数：`classes/FormOperate.md`、`classes/OperateOption.md`
- 数据访问与异常：`classes/DBRoute.md`、`classes/KDException.md`
- 单据体与元数据：`classes/EntryGrid.md`、`classes/SubEntryGrid.md`、`classes/EntityType.md`、`classes/MainEntityType.md`
- 基础资料与多选资料：`classes/BasedataEdit.md`、`classes/MulBasedataEdit.md`、`classes/BasedataProp.md`
- 弹性域入口：`classes/FlexEdit.md`、`classes/FlexEntityType.md`、`classes/FlexProperty.md`、`classes/FlexProp.md`
