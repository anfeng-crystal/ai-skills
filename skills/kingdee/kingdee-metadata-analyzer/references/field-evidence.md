# 字段证据分层

## 目标

字段结论必须区分实体字段、页面控件、物理列、分录层级和代码读写位置，避免把一个层级的证据外推到另一个层级。

## 证据层级

| 层级 | 说明 | 常见来源 |
|---|---|---|
| 实体字段 | `fieldKey`、字段名称、字段类型、引用实体 | `t_meta_entitydesign.fdata`、quick query 字段输出 |
| 页面控件 | 字段是否出现在 PC/移动页面、控件位置、可见/只读状态 | `t_meta_formdesign.fdata`、全景 analyzer |
| 分录层级 | 字段属于单据头、分录、子分录或派生页面 | entity XML 层级、字段父节点 |
| 物理列 | 数据库列名、表名、是否持久化 | 实体设计、表结构、平台字段映射 |
| 代码读写 | 插件中读取、写入、过滤或保存字段的位置 | 源码、反编译结果、扫描报告 |

## 判断规则

- `fieldKey` 存在只证明实体设计里有字段，不证明它在目标页面可见或可编辑。
- 单据体字段不能按单据头字段方式读取；必须标注 `entryKey` 或写“未确认”。
- 未拿到物理列证据时，`physicalColumn` 写 `null`，不要由字段标识推断列名。
- 字段类型使用元数据原始类型，例如 `CheckBoxField`、`OrgField`、`BasedataField`、`TextAreaField`。
- 代码扫描发现字段读写时，要区分读取、写入、查询过滤、保存提交和 UI 控件赋值。

## JSON 字段格式

```json
{
  "fieldKey": "field_key",
  "name": "字段名",
  "fieldType": "TextField",
  "entryKey": null,
  "physicalColumn": null,
  "evidence": ["entitydesign", "formdesign", "source"]
}
```

## 降级输出

证据不足时不要给确定结论，按以下方式输出：

- 字段存在但页面位置未知：`evidence=["entitydesign"]`，说明页面挂载未确认。
- 页面有控件但物理列未知：`physicalColumn=null`。
- quick query 有警告或截断：把字段列为摸底结果，并建议全景分析或直接读取设计 XML。
